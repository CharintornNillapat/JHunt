# tests/test_analyzer.py
"""
Unit tests for role classification and market cluster analyzer.
Verifies English/Thai role detection, skill frequency aggregation,
co-occurrence matrix calculations, and role-based tech clustering.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from src.analyzer.cluster_analyzer import ClusterAnalyzer
from src.analyzer.role_classifier import StandardRole, classify_role
from src.extractor.schemas import ExtractedJob
from src.storage.db import DatabaseManager


class TestRoleClassifier(unittest.TestCase):
    def test_english_title_classification(self):
        cases = [
            ("Senior Backend Developer (Go)", StandardRole.BACKEND),
            ("Junior Python Backend Engineer", StandardRole.BACKEND),
            ("Frontend Developer (React/Next.js)", StandardRole.FRONTEND),
            ("Lead Frontend Engineer", StandardRole.FRONTEND),
            ("Full Stack Software Engineer", StandardRole.FULLSTACK),
            ("Full-Stack Developer", StandardRole.FULLSTACK),
            ("Data Engineer (Big Data & ETL)", StandardRole.DATA_ENGINEER),
            ("Senior Data Analyst", StandardRole.DATA_ENGINEER),
            ("DevOps Engineer", StandardRole.DEVOPS_CLOUD),
            ("Cloud Platform Engineer (AWS)", StandardRole.DEVOPS_CLOUD),
            ("AI Engineer (Computer Vision)", StandardRole.AI_ML),
            ("Machine Learning Researcher", StandardRole.AI_ML),
            ("Office Receptionist", StandardRole.OTHER),
        ]
        for title, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(classify_role(title), expected)

    def test_thai_title_classification(self):
        cases = [
            ("วิศวกรข้อมูล (Data Engineer)", StandardRole.DATA_ENGINEER),
            ("นักวิเคราะห์ข้อมูลอาวุโส", StandardRole.DATA_ENGINEER),
            ("นักวิทยาศาสตร์ข้อมูล", StandardRole.DATA_ENGINEER),
            ("วิศวกรปัญญาประดิษฐ์", StandardRole.AI_ML),
            ("วิศวกร AI", StandardRole.AI_ML),
            ("วิศวกรคลาวด์", StandardRole.DEVOPS_CLOUD),
            ("วิศวกรระบบ", StandardRole.DEVOPS_CLOUD),
            ("นักพัฒนาเว็บฟูลสแต็ก", StandardRole.FULLSTACK),
            ("โปรแกรมเมอร์", StandardRole.BACKEND),
            ("นักพัฒนาซอฟต์แวร์", StandardRole.BACKEND),
        ]
        for title, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(classify_role(title), expected)

    def test_fallback_classification_from_tech_stack(self):
        # Generic title: "Software Engineer"
        # 1. Fullstack (both FE and BE)
        job_fullstack = ExtractedJob(
            job_title="Software Engineer",
            company="Startup",
            must_have_skills=["React", "Node.js"],
            databases=["PostgreSQL"],
        )
        self.assertEqual(classify_role("Software Engineer", job_fullstack), StandardRole.FULLSTACK)

        # 2. AI / ML
        job_ai = ExtractedJob(
            job_title="Software Engineer",
            company="AI Lab",
            must_have_skills=["Python", "PyTorch"],
            tools=["OpenCV"],
        )
        self.assertEqual(classify_role("Software Engineer", job_ai), StandardRole.AI_ML)

        # 3. Data Engineer
        job_data = ExtractedJob(
            job_title="Software Engineer",
            company="Bank",
            must_have_skills=["Python", "Apache Spark"],
            tools=["Airflow"],
        )
        self.assertEqual(classify_role("Software Engineer", job_data), StandardRole.DATA_ENGINEER)


class TestClusterAnalyzer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jhunt_analyzer_test_")
        self.db_path = Path(self.test_dir) / "test_market.db"
        self.db = DatabaseManager(db_path=self.db_path)
        self.analyzer = ClusterAnalyzer(db=self.db)

        # Seed test jobs
        self._seed_data()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _seed_data(self):
        # Job 1: Backend (Go + PostgreSQL + Redis + Docker)
        self.db.save_job({
            "id": "j1",
            "title": "Backend Engineer",
            "company": "Co 1",
            "url": "https://1.com",
        })
        self.db.save_extracted_skills(
            "j1",
            ExtractedJob(
                job_title="Backend Engineer",
                company="Co 1",
                experience_level="Junior",
                must_have_skills=["Go", "Docker"],
                frameworks=[],
                databases=["PostgreSQL", "Redis"],
                cloud_infra=["Docker"],
                tools=["Git"],
            ),
        )

        # Job 2: Backend (Go + PostgreSQL + Docker)
        self.db.save_job({
            "id": "j2",
            "title": "Senior Go Developer",
            "company": "Co 2",
            "url": "https://2.com",
        })
        self.db.save_extracted_skills(
            "j2",
            ExtractedJob(
                job_title="Senior Go Developer",
                company="Co 2",
                experience_level="Senior",
                must_have_skills=["Go", "Docker"],
                frameworks=[],
                databases=["PostgreSQL"],
                cloud_infra=["Docker", "AWS"],
                tools=["Git"],
            ),
        )

        # Job 3: Frontend (React + TypeScript + Tailwind)
        self.db.save_job({
            "id": "j3",
            "title": "Frontend Developer",
            "company": "Co 3",
            "url": "https://3.com",
        })
        self.db.save_extracted_skills(
            "j3",
            ExtractedJob(
                job_title="Frontend Developer",
                company="Co 3",
                experience_level="Mid",
                must_have_skills=["TypeScript", "React"],
                frameworks=["React"],
                databases=[],
                cloud_infra=[],
                tools=["Git", "Webpack"],
            ),
        )

    def test_generate_market_report(self):
        report = self.analyzer.generate_market_report()
        self.assertEqual(report.total_jobs_analyzed, 3)

        # Verify top must_have skills
        must_have_names = [item.name for item in report.top_must_have_skills]
        self.assertIn("Go", must_have_names)
        self.assertIn("Docker", must_have_names)

        # Verify top databases
        db_names = [item.name for item in report.top_databases]
        self.assertEqual(db_names[0], "PostgreSQL")
        self.assertEqual(report.top_databases[0].count, 2)

        # Verify co-occurrences: ("Docker", "Go") should have count 2
        go_docker = next(
            (item for item in report.top_cooccurrences if set([item.tech_a, item.tech_b]) == {"Docker", "Go"}),
            None,
        )
        self.assertIsNotNone(go_docker)
        self.assertEqual(go_docker.count, 2)

        # Verify role clusters
        self.assertIn(StandardRole.BACKEND.value, report.role_clusters)
        backend_cluster = report.role_clusters[StandardRole.BACKEND.value]
        self.assertEqual(backend_cluster.sample_size, 2)
        self.assertIn("Go", backend_cluster.dominant_stack)
        self.assertIn("PostgreSQL", backend_cluster.dominant_stack)

        self.assertIn(StandardRole.FRONTEND.value, report.role_clusters)
        frontend_cluster = report.role_clusters[StandardRole.FRONTEND.value]
        self.assertEqual(frontend_cluster.sample_size, 1)
        self.assertIn("React", frontend_cluster.dominant_stack)

    def test_get_dominant_stack_for_role(self):
        backend_stack = self.analyzer.get_dominant_stack_for_role(StandardRole.BACKEND.value)
        self.assertIn("Go", backend_stack)
        self.assertIn("PostgreSQL", backend_stack)

        # Non-existent role in seed data falls back to standard defaults
        ai_stack = self.analyzer.get_dominant_stack_for_role(StandardRole.AI_ML.value)
        self.assertIn("PyTorch", ai_stack)


if __name__ == "__main__":
    unittest.main()
