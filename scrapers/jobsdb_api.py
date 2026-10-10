# scrapers/jobsdb_api.py
"""
JobsDB Thailand scraper backed by SEEK's public JSON search API.

JobsDB runs on SEEK's platform, which exposes an unauthenticated search endpoint
returning everything the pipeline needs — location, salary and work type included —
in the search response itself. No browser, and no per-job detail fetch.
"""
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class JobsDBAPIScraper:
    SEARCH_URL = "https://th.jobsdb.com/api/jobsearch/v5/search"
    JOB_URL = "https://th.jobsdb.com/job/{job_id}"

    JOB_SCHEMA = {"id", "title", "company", "url"}
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def _validate_job(self, job: dict) -> bool:
        """Ensures every scraped job has the required non-empty fields."""
        return all(job.get(key) for key in self.JOB_SCHEMA)


    # Fixed query params. `sourcesystem` is required — the endpoint rejects
    # requests without it. `locale=en-TH` keeps location/work-type labels in
    # English so the EN terms in INCLUDE_LOCATIONS / EXCLUDE_SENIORITY match.
    BASE_PARAMS = {
        "siteKey": "TH-Main",
        "sourcesystem": "houston",
        "locale": "en-TH",
        "sortmode": "ListedDate",  # newest first — right ordering for a daily alert
    }

    PAGE_SIZE = 100
    MAX_PAGES = 5
    # Look back further than the daily cron interval so a skipped or failed run
    # doesn't create a permanent hole in coverage.
    DATE_RANGE_DAYS = 3
    REQUEST_DELAY = 1.0
    TIMEOUT = 15

    def __init__(self, keywords: list[str]):
        self.keywords = [kw.strip() for kw in keywords if kw.strip()]
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
        })
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    def _fetch_page(self, keyword: str, page: int) -> dict | None:
        """Returns the decoded JSON body, or None if the request/parse failed."""
        params = {
            **self.BASE_PARAMS,
            "keywords": keyword,
            "page": page,
            "pageSize": self.PAGE_SIZE,
            "dateRange": self.DATE_RANGE_DAYS,
        }
        try:
            response = self.session.get(self.SEARCH_URL, params=params, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[JobsDB] Request failed (keyword='{keyword}', page={page}): {e}")
        except ValueError as e:
            # A non-JSON body almost always means the endpoint moved or we got
            # served an error page. Loud, because it silently zeroes out the run.
            print(f"[JobsDB] Response was not JSON (keyword='{keyword}', page={page}): {e}")
        return None

    def _parse_job(self, item: dict) -> dict | None:
        """Maps one API record onto the pipeline's job dict. None if unusable."""
        job_id = str(item.get("id") or "").strip()
        if not job_id:
            return None

        locations = [
            loc.get("label", "") for loc in item.get("locations") or []
        ]

        # workTypes is the contract (Full time / Contract-Temp); workArrangements
        # carries On-site / Remote / Hybrid. Both are useful in the alert.
        work_bits = list(item.get("workTypes") or [])
        arrangements = (item.get("workArrangements") or {}).get("data") or []
        for arrangement in arrangements:
            label = (arrangement.get("label") or {}).get("text", "")
            if label:
                work_bits.append(label)

        advertiser = item.get("advertiser") or {}
        company = item.get("companyName") or advertiser.get("description") or ""

        job = {
            "id": job_id,
            "title": (item.get("title") or "").strip(),
            "company": company.strip(),
            "url": self.JOB_URL.format(job_id=job_id),
            "location": ", ".join(filter(None, locations)),
            "salary": (item.get("salaryLabel") or "").strip(),
            "work_type": " / ".join(dict.fromkeys(filter(None, work_bits))),
            # Consumed by the optional Gemini relevance pass. Free here — no
            # detail-page fetch required.
            "teaser": (item.get("teaser") or "").strip(),
            "bullet_points": [b for b in (item.get("bulletPoints") or []) if b],
            "listing_date": item.get("listingDate") or "",
        }

        if not self._validate_job(job):
            print(f"[JobsDB] Skipped malformed record (id={job_id!r}, title={job['title']!r})")
            return None
        return job

    def scrape(self) -> list[dict]:
        jobs: list[dict] = []
        seen_ids: set[str] = set()  # cross-keyword dedupe within this run

        for keyword in self.keywords:
            print(f"[JobsDB] Searching: '{keyword}'")
            keyword_count = 0

            for page in range(1, self.MAX_PAGES + 1):
                if page > 1 or keyword != self.keywords[0]:
                    time.sleep(self.REQUEST_DELAY)

                payload = self._fetch_page(keyword, page)
                if payload is None:
                    break

                items = payload.get("data") or []
                if not items:
                    break

                for item in items:
                    job = self._parse_job(item)
                    if job is None or job["id"] in seen_ids:
                        continue
                    seen_ids.add(job["id"])
                    jobs.append(job)
                    keyword_count += 1

                total = payload.get("totalCount", 0)
                if page * self.PAGE_SIZE >= total:
                    break

            print(f"[JobsDB] '{keyword}' -> {keyword_count} new job(s)")

        if not jobs:
            # Zero jobs is a legitimate outcome, but it is also exactly what an
            # endpoint change looks like. Say so rather than exiting quietly.
            print("[JobsDB] WARNING: no jobs returned. If this repeats, verify the "
                  f"search endpoint is still live: {self.SEARCH_URL}")

        print(f"[JobsDB] Total unique jobs: {len(jobs)}")
        return jobs


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()
    keywords = [
        kw.strip()
        for kw in os.getenv("SEARCH_KEYWORDS", "python developer,data engineer").split(",")
    ]

    scraper = JobsDBAPIScraper(keywords=keywords)
    results = scraper.scrape()

    print(f"\n--- {len(results)} job(s) ---")
    for job in results[:10]:
        print(f"\n[{job['id']}] {job['title']}")
        print(f"  company   : {job['company']}")
        print(f"  location  : {job['location']}")
        print(f"  salary    : {job['salary'] or '(not advertised)'}")
        print(f"  work_type : {job['work_type'] or '(unspecified)'}")
        print(f"  url       : {job['url']}")

    missing_salary = sum(1 for j in results if not j["salary"])
    print(f"\nJobs kept with no advertised salary: {missing_salary}/{len(results)}")
