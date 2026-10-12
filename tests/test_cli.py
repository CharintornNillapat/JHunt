# tests/test_cli.py
"""
Unit and integration tests for CLI argument parsing, subcommand execution,
and pipeline orchestration in main.py.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from main import (
    build_parser,
    get_config,
    main,
    run_alert_pipeline,
    run_analyze_pipeline,
    run_backfill_pipeline,
    run_full_pipeline,
)
from src.extractor.schemas import ExtractedJob, ProjectIdeaSpec
from src.storage.db import DatabaseManager
from state_manager import StateManager


class TestCLIParsing(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_default_empty_args(self):
        args = self.parser.parse_args([])
        self.assertIsNone(args.command)

    def test_run_subcommand_args(self):
        args = self.parser.parse_args(["run", "--all", "--limit", "15", "--role", "Backend Engineer"])
        self.assertEqual(args.command, "run")
        self.assertTrue(args.all)
        self.assertEqual(args.limit, 15)
        self.assertEqual(args.role, "Backend Engineer")

    def test_run_subcommand_default_limit(self):
        args = self.parser.parse_args(["run", "--all"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.limit, 10)

    def test_alert_subcommand_args(self):
        args = self.parser.parse_args(["alert", "--limit", "5"])
        self.assertEqual(args.command, "alert")
        self.assertEqual(args.limit, 5)

    def test_analyze_subcommand_args(self):
        args = self.parser.parse_args(["analyze", "--role", "Data Engineer / Data Analyst", "--limit", "20"])
        self.assertEqual(args.command, "analyze")
        self.assertEqual(args.role, "Data Engineer / Data Analyst")
        self.assertEqual(args.limit, 20)

    def test_backfill_salaries_subcommand_args(self):
        args = self.parser.parse_args(["backfill-salaries"])
        self.assertEqual(args.command, "backfill-salaries")
        self.assertTrue(args.dry_run)
        self.assertIsNone(args.limit)

        args_apply = self.parser.parse_args(["backfill-salaries", "--apply", "--limit", "30"])
        self.assertEqual(args_apply.command, "backfill-salaries")
        self.assertFalse(args_apply.dry_run)
        self.assertEqual(args_apply.limit, 30)

        args_dry = self.parser.parse_args(["backfill-salaries", "--dry-run"])
        self.assertTrue(args_dry.dry_run)


class TestSubcommandRouting(unittest.TestCase):
    @patch("main.run_full_pipeline")
    def test_main_defaults_to_run_all(self, mock_full):
        mock_full.return_value = {"scraped": 0}
        code = main([])
        self.assertEqual(code, 0)
        mock_full.assert_called_once()

    @patch("main.run_alert_pipeline")
    def test_main_routes_alert(self, mock_alert):
        mock_alert.return_value = 2
        code = main(["alert"])
        self.assertEqual(code, 0)
        mock_alert.assert_called_once()

    @patch("main.run_analyze_pipeline")
    def test_main_routes_analyze(self, mock_analyze):
        mock_analyze.return_value = Path("test.md")
        code = main(["analyze", "--role", "DevOps / Cloud / Platform Engineer"])
        self.assertEqual(code, 0)
        mock_analyze.assert_called_once()

    @patch("main.run_backfill_pipeline")
    def test_main_routes_backfill_salaries(self, mock_backfill):
        mock_backfill.return_value = {"total_candidates": 0}
        code = main(["backfill-salaries", "--apply", "--limit", "50"])
        self.assertEqual(code, 0)
        mock_backfill.assert_called_once_with(limit=50, dry_run=False)

    @patch("main.get_active_scrapers")
    def test_run_scrapers_configures_per_adapter_limits(self, mock_get_scrapers):
        mock_jobsdb = MagicMock()
        mock_jobsdb.__class__.__name__ = "JobsDBScraper"
        mock_blognone = MagicMock()
        mock_blognone.__class__.__name__ = "BlognoneScraper"
        mock_jobthai = MagicMock()
        mock_jobthai.__class__.__name__ = "JobThaiScraper"
        mock_get_scrapers.return_value = [mock_jobsdb, mock_blognone, mock_jobthai]

        from main import run_scrapers

        run_scrapers({"keywords": ["python"]})

        mock_jobsdb.scrape.assert_called_once_with(keywords=["python"], limit=150, known_ids=set())
        mock_blognone.scrape.assert_called_once_with(keywords=["python"], limit=30, known_ids=set())
        mock_jobthai.scrape.assert_called_once_with(keywords=["python"], limit=30, known_ids=set())


# main.py runs load_dotenv() at import, so a developer's real .env is in os.environ.
# Blank the credentials so the pipeline under test can never reach production
# Turso or Gemini (earlier runs inserted test blueprints into the live database).
@patch.dict("os.environ", {"TURSO_DATABASE_URL": "", "TURSO_AUTH_TOKEN": "", "GEMINI_API_KEY": ""})
class TestPipelineOrchestration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jhunt_cli_test_")
        self.db_path = Path(self.temp_dir) / "market.db"
        self.state_path = Path(self.temp_dir) / "seen_jobs.json"
        self.export_dir = Path(self.temp_dir) / "ideas"

        self.db = DatabaseManager(db_path=self.db_path)
        self.state = StateManager(state_file=str(self.state_path))

        self.sample_job = {
            "id": "cli_job_001",
            "title": "Junior Python Developer",
            "company": "Bangkok Soft",
            "url": "https://example.com/cli_1",
            "location": "Bangkok",
            "salary": "40,000 THB",
            "work_type": "Full-time",
            "teaser": "Python and FastAPI junior role",
            "bullet_points": ["Python", "FastAPI"],
            "listing_date": "2026-10-10",
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("main.run_scrapers")
    def test_run_alert_pipeline_execution(self, mock_scrapers):
        mock_scrapers.return_value = [self.sample_job]
        mock_notifier = MagicMock()
        mock_notifier.send_job_alert.return_value = True

        config = {
            "keywords": ["python developer"],
            "title_filter": ["python", "developer"],
            "gemini_enabled": False,
        }

        sent = run_alert_pipeline(
            config=config,
            state=self.state,
            notifier=mock_notifier,
        )
        self.assertEqual(sent, 1)
        mock_notifier.send_job_alert.assert_called_once()

    def test_run_analyze_pipeline_execution(self):
        # Seed DB
        self.db.save_job(self.sample_job)
        self.db.save_extracted_skills(
            "cli_job_001",
            ExtractedJob(
                job_title="Junior Python Developer",
                company="Bangkok Soft",
                must_have_skills=["Python", "FastAPI"],
                databases=["PostgreSQL"],
                cloud_infra=["Docker"],
            ),
        )

        config = {
            "export_dir": str(self.export_dir),
            "gemini_api_key": None,  # Trigger deterministic fallback spec
        }

        exported_path = run_analyze_pipeline(
            config=config,
            db=self.db,
            target_role="Backend Engineer",
        )
        self.assertIsNotNone(exported_path)
        self.assertTrue(exported_path.exists())
        self.assertIn("backend-engineer", exported_path.name)

    @patch("main.run_scrapers")
    def test_run_full_pipeline_execution(self, mock_scrapers):
        mock_scrapers.return_value = [self.sample_job]
        mock_notifier = MagicMock()
        mock_notifier.send_job_alert.return_value = True
        mock_notifier.send_market_brief.return_value = True

        config = {
            "keywords": ["python developer"],
            "title_filter": ["python", "developer"],
            "gemini_enabled": False,
            "gemini_api_key": None,  # Offline fallback
            "gemini_model": "gemini-3.8-flash",
            "export_dir": str(self.export_dir),
        }

        results = run_full_pipeline(
            config=config,
            db=self.db,
            state=self.state,
            notifier=mock_notifier,
            limit=1,
            target_role="Backend Engineer",
        )

        self.assertEqual(results["scraped"], 1)
        self.assertEqual(results["new_stored"], 1)
        self.assertEqual(results["alerted"], 1)
        self.assertIsNotNone(results["exported_spec"])
        mock_notifier.send_market_brief.assert_called_once()

    @patch("main.get_storage")
    def test_backfill_salaries_dry_run_leaves_db_unchanged(self, mock_get_storage):
        mock_get_storage.return_value = self.db

        with self.db._connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, title, company, url, salary, min_salary, max_salary, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("bf_job_1", "Backend Dev", "Co 1", "https://example.com/bf1", "50,000 THB", None, None, "THB"),
            )

        res = run_backfill_pipeline(limit=10, dry_run=True)
        self.assertEqual(res["total_candidates"], 1)
        self.assertEqual(res["parsed_count"], 1)
        self.assertEqual(res["applied_count"], 0)

        with self.db._connection() as conn:
            row = conn.execute("SELECT min_salary, max_salary FROM jobs WHERE id = 'bf_job_1'").fetchone()
            self.assertIsNone(row["min_salary"])
            self.assertIsNone(row["max_salary"])

    @patch("main.get_storage")
    def test_backfill_salaries_apply_persists_parsed_values(self, mock_get_storage):
        mock_get_storage.return_value = self.db

        with self.db._connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, title, company, url, salary, min_salary, max_salary, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("bf_job_2", "Backend Dev", "Co 2", "https://example.com/bf2", "50,000 - 70,000 THB", None, None, "THB"),
            )
            conn.execute(
                """
                INSERT INTO jobs (id, title, company, url, salary, raw_content, min_salary, max_salary, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("bf_job_3", "Data Eng", "Co 3", "https://example.com/bf3", "", '{"description": "salary 45k - 60k THB"}', None, None, "THB"),
            )

        res = run_backfill_pipeline(limit=10, dry_run=False)
        self.assertEqual(res["total_candidates"], 2)
        self.assertEqual(res["parsed_count"], 2)
        self.assertEqual(res["applied_count"], 2)
        self.assertEqual(res["currencies"].get("THB"), 2)

        with self.db._connection() as conn:
            row2 = conn.execute("SELECT min_salary, max_salary, currency FROM jobs WHERE id = 'bf_job_2'").fetchone()
            self.assertEqual(row2["min_salary"], 50000)
            self.assertEqual(row2["max_salary"], 70000)
            self.assertEqual(row2["currency"], "THB")

            row3 = conn.execute("SELECT min_salary, max_salary, currency FROM jobs WHERE id = 'bf_job_3'").fetchone()
            self.assertEqual(row3["min_salary"], 45000)
            self.assertEqual(row3["max_salary"], 60000)

    @patch("scripts.backfill_salaries.get_storage")
    def test_standalone_script_backfill_salaries(self, mock_get_storage):
        mock_get_storage.return_value = self.db
        import scripts.backfill_salaries as script_module

        with self.db._connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, title, company, url, salary, min_salary, max_salary, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("bf_job_script", "Backend Dev", "Co S", "https://example.com/bfs", "60,000 THB", None, None, "THB"),
            )

        exit_code = script_module.main(["--dry-run", "--limit", "5"])
        self.assertEqual(exit_code, 0)
        with self.db._connection() as conn:
            row = conn.execute("SELECT min_salary FROM jobs WHERE id = 'bf_job_script'").fetchone()
            self.assertIsNone(row["min_salary"])

        exit_code_apply = script_module.main(["--apply", "--limit", "5"])
        self.assertEqual(exit_code_apply, 0)
        with self.db._connection() as conn:
            row = conn.execute("SELECT min_salary, max_salary FROM jobs WHERE id = 'bf_job_script'").fetchone()
            self.assertEqual(row["min_salary"], 60000)
            self.assertEqual(row["max_salary"], 60000)

    @patch("main.get_storage")
    def test_run_backfill_pipeline_closes_storage_in_finally(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.get_unparsed_salary_jobs.return_value = []
        mock_get_storage.return_value = mock_storage

        run_backfill_pipeline(limit=5, dry_run=True)
        mock_storage.close.assert_called_once()

        # Verify close called even when error raised
        mock_storage.reset_mock()
        mock_storage.get_unparsed_salary_jobs.side_effect = RuntimeError("db error")
        with self.assertRaises(RuntimeError):
            run_backfill_pipeline(limit=5, dry_run=True)
        mock_storage.close.assert_called_once()

    @patch("scripts.backfill_salaries.get_storage")
    def test_scripts_backfill_salaries_closes_storage_in_finally(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.get_unparsed_salary_jobs.return_value = []
        mock_get_storage.return_value = mock_storage
        import scripts.backfill_salaries as script_module

        script_module.main(["--dry-run"])
        mock_storage.close.assert_called_once()

        # Verify close called even when error raised
        mock_storage.reset_mock()
        mock_storage.get_unparsed_salary_jobs.side_effect = RuntimeError("db error")
        with self.assertRaises(RuntimeError):
            script_module.main(["--dry-run"])
        mock_storage.close.assert_called_once()


class TestTelegramMarketBrief(unittest.TestCase):
    @patch("requests.post")
    def test_send_market_brief_formatting(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_post.return_value = mock_resp

        from src.notifier.telegram_notifier import TelegramNotifier

        notifier = TelegramNotifier(token="mock_token", chat_id="mock_chat")
        success = notifier.send_market_brief(
            top_pairs=[("Go", "PostgreSQL"), ("Python", "Docker")],
            generated_title="Real-Time PromptPay Reconciliation Gateway",
            role="Backend Engineer",
            total_analyzed=42,
        )

        self.assertTrue(success)
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertIn("Thailand Tech Market Intelligence Brief", payload["text"])
        self.assertIn("Go</b> + <b>PostgreSQL", payload["text"])
        self.assertIn("PromptPay Reconciliation Gateway", payload["text"])


class TestCIConfiguration(unittest.TestCase):
    def test_workflow_scraper_cron_enforces_pythonunbuffered(self):
        workflow_path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "scraper_cron.yml"
        self.assertTrue(workflow_path.exists(), f"Workflow file {workflow_path} not found")
        content = workflow_path.read_text(encoding="utf-8")
        self.assertIn('PYTHONUNBUFFERED: "1"', content)


class TestShutdownFlushing(unittest.TestCase):
    @patch("os._exit")
    @patch("logging.shutdown")
    @patch("sys.stderr.flush")
    @patch("sys.stdout.flush")
    def test_main_shutdown_flushes_stdout_and_stderr(
        self, mock_stdout_flush, mock_stderr_flush, mock_log_shutdown, mock_exit
    ):
        from main import flush_and_exit

        flush_and_exit(0)
        mock_stdout_flush.assert_called_once()
        mock_stderr_flush.assert_called_once()
        mock_log_shutdown.assert_called_once()
        mock_exit.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
