# tests/test_storage.py
"""
Unit tests for data contracts (Pydantic schemas) and SQLite persistence layer.
Verifies table creation, duplicate prevention, foreign keys, and co-occurrence aggregation.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.extractor.schemas import ExtractedJob, ProjectIdeaSpec
from src.generator.markdown_exporter import MarkdownExporter
from src.storage.db import DatabaseManager
from src.storage.turso_client import TursoClient


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
            target_tech_stack=["Python", "FastAPI", "Redis", "PostgreSQL", "Docker"],
            architecture_overview="Microservice architecture with event streaming and geospatial indexing",
            core_features=["Driver matching", "Geofencing", "WebSocket updates"],
            database_schema="PostGIS enabled PostgreSQL schema for locations and orders",
            engineering_challenges=["High concurrent location updates", "Sub-second dispatching"],
            difficulty="Intermediate",
        )
        self.assertEqual(spec.difficulty, "Intermediate")
        self.assertEqual(len(spec.core_features), 3)


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jhunt_test_")
        self.db_path = Path(self.test_dir) / "test_market.db"
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_database_initialization(self):
        self.assertTrue(self.db_path.exists())

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

        # Duplicate insert -> False
        second_insert = self.db.save_job(job_data)
        self.assertFalse(second_insert)


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
            file_path=r"C:\Users\MRmar\Desktop\Ideas\2026-10-10_backend_payment-orchestrator.md",
            domain_industry="FinTech",
        )
        self.assertGreater(project_id, 0)

        projects = self.db.get_generated_projects(limit=10)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["title"], "E-Commerce Payment Orchestrator")


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

        # Ensure table creation queries were executed
        executed_sqls = [call[0][0] for call in mock_client.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS jobs" in sql for sql in executed_sqls))
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS skills_extracted" in sql for sql in executed_sqls))
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS generated_projects" in sql for sql in executed_sqls))

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

        synced = turso.sync_jobs(jobs)
        self.assertEqual(synced, 2)
        self.assertEqual(mock_client.execute.call_count, 2)

        # Inspect first executed call
        first_call = mock_client.execute.call_args_list[0]
        sql, params = first_call[0][0], first_call[0][1]
        self.assertIn("INSERT OR IGNORE INTO jobs", sql)
        self.assertEqual(params[0], "job_cloud_01")
        self.assertEqual(params[1], "Cloud Engineer")
        self.assertEqual(params[2], "True Digital")

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

        synced_single = turso.sync_extracted_skills({
            "job_id": "job_cloud_02",
            "extracted": extracted,
        })
        self.assertEqual(synced_single, 1)

        call_args = mock_client.execute.call_args[0]
        sql, params = call_args[0], call_args[1]
        self.assertIn("INSERT INTO skills_extracted", sql)
        self.assertEqual(params[0], "job_cloud_02")
        self.assertEqual(params[1], "Mid")
        self.assertIn("Go", params[2])
        self.assertIn("PostgreSQL", params[5])

        # 2. Sync via list of raw skill dicts
        mock_client.execute.reset_mock()
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
        self.assertEqual(mock_client.execute.call_count, 1)

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
            target_tech_stack=["Python", "FastAPI", "Redis", "PostgreSQL"],
            architecture_overview="Distributed locking architecture with Redis Redlock and outbox pattern",
            core_features=["Inventory allocation", "Order queue", "Distributed lock"],
            database_schema="PostgreSQL schemas for items and orders",
            engineering_challenges=["High concurrency race conditions", "Cache stampede"],
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

