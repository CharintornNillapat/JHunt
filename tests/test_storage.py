# tests/test_storage.py
"""
Unit tests for data contracts (Pydantic schemas) and SQLite persistence layer.
Verifies table creation, duplicate prevention, foreign keys, and co-occurrence aggregation.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from src.extractor.schemas import ExtractedJob, ProjectIdeaSpec
from src.storage.db import DatabaseManager


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
        self.assertTrue(self.db.job_exists("job_001"))

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


if __name__ == "__main__":
    unittest.main()
