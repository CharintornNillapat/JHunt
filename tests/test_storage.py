# tests/test_storage.py
"""
Unit tests for data contracts (Pydantic schemas) and SQLite persistence layer.
Verifies table creation, duplicate prevention, foreign keys, and co-occurrence aggregation.
"""
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.extractor.schemas import ExtractedJob, FailureMode, ProjectIdeaSpec
from src.generator.markdown_exporter import MarkdownExporter
from src.storage import DatabaseManager, TursoClient, get_storage
from src.storage.schema import (
    ALL_INDEX_STATEMENTS,
    EXPECTED_INDEXES,
    SCHEMA_STATEMENTS,
    TABLE_STATEMENTS,
)


class TestDataContracts(unittest.TestCase):
    def test_extracted_job_schema_validation(self):
        job = ExtractedJob(
            job_title="Junior Backend Engineer",
            company="Tech Corp Bangkok",
            experience_level="Junior",
            must_have_skills=["Python", "FastAPI"],
            nice_to_have_skills=["Redis"],
            frameworks=["FastAPI"],
            databases=["PostgreSQL"],
            cloud_infra=["Docker", "AWS"],
            tools=["Git", "GitHub Actions"],
        )
        self.assertEqual(job.job_title, "Junior Backend Engineer")
        self.assertEqual(job.company, "Tech Corp Bangkok")
        self.assertIn("Python", job.all_tech_stack)
        self.assertIn("PostgreSQL", job.all_tech_stack)
        self.assertIn("Docker", job.all_tech_stack)

    def test_project_idea_spec_schema_validation(self):
        spec = ProjectIdeaSpec(
            title="Real-Time Food Delivery Dispatcher",
            domain_industry="Logistics & On-Demand Delivery",
            core_problem="Assign each order to exactly one rider when dispatchers act concurrently.",
            target_tech_stack=["Python", "FastAPI", "PostgreSQL", "Docker"],
            system_boundary="One FastAPI service and one PostgreSQL database.",
            walking_skeleton=["Create order", "Assign rider", "Reject stale assignment"],
            contracts="`POST /assignments` returns 200 or 409.",
            database_schema="PostGIS enabled PostgreSQL schema for locations and orders",
            failure_modes=[{"failure": "Two dispatchers assign one order", "recovery": "Version check; loser gets 409"}],
            verification=["pytest: two concurrent assignments yield 1 success and 1 conflict"],
            difficulty="Intermediate",
        )
        self.assertEqual(spec.difficulty, "Intermediate")
        self.assertEqual(len(spec.walking_skeleton), 3)
        self.assertIsInstance(spec.failure_modes[0], FailureMode)


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jhunt_test_")
        self.db_path = Path(self.test_dir) / "test_market.db"
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_database_initialization(self):
        self.assertTrue(self.db_path.exists())

    def test_database_indexes_exist_after_init_db(self):
        self.db.init_db()
        conn = sqlite3.connect(self.db_path)
        try:
            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        finally:
            conn.close()
        for idx in EXPECTED_INDEXES:
            self.assertIn(idx, indexes, f"Index {idx} should exist after init_db()")

    def test_skills_extracted_columns_and_index_parity(self):
        self.db.init_db()
        conn = sqlite3.connect(self.db_path)
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(skills_extracted)")}
        finally:
            conn.close()
        for expected_col in ("id", "job_id", "skill_name", "category", "experience_level"):
            self.assertIn(expected_col, cols, f"Column {expected_col} should exist in skills_extracted")

    def test_save_job_and_duplicate_prevention(self):
        job_data = {
            "id": "job_001",
            "title": "Data Engineer",
            "company": "Bangkok Bank Tech",
            "url": "https://th.jobsdb.com/job/job_001",
            "location": "Bangkok",
            "salary": "50,000 - 70,000 THB",
            "work_type": "Full-time",
            "teaser": "Seeking Python and Spark engineer",
            "bullet_points": ["Python", "Spark", "SQL"],
            "listing_date": "2026-10-10",
        }

        # First insert -> True
        inserted = self.db.save_job(job_data)
        self.assertTrue(inserted)
        unprocessed = self.db.get_unprocessed_jobs()
        self.assertEqual(len(unprocessed), 1)
        self.assertEqual(unprocessed[0]["id"], "job_001")

        # Verify parsed salary columns were persisted correctly
        with self.db._connection() as conn:
            row = conn.execute("SELECT min_salary, max_salary, currency FROM jobs WHERE id = 'job_001'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["min_salary"], 50000)
            self.assertEqual(row["max_salary"], 70000)
            self.assertEqual(row["currency"], "THB")

        # Duplicate insert -> False
        second_insert = self.db.save_job(job_data)
        self.assertFalse(second_insert)

    def test_database_manager_self_healing_migration_for_salary_columns(self):
        # Create a database table missing min_salary, max_salary, and currency
        custom_db_path = Path(self.test_dir) / "legacy_salary_test.db"
        conn = sqlite3.connect(str(custom_db_path))
        conn.execute("""
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                url TEXT NOT NULL,
                location TEXT,
                salary TEXT,
                work_type TEXT,
                raw_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.close()

        # DatabaseManager initialization triggers self-healing schema migration
        mgr = DatabaseManager(db_path=custom_db_path)
        with mgr._connection() as c:
            cols = {row["name"] for row in c.execute("PRAGMA table_info(jobs)")}
            self.assertIn("min_salary", cols)
            self.assertIn("max_salary", cols)
            self.assertIn("currency", cols)


    def test_get_unprocessed_jobs(self):
        job1 = {
            "id": "job_101",
            "title": "Python Developer",
            "company": "Company A",
            "url": "https://example.com/101",
        }
        job2 = {
            "id": "job_102",
            "title": "Go Backend Developer",
            "company": "Company B",
            "url": "https://example.com/102",
        }
        self.db.save_job(job1)
        self.db.save_job(job2)

        unprocessed = self.db.get_unprocessed_jobs()
        self.assertEqual(len(unprocessed), 2)

        # Extract skills for job1
        extracted = ExtractedJob(
            job_title="Python Developer",
            company="Company A",
            experience_level="Junior",
            must_have_skills=["Python", "FastAPI"],
            databases=["PostgreSQL"],
            cloud_infra=["Docker"],
        )
        self.db.save_extracted_skills("job_101", extracted)

        # Only job2 should remain unprocessed
        remaining = self.db.get_unprocessed_jobs()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["id"], "job_102")

    def test_extracted_skills_persistence_and_retrieval(self):
        job = {
            "id": "job_201",
            "title": "Fullstack Developer",
            "company": "Agoda",
            "url": "https://example.com/201",
        }
        self.db.save_job(job)

        extracted = ExtractedJob(
            job_title="Fullstack Developer",
            company="Agoda",
            experience_level="Mid",
            must_have_skills=["TypeScript", "React", "Python"],
            frameworks=["React", "FastAPI"],
            databases=["PostgreSQL", "Redis"],
            cloud_infra=["Docker", "Kubernetes"],
            tools=["Git", "Kafka"],
        )
        self.db.save_extracted_skills("job_201", extracted)

        retrieved = self.db.get_extracted_skills("job_201")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_title, "Fullstack Developer")
        self.assertEqual(retrieved.company, "Agoda")
        self.assertIn("TypeScript", retrieved.must_have_skills)
        self.assertIn("PostgreSQL", retrieved.databases)
        self.assertIn("Kafka", retrieved.tools)

    def test_skill_cooccurrences(self):
        job1 = {"id": "j1", "title": "Dev 1", "company": "Co 1", "url": "https://1.com"}
        job2 = {"id": "j2", "title": "Dev 2", "company": "Co 2", "url": "https://2.com"}
        self.db.save_job(job1)
        self.db.save_job(job2)

        self.db.save_extracted_skills(
            "j1",
            ExtractedJob(
                job_title="Dev 1",
                company="Co 1",
                must_have_skills=["Python", "Docker"],
                databases=["PostgreSQL"],
            ),
        )
        self.db.save_extracted_skills(
            "j2",
            ExtractedJob(
                job_title="Dev 2",
                company="Co 2",
                must_have_skills=["Python", "Docker"],
                databases=["MongoDB"],
            ),
        )

        cooccurrences = self.db.get_top_skill_cooccurrences(min_count=1)
        # Python and Docker appear together in both jobs (count = 2)
        top_pair = next(
            (item for item in cooccurrences if set([item["tech_a"], item["tech_b"]]) == {"Python", "Docker"}),
            None,
        )
        self.assertIsNotNone(top_pair)
        self.assertEqual(top_pair["count"], 2)

    def test_record_generated_project(self):
        project_id = self.db.record_generated_project(
            title="E-Commerce Payment Orchestrator",
            role="Backend Engineer",
            tech_stack=["Go", "PostgreSQL", "Redis"],
            difficulty="Intermediate",
            domain="FinTech",
            spec_markdown="# E-Commerce Payment Orchestrator",
        )
        self.assertGreater(project_id, 0)

        projects = self.db.get_generated_projects(limit=10)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["title"], "E-Commerce Payment Orchestrator")
        self.assertEqual(projects[0]["domain"], "FinTech")
        self.assertTrue(self.db.has_generated_project("E-Commerce Payment Orchestrator"))
        self.assertFalse(self.db.has_generated_project("Something Else"))

    def test_local_schema_matches_shared_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(generated_projects)")]
        self.assertEqual(
            cols,
            ["id", "title", "role", "difficulty", "domain", "tech_stack", "spec_markdown", "created_at"],
        )


class TestImportGraph(unittest.TestCase):
    def test_storage_imports_standalone(self):
        # storage.db -> extractor -> llm_extractor -> storage.db was a cycle that only
        # surfaced when storage was imported first; a fresh interpreter catches it.
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-c", "import src.storage.db"],
            cwd=repo_root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestLegacyMigration(unittest.TestCase):
    def test_legacy_generated_projects_table_is_rebuilt_with_data(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_migrate_test_")
        try:
            db_path = Path(temp_dir) / "market.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE generated_projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        role TEXT NOT NULL,
                        domain_industry TEXT,
                        tech_stack TEXT,
                        file_path TEXT NOT NULL,
                        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute(
                    "INSERT INTO generated_projects (title, role, domain_industry, tech_stack, file_path) "
                    "VALUES ('Old Blueprint', 'Backend Engineer', 'FinTech', '[\"Go\"]', 'C:/old.md')"
                )
            conn.close()

            db = DatabaseManager(db_path=db_path)
            DatabaseManager(db_path=db_path)  # second open must be a no-op

            projects = db.get_generated_projects()
            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0]["title"], "Old Blueprint")
            self.assertEqual(projects[0]["domain"], "FinTech")
            self.assertNotIn("file_path", projects[0])
            db.record_generated_project(title="New", role="Backend Engineer", tech_stack=["Go"])
            self.assertEqual(len(db.get_generated_projects()), 2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestTursoClient(unittest.TestCase):
    def test_missing_credentials_graceful_fallback(self):
        with patch.dict("os.environ", {}, clear=True):
            turso = TursoClient()
            self.assertFalse(turso.is_available)
            self.assertIsNone(turso.client)

            # Operations return safe defaults without error
            self.assertEqual(turso.sync_jobs([{"id": "j1", "title": "Dev"}]), 0)
            self.assertEqual(turso.sync_extracted_skills({"job_id": "j1"}), 0)
            self.assertFalse(turso.sync_blueprint(
                title="Test Blueprint",
                role="Backend Engineer",
                difficulty="Intermediate",
                domain="FinTech",
                tech_stack=["Go", "Redis"],
                spec_markdown="# Test",
            ))

    def test_turso_url_protocol_normalization(self):
        # 1. Normalize libsql:// to https://
        mock_client = MagicMock()
        turso = TursoClient(
            database_url="libsql://jhunt-db-test.aws-ap-northeast-1.turso.io",
            auth_token="test-token",
            client=mock_client,
        )
        self.assertEqual(turso.database_url, "https://jhunt-db-test.aws-ap-northeast-1.turso.io")
        self.assertEqual(turso.db_url, "https://jhunt-db-test.aws-ap-northeast-1.turso.io")
        self.assertEqual(turso.auth_token, "test-token")

        # 2. Strip quotes and whitespace
        turso2 = TursoClient(
            database_url='  "libsql://jhunt-quoted.turso.io"  ',
            auth_token="  'token-with-quotes'  ",
            client=mock_client,
        )
        self.assertEqual(turso2.database_url, "https://jhunt-quoted.turso.io")
        self.assertEqual(turso2.auth_token, "token-with-quotes")

    def test_table_initialization_with_mock_client(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        self.assertTrue(turso.is_available)

        # Tables and indexes are both batched
        mock_client.batch.assert_any_call(list(TABLE_STATEMENTS))
        mock_client.batch.assert_any_call(list(ALL_INDEX_STATEMENTS))

    def test_turso_indexes_exist_after_init_schema(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        mock_client.batch.reset_mock()

        turso.init_schema()
        mock_client.batch.assert_any_call(list(TABLE_STATEMENTS))
        mock_client.batch.assert_any_call(list(ALL_INDEX_STATEMENTS))

        index_calls = [c[0][0] for c in mock_client.batch.call_args_list if c[0] and c[0][0] == list(ALL_INDEX_STATEMENTS)]
        self.assertTrue(len(index_calls) > 0)
        batched_statements = index_calls[0]
        for idx in EXPECTED_INDEXES:
            matching = [s for s in batched_statements if isinstance(s, str) and idx in s]
            self.assertTrue(len(matching) > 0, f"Expected {idx} in Turso init_schema batch")

    def test_turso_init_schema_creates_all_expected_indexes(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_turso_idx_test_")
        try:
            db_path = Path(temp_dir) / "sim_turso.db"
            conn = sqlite3.connect(db_path)

            class SimulatedLibsqlClient:
                def __init__(self, connection):
                    self.conn = connection

                def execute(self, stmt, params=None):
                    if params is not None:
                        return self.conn.execute(stmt, params)
                    return self.conn.execute(stmt)

                def batch(self, stmts):
                    for stmt in stmts:
                        if isinstance(stmt, str):
                            self.conn.execute(stmt)
                        else:
                            self.conn.execute(stmt[0], stmt[1])

                def close(self):
                    self.conn.close()

            sim_client = SimulatedLibsqlClient(conn)
            turso = TursoClient(client=sim_client)
            turso.init_schema()

            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            for idx in EXPECTED_INDEXES:
                self.assertIn(idx, indexes, f"Index {idx} should exist after Turso init_schema")
            conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_turso_legacy_column_migration_renames_skill_to_skill_name(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_turso_mig_test_")
        try:
            db_path = Path(temp_dir) / "legacy_turso.db"
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE skills_extracted (
                    job_id TEXT PRIMARY KEY,
                    skill TEXT,
                    experience_level TEXT,
                    must_have_skills TEXT,
                    nice_to_have_skills TEXT,
                    frameworks TEXT,
                    databases TEXT,
                    cloud_infra TEXT,
                    tools TEXT,
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

            class SimulatedLibsqlClient:
                def __init__(self, connection):
                    self.conn = connection

                def execute(self, stmt, params=None):
                    if params is not None:
                        cur = self.conn.execute(stmt, params)
                    else:
                        cur = self.conn.execute(stmt)
                    self.conn.commit()
                    return cur

                def batch(self, stmts):
                    for stmt in stmts:
                        if isinstance(stmt, str):
                            self.conn.execute(stmt)
                        else:
                            self.conn.execute(stmt[0], stmt[1])
                    self.conn.commit()

                def close(self):
                    self.conn.close()

            sim_client = SimulatedLibsqlClient(conn)
            turso = TursoClient(client=sim_client)
            turso.init_schema()

            cols = {row[1] for row in conn.execute("PRAGMA table_info(skills_extracted)")}
            self.assertIn("skill_name", cols, "Column 'skill' should be renamed to 'skill_name'")
            self.assertNotIn("skill", cols, "Legacy column 'skill' should no longer exist")
            self.assertIn("category", cols, "Column 'category' should be added")

            # Check that idx_skills_name exists on the migrated table
            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            self.assertIn("idx_skills_name", indexes)
            conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_turso_legacy_column_migration_with_mock(self):
        mock_client = MagicMock()

        class MockRow:
            def __init__(self, name):
                self._name = name

            def __getitem__(self, item):
                if item == "name":
                    return self._name
                raise KeyError(item)

        class MockPRAGMAResult:
            rows = [MockRow("job_id"), MockRow("skill"), MockRow("experience_level")]

        def execute_side_effect(sql, params=None):
            if "PRAGMA table_info" in sql:
                return MockPRAGMAResult()
            return MagicMock()

        mock_client.execute.side_effect = execute_side_effect

        turso = TursoClient(client=mock_client)
        mock_client.execute.assert_any_call("ALTER TABLE skills_extracted RENAME COLUMN skill TO skill_name;")
        mock_client.execute.assert_any_call("ALTER TABLE skills_extracted ADD COLUMN category TEXT;")

    def test_turso_missing_skill_name_added_when_no_legacy_skill(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_turso_add_col_test_")
        try:
            db_path = Path(temp_dir) / "no_skill_col.db"
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE skills_extracted (
                    job_id TEXT PRIMARY KEY,
                    experience_level TEXT
                );
            """)
            conn.commit()

            class SimulatedLibsqlClient:
                def __init__(self, connection):
                    self.conn = connection

                def execute(self, stmt, params=None):
                    if params is not None:
                        cur = self.conn.execute(stmt, params)
                    else:
                        cur = self.conn.execute(stmt)
                    self.conn.commit()
                    return cur

                def batch(self, stmts):
                    for stmt in stmts:
                        if isinstance(stmt, str):
                            self.conn.execute(stmt)
                        else:
                            self.conn.execute(stmt[0], stmt[1])
                    self.conn.commit()

                def close(self):
                    self.conn.close()

            sim_client = SimulatedLibsqlClient(conn)
            turso = TursoClient(client=sim_client)
            turso.init_schema()

            cols = {row[1] for row in conn.execute("PRAGMA table_info(skills_extracted)")}
            self.assertIn("skill_name", cols)
            self.assertIn("category", cols)
            conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_turso_non_blocking_index_creation_errors(self):
        mock_client = MagicMock()

        def batch_side_effect(stmts):
            if any("CREATE INDEX" in s for s in stmts if isinstance(s, str)):
                raise Exception("batch index error: simulated lock")
            return None

        mock_client.batch.side_effect = batch_side_effect
        mock_client.execute.side_effect = Exception("single index error: simulated error")

        # TursoClient initialization should NOT raise and should remain available!
        turso = TursoClient(client=mock_client)
        self.assertTrue(turso.is_available, "Turso client should remain available even if index creation fails")

    def test_malformed_url_falls_back_instead_of_raising(self):
        with patch("libsql_client.create_client_sync", side_effect=ValueError("unsupported URL scheme")):
            turso = TursoClient(database_url="not-a-url", auth_token="x")
        self.assertFalse(turso.is_available)
        self.assertIsNone(turso.client)

    def test_has_blueprint(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        mock_client.execute.return_value.rows = [(1,)]
        self.assertTrue(turso.has_blueprint("Idempotent PromptPay Webhook Processor"))
        mock_client.execute.return_value.rows = []
        self.assertFalse(turso.has_blueprint("Unknown"))
        mock_client.execute.side_effect = Exception("network down")
        self.assertFalse(turso.has_blueprint("Unknown"))

    def test_sync_jobs_with_mock(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        mock_client.execute.reset_mock()

        jobs = [
            {
                "id": "job_cloud_01",
                "title": "Cloud Engineer",
                "company": "True Digital",
                "url": "https://example.com/cloud",
                "location": "Bangkok",
                "salary": "80,000 THB",
                "work_type": "Full-time",
                "teaser": "AWS and Terraform engineer",
                "bullet_points": ["AWS", "Terraform"],
                "listing_date": "2026-10-10",
            },
            {
                "id": "job_cloud_02",
                "title": "Backend Go Developer",
                "company": "Bitkub",
                "url": "https://example.com/go",
            },
        ]

        mock_client.batch.reset_mock()
        synced = turso.sync_jobs(jobs)
        self.assertEqual(synced, 2)
        # One round trip for the whole scrape, not one per job
        mock_client.batch.assert_called_once()
        mock_client.execute.assert_not_called()

        stmts = mock_client.batch.call_args[0][0]
        self.assertEqual(len(stmts), 2)
        sql, params = stmts[0]
        self.assertIn("INSERT OR IGNORE INTO jobs", sql)
        self.assertEqual(params[0], "job_cloud_01")
        self.assertEqual(params[1], "Cloud Engineer")
        self.assertEqual(params[2], "True Digital")
        self.assertEqual(params[10], 80000)
        self.assertEqual(params[11], 80000)
        self.assertEqual(params[12], "THB")

        sql2, params2 = stmts[1]
        self.assertEqual(params2[0], "job_cloud_02")
        self.assertIsNone(params2[10])
        self.assertIsNone(params2[11])
        self.assertEqual(params2[12], "THB")

    def test_turso_migrate_jobs_schema_adds_missing_columns(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)

        class MockTableInfoResult:
            rows = [
                {"name": "id"},
                {"name": "title"},
                {"name": "company"},
                {"name": "url"},
                {"name": "salary"},
            ]

        mock_client.execute.return_value = MockTableInfoResult()
        turso._migrate_jobs_schema()

        executed_sqls = [call[0][0] for call in mock_client.execute.call_args_list if call[0]]
        self.assertTrue(any("ADD COLUMN min_salary" in sql for sql in executed_sqls))
        self.assertTrue(any("ADD COLUMN max_salary" in sql for sql in executed_sqls))
        self.assertTrue(any("ADD COLUMN currency" in sql for sql in executed_sqls))

    def test_sync_jobs_batch_failure_returns_zero(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        mock_client.batch.side_effect = Exception("network down")
        self.assertEqual(turso.sync_jobs([{"id": "j1", "title": "Dev", "company": "Co", "url": "u"}]), 0)

    def test_sync_extracted_skills_with_mock(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        mock_client.execute.reset_mock()

        # 1. Sync via dict with ExtractedJob
        extracted = ExtractedJob(
            job_title="Backend Go Developer",
            company="Bitkub",
            experience_level="Mid",
            must_have_skills=["Go", "gRPC"],
            databases=["PostgreSQL", "Redis"],
            cloud_infra=["Docker", "Kubernetes"],
            tools=["Git", "Kafka"],
        )

        mock_client.batch.reset_mock()
        synced_single = turso.sync_extracted_skills({
            "job_id": "job_cloud_02",
            "extracted": extracted,
        })
        self.assertEqual(synced_single, 1)

        sql, params = mock_client.batch.call_args[0][0][0]
        self.assertIn("INSERT INTO skills_extracted", sql)
        self.assertEqual(params[0], "job_cloud_02")
        self.assertEqual(params[1], "Mid")
        self.assertIn("Go", params[2])
        self.assertIn("PostgreSQL", params[5])

        # 2. Sync via list of raw skill dicts
        mock_client.batch.reset_mock()
        raw_skills = [
            {
                "job_id": "job_cloud_03",
                "experience_level": "Senior",
                "must_have_skills": ["Python", "FastAPI"],
                "nice_to_have_skills": ["Redis"],
                "frameworks": ["FastAPI"],
                "databases": ["PostgreSQL"],
                "cloud_infra": ["AWS"],
                "tools": ["Git"],
            }
        ]
        synced_batch = turso.sync_extracted_skills(raw_skills)
        self.assertEqual(synced_batch, 1)
        mock_client.batch.assert_called_once()

    def test_sync_blueprint_with_mock(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        mock_client.execute.reset_mock()

        success = turso.sync_blueprint(
            title="Real-Time Payment Gateway & Ledger",
            role="Backend Engineer",
            difficulty="Advanced",
            domain="FinTech & Digital Banking",
            tech_stack=["Go", "PostgreSQL", "Kafka", "Redis"],
            spec_markdown="# System Blueprint\nArchitecture details...",
        )
        self.assertTrue(success)
        mock_client.execute.assert_called_once()

        sql, params = mock_client.execute.call_args[0]
        self.assertIn("INSERT INTO generated_projects", sql)
        self.assertEqual(params[0], "Real-Time Payment Gateway & Ledger")
        self.assertEqual(params[1], "Backend Engineer")
        self.assertEqual(params[2], "Advanced")
        self.assertEqual(params[3], "FinTech & Digital Banking")
        self.assertIn("Go", params[4])
        self.assertIn("System Blueprint", params[5])

    def test_turso_client_close(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)
        self.assertTrue(turso.is_available)
        turso.close()
        self.assertFalse(turso.is_available)
        self.assertIsNone(turso.client)
        mock_client.close.assert_called_once()

    def test_turso_get_unprocessed_jobs_with_mock(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)

        class MockResult:
            columns = ("id", "title", "company", "url", "raw_content")
            rows = [
                ("j1", "Backend Dev", "Acme", "https://example.com/1", '{"teaser": "Go role"}'),
            ]

        mock_client.execute.return_value = MockResult()
        unprocessed = turso.get_unprocessed_jobs(limit=10)
        self.assertEqual(len(unprocessed), 1)
        self.assertEqual(unprocessed[0]["id"], "j1")
        self.assertEqual(unprocessed[0]["teaser"], "Go role")

    def test_turso_get_all_extracted_skills_with_mock(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)

        class MockSkillsResult:
            columns = (
                "job_id", "title", "company", "experience_level",
                "must_have_skills", "nice_to_have_skills", "frameworks",
                "databases", "cloud_infra", "tools",
            )
            rows = [
                (
                    "j1", "Backend Dev", "Acme", "Mid",
                    '["Go", "Docker"]', '["Redis"]', '["Gin"]',
                    '["PostgreSQL"]', '["AWS"]', '["Git"]',
                )
            ]

        mock_client.execute.return_value = MockSkillsResult()
        skills = turso.get_all_extracted_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].job_title, "Backend Dev")
        self.assertIn("Go", skills[0].must_have_skills)
        self.assertIn("PostgreSQL", skills[0].databases)

    def test_turso_skill_cooccurrences_with_mock(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)

        class MockSkillsResult:
            columns = (
                "job_id", "title", "company", "experience_level",
                "must_have_skills", "nice_to_have_skills", "frameworks",
                "databases", "cloud_infra", "tools",
            )
            rows = [
                ("j1", "Dev 1", "Co", "Mid", '["Python"]', '[]', '["FastAPI"]', '["PostgreSQL"]', '[]', '[]'),
                ("j2", "Dev 2", "Co", "Mid", '["Python"]', '[]', '["FastAPI"]', '[]', '[]', '[]'),
            ]

        mock_client.execute.return_value = MockSkillsResult()
        pairs = turso.get_top_skill_cooccurrences()
        self.assertTrue(len(pairs) > 0)
        top = pairs[0]
        self.assertEqual(top["count"], 2)

    def test_turso_record_and_get_generated_projects(self):
        mock_client = MagicMock()
        turso = TursoClient(client=mock_client)

        row_id = turso.record_generated_project(
            title="New Spec",
            role="Backend Engineer",
            tech_stack=["Python"],
            spec_markdown="# Spec",
        )
        self.assertEqual(row_id, 1)

        mock_client.execute.return_value.rows = [(1,)]
        self.assertTrue(turso.has_generated_project("New Spec"))

        class MockProjResult:
            columns = ("id", "title", "role", "created_at")
            rows = [(1, "New Spec", "Backend Engineer", "2026-10-11")]

        mock_client.execute.return_value = MockProjResult()
        projects = turso.get_generated_projects(limit=5)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["title"], "New Spec")


class TestStorageFactory(unittest.TestCase):
    def test_get_storage_falls_back_to_database_manager(self):
        with patch.dict("os.environ", {}, clear=True):
            storage = get_storage()
            self.assertIsInstance(storage, DatabaseManager)

    def test_get_storage_force_sqlite(self):
        with patch.dict("os.environ", {"TURSO_DATABASE_URL": "https://test.turso.io", "TURSO_AUTH_TOKEN": "token"}):
            storage = get_storage(force_sqlite=True, db_path=":memory:")
            self.assertIsInstance(storage, DatabaseManager)

    @patch("src.storage.TursoClient")
    def test_get_storage_selects_turso_when_available(self, mock_turso_cls):
        mock_turso = MagicMock()
        mock_turso.is_available = True
        mock_turso_cls.return_value = mock_turso

        storage = get_storage(database_url="https://mock.turso.io", auth_token="token")
        self.assertEqual(storage, mock_turso)

    def test_get_storage_require_cloud_explicit_raises_when_no_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                get_storage(require_cloud=True)
            self.assertIn("JHUNT_REQUIRE_TURSO is set but Turso is unavailable", str(ctx.exception))

    def test_get_storage_require_cloud_env_var_raises_when_no_credentials(self):
        with patch.dict("os.environ", {"JHUNT_REQUIRE_TURSO": "1"}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                get_storage()
            self.assertIn("JHUNT_REQUIRE_TURSO is set but Turso is unavailable", str(ctx.exception))

    def test_get_storage_require_cloud_env_var_truthy_variations(self):
        for val in ("true", "TRUE", "yes", "on", "1"):
            with self.subTest(val=val):
                with patch.dict("os.environ", {"JHUNT_REQUIRE_TURSO": val}, clear=True):
                    with self.assertRaises(RuntimeError):
                        get_storage()

    def test_get_storage_require_cloud_falsy_env_var_falls_back(self):
        for val in ("0", "false", "no", "off", "", "   "):
            with self.subTest(val=val):
                with patch.dict("os.environ", {"JHUNT_REQUIRE_TURSO": val}, clear=True):
                    storage = get_storage()
                    self.assertIsInstance(storage, DatabaseManager)

    def test_get_storage_require_cloud_force_sqlite_raises(self):
        with patch.dict("os.environ", {"TURSO_DATABASE_URL": "https://test.turso.io", "TURSO_AUTH_TOKEN": "token"}):
            with self.assertRaises(RuntimeError):
                get_storage(force_sqlite=True, require_cloud=True)

    @patch("src.storage.TursoClient")
    def test_get_storage_require_cloud_returns_turso_when_available(self, mock_turso_cls):
        mock_turso = MagicMock()
        mock_turso.is_available = True
        mock_turso_cls.return_value = mock_turso

        storage = get_storage(database_url="https://mock.turso.io", auth_token="token", require_cloud=True)
        self.assertEqual(storage, mock_turso)

    @patch("src.storage.TursoClient")
    def test_get_storage_require_cloud_raises_when_turso_client_unavailable(self, mock_turso_cls):
        mock_turso = MagicMock()
        mock_turso.is_available = False
        mock_turso_cls.return_value = mock_turso

        with self.assertRaises(RuntimeError):
            get_storage(database_url="https://mock.turso.io", auth_token="token", require_cloud=True)



class TestTursoExporterIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jhunt_turso_export_")
        self.export_dir = Path(self.temp_dir) / "ideas"
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_exporter_triggers_turso_sync_blueprint(self):
        mock_turso = MagicMock()
        mock_turso.sync_blueprint.return_value = True

        exporter = MarkdownExporter(
            export_dir=self.export_dir,
            db=self.db,
            turso=mock_turso,
        )

        spec = ProjectIdeaSpec(
            title="Flash Sale Inventory Locking Engine",
            domain_industry="E-Commerce",
            core_problem="Never oversell stock when many buyers reserve the last items at once.",
            target_tech_stack=["Python", "FastAPI", "Redis", "PostgreSQL"],
            system_boundary="One FastAPI service, PostgreSQL, and Redis for reservations.",
            walking_skeleton=["Reserve an item", "Expire unpaid reservations"],
            contracts="`POST /reservations` returns 201 or 409.",
            database_schema="PostgreSQL schemas for items and orders",
            failure_modes=[{"failure": "Concurrent reservations", "recovery": "Conditional decrement; loser gets 409"}],
            verification=["Locust: reserved count never exceeds stock"],
            difficulty="Intermediate",
        )

        file_path = exporter.export(spec=spec, target_role="Backend Engineer")
        self.assertTrue(file_path.exists())

        # Verify turso.sync_blueprint was called with correct parameters
        mock_turso.sync_blueprint.assert_called_once()
        call_kwargs = mock_turso.sync_blueprint.call_args[1]
        self.assertEqual(call_kwargs["title"], "Flash Sale Inventory Locking Engine")
        self.assertEqual(call_kwargs["role"], "Backend Engineer")
        self.assertEqual(call_kwargs["difficulty"], "Intermediate")
        self.assertEqual(call_kwargs["domain"], "E-Commerce")
        self.assertIn("FastAPI", call_kwargs["tech_stack"])
        self.assertIn("Flash Sale Inventory Locking Engine", call_kwargs["spec_markdown"])


if __name__ == "__main__":
    unittest.main()

