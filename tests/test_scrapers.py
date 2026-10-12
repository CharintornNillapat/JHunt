# tests/test_scrapers.py
"""
Hermetic test suite for JHunt Scraper Adapter Architecture.
Tests JobsDB, Blognone, and JobThai scraper adapters, ensuring:
- Strict contract parity (all return List[RawJob])
- Correct ID prefixing (jobsdb_*, blognone_*, jobthai_*)
- Resilient parsing (HTML, GraphQL, JSON)
- Zero real outbound network traffic
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from src.models import RawJob
from src.scrapers import (
    BaseScraper,
    BlognoneScraper,
    JobsDBScraper,
    JobThaiScraper,
    get_active_scrapers,
)


class TestRawJobModel(unittest.TestCase):
    def test_raw_job_initialization_and_fields(self):
        job = RawJob(
            id="jobsdb_12345",
            title="Senior Python Developer",
            company="Fintech Co",
            location="Bangkok",
            description="Build scalable APIs",
            url="https://th.jobsdb.com/job/12345",
            source="jobsdb",
            posted_at="2026-10-10",
            salary="80,000 - 120,000 THB",
            work_type="Full-time",
            tags=["Python", "FastAPI"],
        )
        self.assertEqual(job.id, "jobsdb_12345")
        self.assertEqual(job.title, "Senior Python Developer")
        self.assertEqual(job.company, "Fintech Co")
        self.assertEqual(job.source, "jobsdb")
        self.assertEqual(job.tags, ["Python", "FastAPI"])

    def test_raw_job_dict_like_access_compatibility(self):
        job = RawJob(
            id="blognone_dev-1",
            title="Backend Engineer",
            company="Agile Ltd",
            source="blognone",
            location="Chiang Mai",
        )
        # Test __getitem__
        self.assertEqual(job["id"], "blognone_dev-1")
        self.assertEqual(job["title"], "Backend Engineer")
        self.assertEqual(job["location"], "Chiang Mai")

        # Test get()
        self.assertEqual(job.get("company"), "Agile Ltd")
        self.assertEqual(job.get("non_existent", "default_val"), "default_val")

        # Test __contains__
        self.assertIn("title", job)
        self.assertNotIn("non_existent_key", job)

        # Test __setitem__
        job["url"] = "https://jobs.blognone.com/job/dev-1"
        self.assertEqual(job.url, "https://jobs.blognone.com/job/dev-1")

        # Test to_dict()
        d = job.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["id"], "blognone_dev-1")


class TestScrapersFactory(unittest.TestCase):
    def test_get_active_scrapers(self):
        scrapers = get_active_scrapers()
        self.assertEqual(len(scrapers), 3)

        classes = [s.__class__.__name__ for s in scrapers]
        self.assertIn("JobsDBScraper", classes)
        self.assertIn("BlognoneScraper", classes)
        self.assertIn("JobThaiScraper", classes)

        for s in scrapers:
            self.assertIsInstance(s, BaseScraper)


class TestJobsDBScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = JobsDBScraper(keywords=["python developer"])
        self.mock_api_payload = {
            "totalCount": 2,
            "data": [
                {
                    "id": "78901234",
                    "title": "Full Stack Python Developer",
                    "companyName": "Bangkok Tech Ltd",
                    "locations": [{"label": "Bangkok"}],
                    "workTypes": ["Full-time"],
                    "workArrangements": {"data": [{"label": {"text": "Hybrid"}}]},
                    "salaryLabel": "60,000 - 90,000 THB",
                    "teaser": "Exciting role building cloud applications",
                    "bulletPoints": ["Python / Django", "React", "Docker"],
                    "listingDate": "2026-10-10T08:00:00Z",
                },
                {
                    "id": "78901235",
                    "title": "Data Engineer",
                    "companyName": "Data Co",
                    "locations": [{"label": "Nonthaburi"}],
                    "workTypes": ["Full-time"],
                    "salaryLabel": "",
                    "teaser": "ETL pipelines",
                    "bulletPoints": ["SQL", "Airflow"],
                    "listingDate": "2026-10-09T08:00:00Z",
                },
            ],
        }

    @patch("requests.Session.get")
    def test_jobsdb_scrape_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.mock_api_payload
        mock_get.return_value = mock_resp

        jobs = self.scraper.scrape(keywords=["python developer"], limit=10)

        self.assertEqual(len(jobs), 2)
        job1 = jobs[0]
        self.assertIsInstance(job1, RawJob)
        self.assertEqual(job1.id, "jobsdb_78901234")
        self.assertEqual(job1.title, "Full Stack Python Developer")
        self.assertEqual(job1.company, "Bangkok Tech Ltd")
        self.assertEqual(job1.source, "jobsdb")
        self.assertEqual(job1.location, "Bangkok")
        self.assertEqual(job1.salary, "60,000 - 90,000 THB")
        self.assertIn("Full-time", job1.work_type)
        self.assertIn("Hybrid", job1.work_type)
        self.assertIn("Python / Django", job1.description)
        self.assertEqual(job1.url, "https://th.jobsdb.com/job/78901234")

    @patch("requests.Session.get")
    def test_jobsdb_scrape_respects_limit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.mock_api_payload
        mock_get.return_value = mock_resp

        jobs = self.scraper.scrape(keywords=["python developer"], limit=1)
        self.assertEqual(len(jobs), 1)

    @patch("requests.Session.get")
    def test_jobsdb_malformed_record_handling(self, mock_get):
        malformed_payload = {
            "totalCount": 2,
            "data": [
                {"id": "", "title": "Missing ID"},
                {"id": "valid_123", "title": "", "companyName": "Missing Title"},
                {"id": "valid_456", "title": "Valid Dev", "companyName": "Valid Co"},
            ],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = malformed_payload
        mock_get.return_value = mock_resp

        jobs = self.scraper.scrape(keywords=["python developer"])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].id, "jobsdb_valid_456")

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_jobsdb_scrape_covers_all_keywords(self, mock_get, mock_sleep):
        def mock_fetch(url, params=None, timeout=None):
            kw = (params or {}).get("keywords")
            resp = MagicMock()
            resp.status_code = 200
            if kw == "python":
                resp.json.return_value = {
                    "totalCount": 1,
                    "data": [{"id": "111", "title": "Python Dev", "companyName": "Co A"}],
                }
            else:
                resp.json.return_value = {
                    "totalCount": 1,
                    "data": [{"id": "222", "title": "Data Eng", "companyName": "Co B"}],
                }
            return resp

        mock_get.side_effect = mock_fetch
        jobs = self.scraper.scrape(keywords=["python", "data"], limit=1)
        self.assertEqual(len(jobs), 2)
        ids = [j.id for j in jobs]
        self.assertEqual(ids, ["jobsdb_111", "jobsdb_222"])


class TestBlognoneScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = BlognoneScraper(fetch_details=True)
        self.mock_ssr_json = {
            "api": {
                "endpoint": "https://jobs-api.blognone.com",
            },
            "r": {
                "name": "search",
                "data": {
                    "jobs_count": 1,
                    "jobs": [
                        {
                            "slug": "ai-engineer-Ir_5",
                            "title": "AI Engineer",
                            "company": {
                                "slug": "computer-data-system",
                                "name_en": "Computer Data System",
                                "name_th": "บริษัท คอมพิวเตอร์ดาต้าซิสเต็ม จำกัด",
                            },
                            "type": "FULL_TIME",
                            "province": "Bangkok",
                            "district": "Pathum Wan",
                            "level": "SENIOR",
                            "salary_min": "70000.00",
                            "salary_max": "100000.00",
                            "salary_display_format": "70,000 - 100,000",
                            "skills": ["Python", "PyTorch", "LLM"],
                            "updated": "2026-10-10T10:00:00Z",
                        }
                    ],
                },
            },
        }

        self.mock_search_html = f"""
        <!doctype html>
        <html>
        <head><title>Search Jobs</title></head>
        <body>
        <script>{json.dumps(self.mock_ssr_json)}</script>
        </body>
        </html>
        """

        self.mock_detail_html = """
        <!doctype html>
        <html>
        <head>
          <script type="application/ld+json">
          {
            "@context": "http://schema.org",
            "@type": "JobPosting",
            "title": "AI Engineer",
            "description": "<p>Design and deploy production RAG and LLM systems.</p>"
          }
          </script>
        </head>
        <body>Job Detail Body</body>
        </html>
        """

    @patch("requests.Session.get")
    def test_blognone_scrape_success(self, mock_get):
        def side_effect(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "search" in url:
                resp.text = self.mock_search_html
            else:
                resp.text = self.mock_detail_html
            return resp

        mock_get.side_effect = side_effect

        jobs = self.scraper.scrape(keywords=["ai engineer"], limit=10)

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertIsInstance(job, RawJob)
        self.assertEqual(job.id, "blognone_ai-engineer-Ir_5")
        self.assertEqual(job.title, "AI Engineer")
        self.assertEqual(job.company, "Computer Data System")
        self.assertEqual(job.source, "blognone")
        self.assertEqual(job.location, "Pathum Wan, Bangkok")
        self.assertEqual(job.salary, "70,000 - 100,000 THB")
        self.assertEqual(job.work_type, "FULL_TIME")
        self.assertEqual(job.tags, ["Python", "PyTorch", "LLM"])
        self.assertIn("production RAG and LLM systems", job.description)
        self.assertEqual(
            job.url,
            "https://jobs.blognone.com/company/computer-data-system/job/ai-engineer-Ir_5",
        )

    @patch("requests.Session.get")
    def test_blognone_scrape_fallback_description_when_detail_fails(self, mock_get):
        def side_effect(url, *args, **kwargs):
            resp = MagicMock()
            if "search" in url:
                resp.status_code = 200
                resp.text = self.mock_search_html
            else:
                resp.status_code = 404
                resp.text = "Not found"
            return resp

        mock_get.side_effect = side_effect

        jobs = self.scraper.scrape(keywords=["ai engineer"], limit=10)
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertIn("Position: AI Engineer", job.description)
        self.assertIn("Technical Stack: Python, PyTorch, LLM", job.description)

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_blognone_scrape_covers_all_keywords(self, mock_get, mock_sleep):
        scraper = BlognoneScraper(fetch_details=False)

        def mock_fetch(url, params=None, timeout=None):
            resp = MagicMock()
            resp.status_code = 200
            kw = (params or {}).get("q", "")
            ssr = {
                "api": {"endpoint": "https://jobs-api.blognone.com"},
                "r": {
                    "data": {
                        "jobs_count": 1,
                        "jobs": [{"slug": f"job-{kw}", "title": f"Title {kw}", "company": {"name_en": "Co"}}],
                    }
                },
            }
            resp.text = f"<script>{json.dumps(ssr)}</script>"
            return resp

        mock_get.side_effect = mock_fetch
        jobs = scraper.scrape(keywords=["python", "data"], limit=1)
        self.assertEqual(len(jobs), 2)
        ids = [j.id for j in jobs]
        self.assertEqual(ids, ["blognone_job-python", "blognone_job-data"])

    @patch("requests.Session.get")
    def test_blognone_skips_detail_fetch_for_known_ids(self, mock_get):
        scraper = BlognoneScraper(fetch_details=True)
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.text = self.mock_search_html
        mock_get.return_value = search_resp

        with patch.object(scraper, "_fetch_detail_description") as mock_detail:
            jobs = scraper.scrape(keywords=["python"], limit=1, known_ids={"blognone_ai-engineer-Ir_5"})
            self.assertEqual(len(jobs), 1)
            mock_detail.assert_not_called()

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_blognone_rate_limiting_delay_before_new_detail_fetch(self, mock_get, mock_sleep):
        scraper = BlognoneScraper(fetch_details=True)
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.text = self.mock_search_html
        mock_get.return_value = search_resp

        with patch.object(scraper, "_fetch_detail_description", return_value="Detail text"):
            jobs = scraper.scrape(keywords=["python"], limit=1, known_ids=set())
            self.assertEqual(len(jobs), 1)
            mock_sleep.assert_called_with(scraper.REQUEST_DELAY)


class TestJobThaiScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = JobThaiScraper(fetch_details=True)
        self.mock_graphql_search = {
            "data": {
                "searchJobs": {
                    "data": {
                        "total": 1,
                        "data": [
                            {
                                "id": 1547764,
                                "companyID": 339502,
                                "jobTitle": "Python / Odoo Backend Developer",
                                "companyName": "Global Auto Co., Ltd.",
                                "salary": "70,000 - 100,000 THB",
                                "updatedAt": "2026-10-11T11:00:00.000Z",
                                "province": {"name": "Bangkok"},
                                "district": {"name": "Huai Khwang"},
                                "tags": ["Python", "Odoo", "PostgreSQL"],
                            }
                        ],
                    }
                }
            }
        }

        self.mock_graphql_raw_data = {
            "data": {
                "getJobRawData": {
                    "data": {
                        "_id": 1547764,
                        "title": "Python / Odoo Backend Developer",
                        "description": "Develop and maintain core business ERP microservices.",
                        "properties": [
                            "Proficiency in Python and PostgreSQL",
                            "Understanding of API integration",
                        ],
                        "salary": "70,000 - 100,000 THB",
                    }
                }
            }
        }

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_jobthai_scrape_success(self, mock_get, mock_post):
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = self.mock_graphql_search
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = self.mock_graphql_raw_data
        mock_post.return_value = mock_post_resp

        jobs = self.scraper.scrape(keywords=["python developer"], limit=10)

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertIsInstance(job, RawJob)
        self.assertEqual(job.id, "jobthai_1547764")
        self.assertEqual(job.title, "Python / Odoo Backend Developer")
        self.assertEqual(job.company, "Global Auto Co., Ltd.")
        self.assertEqual(job.source, "jobthai")
        self.assertEqual(job.location, "Huai Khwang, Bangkok")
        self.assertEqual(job.salary, "70,000 - 100,000 THB")
        self.assertIn("Develop and maintain core business ERP", job.description)
        self.assertIn("Proficiency in Python and PostgreSQL", job.description)
        self.assertEqual(job.url, "https://www.jobthai.com/en/company/job/1547764")

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_jobthai_handles_missing_description_and_banner_format_gracefully(self, mock_get, mock_post):
        # Banner-only job: raw_data has null description and empty properties
        mock_banner_raw = {
            "data": {
                "getJobRawData": {
                    "data": {
                        "_id": 1547764,
                        "title": "Python / Odoo Backend Developer",
                        "description": None,
                        "properties": [],
                        "salary": "Negotiable",
                    }
                }
            }
        }

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = self.mock_graphql_search
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = mock_banner_raw
        mock_post.return_value = mock_post_resp

        jobs = self.scraper.scrape(keywords=["python developer"], limit=10)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].description, "")

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_jobthai_scrape_covers_all_keywords(self, mock_get, mock_sleep):
        scraper = JobThaiScraper(fetch_details=False)

        def mock_search(url, params=None, timeout=None):
            vars_json = json.loads(params["variables"])
            kw = vars_json["searchJobsFilter"]["keyword"]
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "data": {
                    "searchJobs": {
                        "data": {
                            "total": 1,
                            "data": [{"id": 100 if kw == "python" else 200, "jobTitle": f"Dev {kw}", "companyName": "Co"}],
                        }
                    }
                }
            }
            return resp

        mock_get.side_effect = mock_search
        jobs = scraper.scrape(keywords=["python", "data"], limit=1)
        self.assertEqual(len(jobs), 2)
        ids = [j.id for j in jobs]
        self.assertEqual(ids, ["jobthai_100", "jobthai_200"])

    @patch("requests.Session.get")
    def test_jobthai_skips_detail_fetch_for_known_ids(self, mock_get):
        scraper = JobThaiScraper(fetch_details=True)
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "data": {
                "searchJobs": {
                    "data": {
                        "total": 1,
                        "data": [{"id": 1547764, "jobTitle": "Dev", "companyName": "Co"}],
                    }
                }
            }
        }
        mock_get.return_value = search_resp

        with patch.object(scraper, "_fetch_job_description") as mock_desc:
            jobs = scraper.scrape(keywords=["python"], limit=1, known_ids={"jobthai_1547764"})
            self.assertEqual(len(jobs), 1)
            mock_desc.assert_not_called()

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_jobthai_rate_limiting_delay_before_new_detail_fetch(self, mock_get, mock_sleep):
        scraper = JobThaiScraper(fetch_details=True)
        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {
            "data": {
                "searchJobs": {
                    "data": {
                        "total": 1,
                        "data": [{"id": 1547764, "jobTitle": "Dev", "companyName": "Co"}],
                    }
                }
            }
        }
        mock_get.return_value = search_resp

        with patch.object(scraper, "_fetch_job_description", return_value="Job details"):
            jobs = scraper.scrape(keywords=["python"], limit=1, known_ids=set())
            self.assertEqual(len(jobs), 1)
            mock_sleep.assert_called_with(scraper.REQUEST_DELAY)


class TestContractParityAndZeroNetwork(unittest.TestCase):
    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_contract_parity_across_all_scrapers(self, mock_post, mock_get):
        # Setup mocks for all 3 scrapers
        jobsdb_resp = MagicMock(
            status_code=200,
            json=lambda: {
                "totalCount": 1,
                "data": [
                    {
                        "id": "111",
                        "title": "JobsDB Dev",
                        "companyName": "JobsDB Co",
                        "locations": [{"label": "Bangkok"}],
                    }
                ],
            },
        )

        blognone_html = """
        <script>{"api":{"endpoint":"https:\\u002F\\u002Fjobs-api.blognone.com"},"r":{"data":{"jobs":[{"slug":"bn-222","title":"Blognone Dev","company":{"slug":"bn-co","name_en":"Blognone Co"}}],"jobs_count":1}}}</script>
        """
        blognone_resp = MagicMock(status_code=200, text=blognone_html)

        jobthai_search = {
            "data": {
                "searchJobs": {
                    "data": {
                        "total": 1,
                        "data": [{"id": 333, "jobTitle": "JobThai Dev", "companyName": "JobThai Co"}],
                    }
                }
            }
        }
        jobthai_get_resp = MagicMock(status_code=200, json=lambda: jobthai_search)
        jobthai_post_resp = MagicMock(
            status_code=200,
            json=lambda: {"data": {"getJobRawData": {"data": {"description": "JobThai description"}}}},
        )

        def get_dispatcher(url, *args, **kwargs):
            if "jobsdb" in url:
                return jobsdb_resp
            elif "blognone" in url:
                return blognone_resp
            elif "jobthai" in url:
                return jobthai_get_resp
            return MagicMock(status_code=404)

        mock_get.side_effect = get_dispatcher
        mock_post.return_value = jobthai_post_resp

        scrapers = get_active_scrapers()
        all_scraped_jobs = []

        for scraper in scrapers:
            scraped = scraper.scrape(keywords=["developer"], limit=5)
            self.assertIsInstance(scraped, list)
            self.assertTrue(len(scraped) >= 1)
            for j in scraped:
                self.assertIsInstance(j, RawJob)
                self.assertTrue(j.id)
                self.assertTrue(j.title)
                self.assertTrue(j.company)
                self.assertIn(j.source, ("jobsdb", "blognone", "jobthai"))
                self.assertTrue(j.id.startswith(f"{j.source}_"))
            all_scraped_jobs.extend(scraped)

        self.assertEqual(len(all_scraped_jobs), 3)

    @patch("requests.Session.get")
    def test_jobsdb_network_error_resilience(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        scraper = JobsDBScraper(keywords=["python"])
        jobs = scraper.scrape()
        self.assertEqual(jobs, [])

    @patch("requests.Session.get")
    def test_blognone_network_error_resilience(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Read timeout")
        scraper = BlognoneScraper()
        jobs = scraper.scrape()
        self.assertEqual(jobs, [])

    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_jobthai_network_error_resilience(self, mock_post, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("Network down")
        mock_post.side_effect = requests.exceptions.RequestException("Network down")
        scraper = JobThaiScraper()
        jobs = scraper.scrape()
        self.assertEqual(jobs, [])

    @patch("socket.socket.connect")
    def test_zero_outbound_network_traffic(self, mock_connect):
        mock_connect.side_effect = AssertionError("Real outbound network socket connection attempted!")
        # Re-run all scrapers with mock requests to ensure no sockets ever connect
        with patch("requests.Session.get") as mock_get, patch("requests.Session.post") as mock_post:
            resp = MagicMock()
            resp.status_code = 404
            resp.raise_for_status.side_effect = Exception("404 Not Found")
            resp.text = ""
            resp.json.return_value = {}
            mock_get.return_value = resp
            mock_post.return_value = resp
            for scraper in get_active_scrapers():
                res = scraper.scrape(keywords=["test"])
                self.assertIsInstance(res, list)


if __name__ == "__main__":
    unittest.main()
