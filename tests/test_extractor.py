# tests/test_extractor.py
"""
Unit tests for text sanitization and LLM extraction pipeline.
Verifies HTML stripping, boilerplate pruning, mock Gemini extraction,
exponential backoff retry behavior, and batch queue processing.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.extractor.gemini_client import (
    CIRCUIT_BREAK_AFTER,
    DailyQuotaExhaustedError,
    is_daily_quota_exhausted,
    is_deadline_or_timeout_error,
    is_transient_error,
    _is_transient_error,
)
from src.extractor.schemas import BatchExtractedJob, ExtractedJob
from src.extractor.text_cleaner import clean_job_description
from src.extractor.text_sanitizer import (
    build_sanitized_job_prompt,
    clean_html,
    strip_boilerplate,
)
from src.extractor.llm_extractor import (
    BATCH_SIZE,
    GeminiExtractor,
    is_tech_job,
    process_unprocessed_jobs,
)
from src.storage.db import DatabaseManager


def _job(i, title="Backend Python Developer", company=None):
    return {
        "id": f"job_{i:03d}",
        "title": title,
        "company": company or f"Company {i}",
        "url": f"https://example.com/{i}",
        "teaser": "Python and FastAPI backend role",
    }


def _answer(idx, title="Backend Python Developer", company="Acme", **skills):
    return BatchExtractedJob(id=idx, job_title=title, company=company, experience_level="Junior", **skills)


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


class TestJobDescriptionCleaner(unittest.TestCase):
    def test_strip_welfare_benefits_english(self):
        markers = [
            "benefits:", "welfare:", "what we offer:", "perks:",
            "about us:", "about company:", "how to apply:", "company overview:",
        ]
        for marker in markers:
            raw = f"""
            Requirements:
            - 3+ years experience with Python and Docker
            - Kubernetes, PostgreSQL, and SQL query tuning

            {marker}
            - Premium health insurance and dental plan
            - Annual performance bonus and provident fund
            - Free barista coffee, snacks, and company trips
            """
            cleaned = clean_job_description(raw, max_chars=1500)
            self.assertIn("Python", cleaned, f"Should keep Python for marker {marker}")
            self.assertIn("Docker", cleaned, f"Should keep Docker for marker {marker}")
            self.assertIn("Kubernetes", cleaned, f"Should keep Kubernetes for marker {marker}")
            self.assertIn("SQL", cleaned, f"Should keep SQL for marker {marker}")
            self.assertNotIn(marker, cleaned.lower(), f"Should remove marker {marker}")
            self.assertNotIn("health insurance", cleaned.lower(), f"Should remove perks for {marker}")
            self.assertNotIn("barista coffee", cleaned.lower(), f"Should remove perks for {marker}")

    def test_strip_welfare_benefits_thai(self):
        markers = [
            "สวัสดิการ:", "สิทธิประโยชน์:", "เกี่ยวกับบริษัท:",
            "วิธีการสมัคร:", "ข้อมูลติดต่อ:",
        ]
        for marker in markers:
            raw = f"""
            คุณสมบัติ:
            - สามารถพัฒนา Backend ด้วย Python, FastAPI, Docker
            - ใช้งานฐานข้อมูล SQL และ PostgreSQL ได้อย่างมีประสิทธิภาพ

            {marker}
            - ประกันสุขภาพกลุ่มและประกันอุบัติเหตุ
            - โบนัสประจำปีและกองทุนสำรองเลี้ยงชีพ
            - เบี้ยขยันและวันหยุดพักร้อน
            """
            cleaned = clean_job_description(raw, max_chars=1500)
            self.assertIn("Python", cleaned, f"Should keep Python for Thai marker {marker}")
            self.assertIn("FastAPI", cleaned, f"Should keep FastAPI for Thai marker {marker}")
            self.assertIn("Docker", cleaned, f"Should keep Docker for Thai marker {marker}")
            self.assertIn("SQL", cleaned, f"Should keep SQL for Thai marker {marker}")
            self.assertNotIn(marker, cleaned, f"Should remove Thai marker {marker}")
            self.assertNotIn("ประกันสุขภาพ", cleaned, f"Should remove perks for {marker}")
            self.assertNotIn("กองทุนสำรองเลี้ยงชีพ", cleaned, f"Should remove perks for {marker}")

    def test_truncation_limit_enforcement(self):
        long_text = "\n".join([f"Requirement {i}: Python, Docker, Kubernetes, SQL, AWS, Kafka" for i in range(100)])
        for limit in [100, 300, 500, 1000, 1500]:
            cleaned = clean_job_description(long_text, max_chars=limit)
            self.assertLessEqual(len(cleaned), limit, f"Cleaned text must be <= {limit} characters")
            self.assertGreater(len(cleaned), int(limit * 0.6), "Cleaned text should not be overly truncated")

    def test_preservation_of_core_technical_keywords(self):
        raw = """
        About Us:
        Leading fintech organization based in Bangkok.

        Role & Requirements:
        - Must have deep knowledge of Python, Docker, Kubernetes, and SQL
        - Hands-on experience with FastAPI, Redis, PostgreSQL, and AWS
        - CI/CD automation with GitHub Actions

        Benefits:
        - Work from home allowance
        - Health insurance
        """
        cleaned = clean_job_description(raw, max_chars=1500)
        for keyword in ["Python", "Docker", "Kubernetes", "SQL", "FastAPI", "Redis", "PostgreSQL", "AWS"]:
            self.assertIn(keyword, cleaned, f"Core keyword {keyword} must be preserved")
        self.assertNotIn("About Us", cleaned)
        self.assertNotIn("Benefits", cleaned)
        self.assertNotIn("Health insurance", cleaned)

    def test_safe_handling_of_empty_none_or_short_descriptions(self):
        self.assertEqual(clean_job_description(""), "")
        self.assertEqual(clean_job_description(None), "")
        self.assertEqual(clean_job_description("   "), "")
        self.assertEqual(clean_job_description("\n\t\n"), "")
        self.assertEqual(clean_job_description("Python Developer"), "Python Developer")
        short_desc = "Junior Go Developer at TechCorp"
        self.assertEqual(clean_job_description(short_desc, max_chars=1500), short_desc)

    def test_normalize_whitespace_and_blank_lines(self):
        raw = """
        Requirements:

        -   Python     and    Docker

        -       FastAPI and      SQL


        """
        cleaned = clean_job_description(raw)
        self.assertNotIn("     ", cleaned)
        self.assertNotIn("\n\n\n", cleaned)
        self.assertIn("Python and Docker", cleaned)
        self.assertIn("FastAPI and SQL", cleaned)


class TestGeminiExtractor(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.extractor = GeminiExtractor(
            api_key="fake-test-key",
            model="gemini-3.8-flash",
            rate_limit_delay=0.0,  # Fast tests
            client=self.mock_client,
        )

    def _respond(self, answers):
        response = MagicMock()
        response.parsed = answers
        return response

    def test_extract_batch_success_via_parsed(self):
        jobs = [_job(0), _job(1, title="Frontend React Developer")]
        self.mock_client.models.generate_content.return_value = self._respond([
            _answer(0, must_have_skills=["Python", "FastAPI"], databases=["PostgreSQL"]),
            _answer(1, title="Frontend React Developer", must_have_skills=["TypeScript", "React"]),
        ])

        results = self.extractor.extract_batch(jobs)

        self.assertEqual(set(results), {"job_000", "job_001"})
        self.assertIn("FastAPI", results["job_000"].must_have_skills)
        self.assertIn("React", results["job_001"].must_have_skills)
        self.assertIsInstance(results["job_000"], ExtractedJob)
        self.assertEqual(self.mock_client.models.generate_content.call_count, 1)

    def test_extract_batch_success_via_json_text(self):
        response = MagicMock()
        response.parsed = None
        response.text = json.dumps([{
            "id": 0,
            "job_title": "Data Engineer",
            "company": "FinTech Bangkok",
            "experience_level": "Mid",
            "must_have_skills": ["Python", "Apache Spark"],
            "databases": ["PostgreSQL", "BigQuery"],
            "tools": ["Git", "Airflow"],
        }])
        self.mock_client.models.generate_content.return_value = response

        results = self.extractor.extract_batch([_job(0, title="Data Engineer")])

        self.assertEqual(results["job_000"].experience_level, "Mid")
        self.assertIn("BigQuery", results["job_000"].databases)

    def test_extract_batch_sends_one_json_payload(self):
        jobs = [_job(i) for i in range(3)]
        self.mock_client.models.generate_content.return_value = self._respond([])

        self.extractor.extract_batch(jobs)

        sent = json.loads(self.mock_client.models.generate_content.call_args[1]["contents"])
        self.assertEqual([item["id"] for item in sent], [0, 1, 2])
        self.assertEqual(set(sent[0]), {"id", "title", "company", "description"})
        self.assertIn("FastAPI", sent[0]["description"])

    def test_extract_batch_cleans_candidate_descriptions(self):
        jobs = [{
            "id": "job_999",
            "title": "Backend Lead",
            "company": "Bangkok Bank Tech",
            "description": (
                "About Company:\nAcme Corp is big.\n\n"
                "Requirements:\n- Python, Docker, Kubernetes, SQL\n\n"
                "Benefits:\n- Health insurance\n- Free coffee\n"
            ),
        }]
        self.mock_client.models.generate_content.return_value = self._respond([])
        self.extractor.extract_batch(jobs)

        sent = json.loads(self.mock_client.models.generate_content.call_args[1]["contents"])
        desc = sent[0]["description"]
        self.assertIn("Python", desc)
        self.assertIn("Docker", desc)
        self.assertNotIn("About Company", desc)
        self.assertNotIn("Health insurance", desc)
        self.assertLessEqual(len(desc), 1500)

    def test_extract_batch_discards_unknown_and_duplicate_ids(self):
        jobs = [_job(0), _job(1)]
        self.mock_client.models.generate_content.return_value = self._respond([
            _answer(0, must_have_skills=["Go"]),
            _answer(0, must_have_skills=["Rust"]),  # duplicate: first answer wins
            _answer(7, must_have_skills=["Java"]),  # not in the batch
        ])

        results = self.extractor.extract_batch(jobs)

        self.assertEqual(list(results), ["job_000"])
        self.assertEqual(results["job_000"].must_have_skills, ["Go"])

    def test_extract_batch_fills_missing_title_and_company(self):
        self.mock_client.models.generate_content.return_value = self._respond([_answer(0, title="", company="")])

        results = self.extractor.extract_batch([_job(0, title="Python Developer", company="Siam Soft")])

        self.assertEqual(results["job_000"].job_title, "Python Developer")
        self.assertEqual(results["job_000"].company, "Siam Soft")

    def test_extract_batch_retry_on_rate_limit(self):
        self.mock_client.models.generate_content.side_effect = [
            Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded"),
            self._respond([_answer(0, must_have_skills=["PyTorch"])]),
        ]

        with patch("time.sleep"):  # Mock sleep so tests run instantly
            results = self.extractor.extract_batch([_job(0)])

        self.assertIn("job_000", results)
        self.assertEqual(self.mock_client.models.generate_content.call_count, 2)

    def test_extract_batch_returns_empty_when_retries_exhausted(self):
        self.mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

        with patch("time.sleep"):
            results = self.extractor.extract_batch([_job(0)])

        self.assertEqual(results, {})

    def test_is_transient_error_rejects_numbers_containing_500_and_502(self):
        non_transient_samples = [
            "Input exceeded 1500 chars",
            "Salary 50000 THB",
            "Budget range: 25000 - 35000",
            "Error occurred at line 5020 in script",
        ]
        for msg in non_transient_samples:
            info = is_transient_error(msg)
            self.assertFalse(info.is_transient, f"Expected '{msg}' to be non-transient, got {info}")

    def test_is_transient_error_rejects_pydantic_validation_error(self):
        from pydantic import TypeAdapter, ValidationError

        try:
            TypeAdapter(int).validate_python("exceeded 1500 items")
        except ValidationError as ve:
            info = is_transient_error(ve)
            self.assertFalse(info.is_transient, f"Expected ValidationError to be non-transient, got {info}")

    def test_is_transient_error_structural_status_codes(self):
        class MockApiError(Exception):
            def __init__(self, message, code=None, status=None):
                super().__init__(message)
                self.code = code
                self.status = status

        # Structural transient errors
        err_503 = MockApiError("Service unavailable", code=503)
        info_503 = is_transient_error(err_503)
        self.assertTrue(info_503.is_transient)
        self.assertTrue(info_503.is_503)

        err_429 = MockApiError("Rate limited", code=429)
        info_429 = is_transient_error(err_429)
        self.assertTrue(info_429.is_transient)
        self.assertTrue(info_429.is_rate_limit)

        err_504 = MockApiError("Timeout", code=504)
        info_504 = is_transient_error(err_504)
        self.assertTrue(info_504.is_transient)
        self.assertTrue(info_504.is_504_or_deadline)

        err_500 = MockApiError("Server error", code=500)
        self.assertTrue(is_transient_error(err_500).is_transient)

        err_502 = MockApiError("Bad gateway", code=502)
        self.assertTrue(is_transient_error(err_502).is_transient)

        # Structural status enum strings
        err_status_unavailable = MockApiError("Unavailable", status="UNAVAILABLE")
        self.assertTrue(is_transient_error(err_status_unavailable).is_503)

        err_status_exhausted = MockApiError("Exhausted", status="RESOURCE_EXHAUSTED")
        self.assertTrue(is_transient_error(err_status_exhausted).is_rate_limit)

        err_status_deadline = MockApiError("Deadline", status="DEADLINE_EXCEEDED")
        self.assertTrue(is_transient_error(err_status_deadline).is_504_or_deadline)

        # Non-transient status codes
        err_400 = MockApiError("Bad Request", code=400)
        self.assertFalse(is_transient_error(err_400).is_transient)

        err_404 = MockApiError("Not Found", code=404)
        self.assertFalse(is_transient_error(err_404).is_transient)

    def test_generate_aborts_immediately_on_validation_error(self):
        # Return response whose payload fails schema validation with text containing '1500'
        resp = MagicMock()
        resp.parsed = None
        resp.text = json.dumps([{"id": "bad_id_1500", "invalid_field": 1500}])
        self.mock_client.models.generate_content.return_value = resp

        with patch("time.sleep") as mock_sleep:
            results = self.extractor.extract_batch([_job(0)])

        self.assertEqual(results, {})
        # Must NOT retry when payload fails Pydantic schema validation
        self.assertEqual(self.mock_client.models.generate_content.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)

    def test_generate_respects_overall_wall_clock_deadline(self):
        self.mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

        # Simulate monotonic clock: start at 0, record call at 1.0, then elapsed check jumps to 80.0s (past deadline)
        times = iter([0.0, 1.0, 80.0])
        with patch("time.monotonic", side_effect=lambda: next(times, 100.0)), patch("time.sleep") as mock_sleep:
            results = self.extractor.extract_batch([_job(0)])

        self.assertEqual(results, {})
        # Should abort after 1 call because 80.0s exceeds the overall deadline
        self.assertEqual(self.mock_client.models.generate_content.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)

    def test_extract_batch_503_fallback_to_gemini_2_5_flash(self):
        self.mock_client.models.generate_content.side_effect = [
            Exception("503 UNAVAILABLE: Model is currently experiencing high demand"),
            Exception("503 UNAVAILABLE: Model is currently experiencing high demand"),
            self._respond([_answer(0, must_have_skills=["Terraform"])]),
        ]

        with patch("time.sleep") as mock_sleep:
            results = self.extractor.extract_batch([_job(0)])

        self.assertIn("job_000", results)
        calls = self.mock_client.models.generate_content.call_args_list
        self.assertEqual([c[1]["model"] for c in calls], ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-2.5-flash"])
        self.assertEqual(mock_sleep.call_count, 2)

    def test_extract_batch_504_fallback_to_gemini_2_5_flash(self):
        self.mock_client.models.generate_content.side_effect = [
            Exception("504 Gateway Timeout"),
            self._respond([_answer(0, must_have_skills=["Go", "Docker"])]),
        ]

        with patch("time.sleep") as mock_sleep:
            results = self.extractor.extract_batch([_job(0)])

        self.assertIn("job_000", results)
        calls = self.mock_client.models.generate_content.call_args_list
        self.assertEqual([c[1]["model"] for c in calls], ["gemini-3.8-flash", "gemini-2.5-flash"])
        self.assertEqual(mock_sleep.call_count, 1)

    def test_extract_batch_deadline_exceeded_fallback_to_gemini_2_5_flash(self):
        self.mock_client.models.generate_content.side_effect = [
            Exception("DEADLINE_EXCEEDED: The request exceeded the deadline"),
            self._respond([_answer(0, must_have_skills=["Kubernetes"])]),
        ]

        with patch("time.sleep") as mock_sleep:
            results = self.extractor.extract_batch([_job(0)])

        self.assertIn("job_000", results)
        calls = self.mock_client.models.generate_content.call_args_list
        self.assertEqual([c[1]["model"] for c in calls], ["gemini-3.8-flash", "gemini-2.5-flash"])
        self.assertEqual(mock_sleep.call_count, 1)

    def test_is_transient_error_classification(self):
        # 504 / Gateway Timeout / DEADLINE_EXCEEDED -> transient & triggers fallback
        for err in [
            "504 Gateway Timeout",
            "HTTP 504: gateway timeout",
            "DEADLINE_EXCEEDED: Deadline exceeded",
            "deadline exceeded while processing",
        ]:
            info = is_transient_error(err)
            self.assertTrue(bool(info), f"Expected {err} to evaluate as transient (True)")
            self.assertTrue(info.is_transient, f"Expected {err} to be transient")
            self.assertTrue(info.is_504_or_deadline, f"Expected {err} to be 504 or deadline exceeded")
            self.assertTrue(is_deadline_or_timeout_error(err))
            self.assertTrue(_is_transient_error(err))
            self.assertTrue(self.extractor._is_transient_error(err))

        # 502 / 500 / other timeouts -> transient
        for err in ["502 Bad Gateway", "500 Internal Server Error", "Connection timed out"]:
            info = is_transient_error(err)
            self.assertTrue(bool(info), f"Expected {err} to be transient")
            self.assertTrue(info.is_transient)

        # 503 -> transient with is_503=True
        info_503 = is_transient_error("503 Service Unavailable")
        self.assertTrue(info_503.is_transient)
        self.assertTrue(info_503.is_503)

        # 429 -> transient with is_rate_limit=True
        info_429 = is_transient_error("429 RESOURCE_EXHAUSTED: Rate limit exceeded")
        self.assertTrue(info_429.is_transient)
        self.assertTrue(info_429.is_rate_limit)

        # Non-transient errors (400, 404, etc.)
        for err in ["400 Bad Request", "404 Not Found", "401 Unauthorized"]:
            info = is_transient_error(err)
            self.assertFalse(bool(info), f"Expected {err} to evaluate as False")
            self.assertFalse(info.is_transient)

    def test_extract_batch_fails_fast_on_daily_quota(self):
        self.mock_client.models.generate_content.side_effect = Exception(
            "429 Quota exceeded for quota metric 'GenerateRequestsPerDayPerProjectPerModel'"
        )

        with self.assertRaises(DailyQuotaExhaustedError):
            self.extractor.extract_batch([_job(0)])

        # Must not retry when daily quota is exhausted
        self.assertEqual(self.mock_client.models.generate_content.call_count, 1)

    def test_circuit_opens_after_consecutive_failed_calls(self):
        self.mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

        with patch("time.sleep"):
            for _ in range(CIRCUIT_BREAK_AFTER):
                self.assertEqual(self.extractor.extract_batch([_job(0)]), {})
            calls_before = self.mock_client.models.generate_content.call_count
            with self.assertRaises(DailyQuotaExhaustedError):
                self.extractor.extract_batch([_job(0)])

        # The open circuit refuses before making a request
        self.assertEqual(self.mock_client.models.generate_content.call_count, calls_before)

    def test_model_default_and_custom_override(self):
        with patch.dict("os.environ", {}, clear=True):
            extractor_default = GeminiExtractor(api_key="fake_key")
            self.assertEqual(extractor_default.model_name, "gemini-3.8-flash")

        with patch.dict("os.environ", {"GEMINI_MODEL": "gemini-env-model"}):
            extractor_env = GeminiExtractor(api_key="fake_key")
            self.assertEqual(extractor_env.model_name, "gemini-env-model")

        extractor_custom = GeminiExtractor(api_key="fake_key", model_name="gemini-custom-model")
        self.assertEqual(extractor_custom.model_name, "gemini-custom-model")

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


class TestBatchQueueProcessing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jhunt_batch_test_")
        self.db = DatabaseManager(db_path=Path(self.temp_dir) / "market.db")
        self.extractor = MagicMock(spec=GeminiExtractor)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed(self, jobs):
        for job in jobs:
            self.db.save_job(job)
        return jobs

    @staticmethod
    def _answer_all(batch):
        return {
            job["id"]: ExtractedJob(job_title=job["title"], company=job["company"], must_have_skills=["Python"])
            for job in batch
        }

    def test_batch_process_unprocessed_jobs(self):
        self._seed([_job(0), _job(1, title="Frontend React Developer")])
        self.extractor.extract_batch.side_effect = self._answer_all

        processed = process_unprocessed_jobs(db=self.db, extractor=self.extractor)

        self.assertEqual(processed, 2)
        self.assertEqual(self.extractor.extract_batch.call_count, 1)
        self.assertEqual(self.db.get_unprocessed_jobs(), [])
        self.assertIn("Python", self.db.get_extracted_skills("job_000").must_have_skills)

    def test_thirty_jobs_cost_two_requests(self):
        self._seed([_job(i) for i in range(30)])
        self.extractor.extract_batch.side_effect = self._answer_all

        processed = process_unprocessed_jobs(db=self.db, extractor=self.extractor, limit=30)

        self.assertEqual(processed, 30)
        self.assertEqual(self.extractor.extract_batch.call_count, 2)
        sizes = [len(c[0][0]) for c in self.extractor.extract_batch.call_args_list]
        self.assertEqual(sizes, [BATCH_SIZE, BATCH_SIZE])

    def test_limit_caps_jobs_sent(self):
        self._seed([_job(i) for i in range(20)])
        self.extractor.extract_batch.side_effect = self._answer_all

        processed = process_unprocessed_jobs(db=self.db, extractor=self.extractor, limit=10)

        self.assertEqual(processed, 10)
        self.assertEqual(len(self.db.get_unprocessed_jobs()), 10)

    def test_unanswered_jobs_stay_queued(self):
        self._seed([_job(0), _job(1)])
        self.extractor.extract_batch.side_effect = lambda batch: {
            j["id"]: ExtractedJob(job_title=j["title"], company=j["company"], must_have_skills=["Python"])
            for j in batch if j["id"] == "job_000"
        }

        processed = process_unprocessed_jobs(db=self.db, extractor=self.extractor)

        self.assertEqual(processed, 1)
        self.assertEqual([j["id"] for j in self.db.get_unprocessed_jobs()], ["job_001"])

    def test_batch_process_stops_gracefully_on_daily_quota(self):
        self._seed([_job(i) for i in range(20)])
        self.extractor.extract_batch.side_effect = [
            self._answer_all([_job(i) for i in range(BATCH_SIZE)]),
            DailyQuotaExhaustedError("Daily quota exhausted"),
        ]

        processed = process_unprocessed_jobs(db=self.db, extractor=self.extractor)

        self.assertEqual(processed, BATCH_SIZE)
        self.assertEqual(self.extractor.extract_batch.call_count, 2)
        self.assertEqual(len(self.db.get_unprocessed_jobs()), 20 - BATCH_SIZE)

    def test_batch_process_skips_non_tech_jobs(self):
        self._seed([
            {"id": "nt_001", "title": "Sales Representative", "company": "Sales Co", "url": "https://example.com/nt", "teaser": "Cold calls"},
            {"id": "nt_002", "title": "Python Developer", "company": "Tech Co", "url": "https://example.com/t", "teaser": "Backend code"},
        ])
        self.extractor.extract_batch.side_effect = self._answer_all

        processed = process_unprocessed_jobs(db=self.db, extractor=self.extractor)

        self.assertEqual(processed, 1)
        sent = self.extractor.extract_batch.call_args[0][0]
        self.assertEqual([j["id"] for j in sent], ["nt_002"])
        self.assertEqual(self.db.get_unprocessed_jobs(), [])

        nt_skills = self.db.get_extracted_skills("nt_001")
        self.assertEqual(nt_skills.experience_level, "Non-Tech")
        self.assertEqual(nt_skills.must_have_skills, [])

    def test_extracted_skills_are_synced_to_turso_in_one_call(self):
        self._seed([_job(0), _job(1)])
        self.extractor.extract_batch.side_effect = self._answer_all
        turso = MagicMock()

        process_unprocessed_jobs(db=self.db, extractor=self.extractor, turso=turso)

        turso.sync_extracted_skills.assert_called_once()
        self.assertEqual(len(turso.sync_extracted_skills.call_args[0][0]), 2)

    def test_unexpected_batch_failure_increments_extract_attempts(self):
        self._seed([_job(0), _job(1)])
        self.extractor.extract_batch.side_effect = RuntimeError("Malformed LLM JSON")
        mock_storage = MagicMock()
        mock_storage.get_unprocessed_jobs.return_value = [_job(0), _job(1)]

        processed = process_unprocessed_jobs(storage=mock_storage, extractor=self.extractor)

        self.assertEqual(processed, 0)
        mock_storage.increment_extract_attempts.assert_called_once_with(["job_000", "job_001"])

    def test_unanswered_jobs_in_batch_increment_extract_attempts(self):
        jobs = [_job(0), _job(1)]
        self._seed(jobs)
        self.extractor.extract_batch.return_value = {
            "job_000": ExtractedJob(job_title="Job 0", company="Co 0", must_have_skills=["Python"])
        }
        mock_storage = MagicMock()
        mock_storage.get_unprocessed_jobs.return_value = jobs

        processed = process_unprocessed_jobs(storage=mock_storage, extractor=self.extractor)

        self.assertEqual(processed, 1)
        mock_storage.increment_extract_attempts.assert_called_once_with(["job_001"])


if __name__ == "__main__":
    unittest.main()
