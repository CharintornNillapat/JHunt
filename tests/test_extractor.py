# tests/test_extractor.py
"""
Unit tests for text sanitization and LLM extraction pipeline.
Verifies HTML stripping, boilerplate pruning, mock Gemini extraction,
exponential backoff retry behavior, and batch queue processing.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.extractor.schemas import ExtractedJob
from src.extractor.text_sanitizer import (
    build_sanitized_job_prompt,
    clean_html,
    strip_boilerplate,
)
from src.extractor.llm_extractor import (
    DailyQuotaExhaustedError,
    GeminiExtractor,
    is_daily_quota_exhausted,
    is_tech_job,
    process_unprocessed_jobs,
)
from src.storage.db import DatabaseManager


class TestTextSanitizer(unittest.TestCase):
    def test_clean_html_strips_tags_and_decodes_entities(self):
        raw = "<p>Join <strong>Acme Corp</strong> as a <em>Backend Developer</em>!<br/>Tech: Python &amp; Go &lt;Remote&gt;</p>"
        cleaned = clean_html(raw)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("<strong>", cleaned)
        self.assertIn("Acme Corp", cleaned)
        self.assertIn("Python & Go <Remote>", cleaned)

    def test_strip_boilerplate_removes_benefits_and_eeo(self):
        text = """
Requirements:
- 2+ years of Python & FastAPI experience
- Solid understanding of PostgreSQL and Docker

Benefits:
- Health insurance and dental coverage
- Provident fund 5%
- Free coffee and snacks

Equal Opportunity Employer:
All qualified applicants will receive consideration regardless of race or gender.
"""
        cleaned = strip_boilerplate(text)
        self.assertIn("Python & FastAPI", cleaned)
        self.assertIn("PostgreSQL and Docker", cleaned)
        self.assertNotIn("Health insurance", cleaned)
        self.assertNotIn("Provident fund", cleaned)
        self.assertNotIn("Equal Opportunity Employer", cleaned)

    def test_preserve_thai_requirements_while_stripping_perks(self):
        text = """
คุณสมบัติ:
- มีประสบการณ์พัฒนาโปรแกรมด้วย Python และ SQL อย่างน้อย 1 ปี
- สามารถใช้งาน Git และ Docker ได้

