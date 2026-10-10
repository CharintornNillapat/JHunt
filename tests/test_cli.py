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
            "gemini_model": "gemini-2.0-flash",
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


if __name__ == "__main__":
    unittest.main()