สวัสดิการ:
- กองทุนสำรองเลี้ยงชีพ
- ประกันสุขภาพกลุ่ม
- โบนัสประจำปี
"""
        cleaned = strip_boilerplate(text)
        self.assertIn("Python และ SQL", cleaned)
        self.assertIn("Git และ Docker", cleaned)
        self.assertNotIn("กองทุนสำรองเลี้ยงชีพ", cleaned)
        self.assertNotIn("ประกันสุขภาพกลุ่ม", cleaned)

    def test_build_sanitized_job_prompt(self):
        job = {
            "id": "123",
            "title": "Software Engineer (Python)",
            "company": "Siam Tech Co., Ltd.",
            "location": "Bangkok",
            "salary": "60,000 THB",
            "teaser": "<b>Fast-growing startup</b> looking for Python talent.<br>Health insurance included.",
            "bullet_points": [
                "Build scalable APIs with FastAPI and Redis",
                "Deploy on AWS with Kubernetes",
                "Provident fund 5%",
            ],
        }
        prompt = build_sanitized_job_prompt(job)
        self.assertIn("Title: Software Engineer (Python)", prompt)
        self.assertIn("FastAPI and Redis", prompt)
        self.assertIn("AWS with Kubernetes", prompt)
        self.assertNotIn("Health insurance", prompt)
        self.assertNotIn("Provident fund", prompt)


class TestGeminiExtractor(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.extractor = GeminiExtractor(
            api_key="fake-test-key",
            model="gemini-2.0-flash",
            rate_limit_delay=0.0,  # Fast tests
            client=self.mock_client,
        )

    def test_extract_job_success_via_parsed(self):
        expected_job = ExtractedJob(
            job_title="Backend Developer",
            company="Acme Corp",
            experience_level="Junior",
            must_have_skills=["Python", "FastAPI"],
            databases=["PostgreSQL"],
            cloud_infra=["Docker"],
        )
        mock_response = MagicMock()
        mock_response.parsed = expected_job
        self.mock_client.models.generate_content.return_value = mock_response

        result = self.extractor.extract_job(
            job_text="Backend Developer job description text",
            fallback_title="Fallback Title",
            fallback_company="Fallback Company",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.job_title, "Backend Developer")
        self.assertIn("Python", result.must_have_skills)

    def test_extract_job_success_via_json_text(self):
        json_output = """{
            "job_title": "Data Engineer",
            "company": "FinTech Bangkok",
            "experience_level": "Mid",
            "must_have_skills": ["Python", "Apache Spark"],
            "nice_to_have_skills": ["Kafka"],
            "frameworks": [],
            "databases": ["PostgreSQL", "BigQuery"],
            "cloud_infra": ["GCP"],
            "tools": ["Git", "Airflow"]
        }"""
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = json_output
        self.mock_client.models.generate_content.return_value = mock_response

        result = self.extractor.extract_job(job_text="Data engineer JD")
        self.assertIsNotNone(result)
        self.assertEqual(result.job_title, "Data Engineer")
        self.assertEqual(result.experience_level, "Mid")
        self.assertIn("BigQuery", result.databases)
        self.assertIn("Airflow", result.tools)

    def test_extract_job_retry_on_rate_limit(self):
        expected_job = ExtractedJob(
            job_title="AI Engineer",
            company="AI Lab",
            experience_level="Junior",
            must_have_skills=["Python", "PyTorch"],
        )
        success_response = MagicMock()
        success_response.parsed = expected_job

        # First call fails with 429 RESOURCE_EXHAUSTED, second succeeds
        self.mock_client.models.generate_content.side_effect = [
            Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded"),
            success_response,
        ]

        with patch("time.sleep"):  # Mock sleep so tests run instantly
            result = self.extractor.extract_job(job_text="AI job description")

        self.assertIsNotNone(result)
        self.assertEqual(result.job_title, "AI Engineer")
        self.assertEqual(self.mock_client.models.generate_content.call_count, 2)

    def test_extract_job_fails_safely_when_retries_exhausted(self):
        self.mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

        with patch("time.sleep"):
            result = self.extractor.extract_job(job_text="Any job text")

        self.assertIsNone(result)

    def test_batch_process_unprocessed_jobs(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_batch_test_")
        try:
            db_path = Path(temp_dir) / "market.db"
            db = DatabaseManager(db_path=db_path)

            # Insert two jobs
            db.save_job({
                "id": "batch_001",
                "title": "Backend Python Dev",
                "company": "Company A",
                "url": "https://example.com/1",
                "teaser": "Python and FastAPI backend role",
            })
            db.save_job({
                "id": "batch_002",
                "title": "Frontend React Dev",
                "company": "Company B",
                "url": "https://example.com/2",
                "teaser": "React and TypeScript role",
            })

            # Mock extractor to return ExtractedJob
            mock_extractor = MagicMock(spec=GeminiExtractor)
            mock_extractor.extract_job.side_effect = [
                ExtractedJob(
                    job_title="Backend Python Dev",
                    company="Company A",
                    experience_level="Junior",
                    must_have_skills=["Python", "FastAPI"],
                    databases=["PostgreSQL"],
                ),
                ExtractedJob(
                    job_title="Frontend React Dev",
                    company="Company B",
                    experience_level="Junior",
                    must_have_skills=["TypeScript", "React"],
                ),
            ]

            processed_count = process_unprocessed_jobs(db=db, extractor=mock_extractor)
            self.assertEqual(processed_count, 2)

            # Queue should now be empty
            unprocessed_remaining = db.get_unprocessed_jobs()
            self.assertEqual(len(unprocessed_remaining), 0)

            # Extracted skills should be saved in DB
            skills1 = db.get_extracted_skills("batch_001")
            self.assertIsNotNone(skills1)
            self.assertIn("Python", skills1.must_have_skills)

            skills2 = db.get_extracted_skills("batch_002")
            self.assertIsNotNone(skills2)
            self.assertIn("TypeScript", skills2.must_have_skills)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_model_override_avoids_gemini_2_5_flash(self):
        extractor = GeminiExtractor(api_key="fake_key", model_name="gemini-2.5-flash")
        self.assertEqual(extractor.model_name, "gemini-2.0-flash")

    def test_is_tech_job_heuristic(self):
        # Definite non-tech
        self.assertFalse(is_tech_job("Sales Executive", "Looking for sales rep"))
        self.assertFalse(is_tech_job("Senior Accountant", "Manage taxes and payroll"))
        self.assertFalse(is_tech_job("HR Specialist", "Recruitment and onboarding"))
        self.assertFalse(is_tech_job("Economic Research Analyst", "Macroeconomic analysis"))

        # Definite tech
        self.assertTrue(is_tech_job("Backend Python Engineer", "Build APIs with FastAPI"))
        self.assertTrue(is_tech_job("Frontend Developer", "React and Next.js"))
        self.assertTrue(is_tech_job("DevOps / Cloud Specialist", "Kubernetes and AWS"))
        self.assertTrue(is_tech_job("AI / ML Researcher", "Train deep learning models"))

        # Hybrid tech
        self.assertTrue(is_tech_job("Sales Engineer", "Technical pre-sales and architecture"))
        self.assertTrue(is_tech_job("Financial Data Analyst", "Analyze financial datasets with SQL"))

    def test_is_daily_quota_exhausted(self):
        self.assertTrue(is_daily_quota_exhausted(
            "429 Quota exceeded for quota metric 'GenerateRequestsPerDayPerProjectPerModel'"
        ))
        self.assertTrue(is_daily_quota_exhausted("Resource exhausted: please retry in 18h20m"))
        self.assertTrue(is_daily_quota_exhausted("Daily quota limit reached"))
        self.assertFalse(is_daily_quota_exhausted("429 RESOURCE_EXHAUSTED: Rate limit exceeded. Retry in 10s"))
        self.assertFalse(is_daily_quota_exhausted("503 Service Unavailable"))

    def test_extract_job_fails_fast_on_daily_quota(self):
        self.mock_client.models.generate_content.side_effect = Exception(
            "429 Quota exceeded for quota metric 'GenerateRequestsPerDayPerProjectPerModel'"
        )

        with self.assertRaises(DailyQuotaExhaustedError):
            self.extractor.extract_job(job_text="Backend Python Developer")

        # Must not retry when daily quota is exhausted
        self.assertEqual(self.mock_client.models.generate_content.call_count, 1)

    def test_batch_process_stops_gracefully_on_daily_quota(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_quota_test_")
        try:
            db_path = Path(temp_dir) / "market.db"
            db = DatabaseManager(db_path=db_path)

            db.save_job({"id": "q_001", "title": "Developer 1", "company": "Co 1", "url": "https://example.com/1"})
            db.save_job({"id": "q_002", "title": "Developer 2", "company": "Co 2", "url": "https://example.com/2"})
            db.save_job({"id": "q_003", "title": "Developer 3", "company": "Co 3", "url": "https://example.com/3"})

            mock_extractor = MagicMock(spec=GeminiExtractor)
            mock_extractor.extract_job.side_effect = [
                ExtractedJob(job_title="Developer 1", company="Co 1", experience_level="Mid", must_have_skills=["Go"]),
                DailyQuotaExhaustedError("Daily quota exhausted"),
            ]

            processed = process_unprocessed_jobs(db=db, extractor=mock_extractor)
            self.assertEqual(processed, 1)
            # Only first two jobs were attempted (1 succeeded, 2 aborted, 3 untouched)
            self.assertEqual(mock_extractor.extract_job.call_count, 2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_batch_process_skips_non_tech_jobs(self):
        temp_dir = tempfile.mkdtemp(prefix="jhunt_nontech_test_")
        try:
            db_path = Path(temp_dir) / "market.db"
            db = DatabaseManager(db_path=db_path)

            db.save_job({"id": "nt_001", "title": "Sales Representative", "company": "Sales Co", "url": "https://example.com/nt", "teaser": "Cold calls"})
            db.save_job({"id": "nt_002", "title": "Python Developer", "company": "Tech Co", "url": "https://example.com/t", "teaser": "Backend code"})

            mock_extractor = MagicMock(spec=GeminiExtractor)
            mock_extractor.extract_job.return_value = ExtractedJob(
                job_title="Python Developer",
                company="Tech Co",
                experience_level="Junior",
                must_have_skills=["Python"],
            )

            processed = process_unprocessed_jobs(db=db, extractor=mock_extractor)
            self.assertEqual(processed, 1)
            # Extractor only called for the tech job
            self.assertEqual(mock_extractor.extract_job.call_count, 1)

            # Both jobs should now be marked processed in DB
            remaining = db.get_unprocessed_jobs()
            self.assertEqual(len(remaining), 0)

            # Non-tech job is saved with experience_level 'Non-Tech'
            nt_skills = db.get_extracted_skills("nt_001")
            self.assertIsNotNone(nt_skills)
            self.assertEqual(nt_skills.experience_level, "Non-Tech")
            self.assertEqual(nt_skills.must_have_skills, [])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
