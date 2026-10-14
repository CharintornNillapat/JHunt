# src/scrapers/jobsdb.py
"""
JobsDB Thailand scraper backed by SEEK's public JSON search API.
Implements BaseScraper to return normalized RawJob instances.
"""
from __future__ import annotations

import html
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from src.models import RawJob
from src.scrapers.base import BaseScraper
from src.extractor.salary_parser import parse_salary

logger = logging.getLogger("JHunt.Scrapers.JobsDB")


class JobsDBScraper(BaseScraper):
    """
    JobsDB Thailand scraper utilizing SEEK's public search endpoint.
    Retrieves job postings without browser automation and normalizes them into RawJob.
    """

    SEARCH_URL = "https://th.jobsdb.com/api/jobsearch/v5/search"
    DETAIL_URL = "https://th.jobsdb.com/api/jobsearch/v5/job/{job_id}"
    JOB_URL = "https://th.jobsdb.com/job/{job_id}"

    BASE_PARAMS = {
        "siteKey": "TH-Main",
        "sourcesystem": "houston",
        "locale": "en-TH",
        "sortmode": "ListedDate",  # newest first
    }

    PAGE_SIZE = 100
    MAX_PAGES = 5
    DATE_RANGE_DAYS = 3
    REQUEST_DELAY = 1.0

    def __init__(self, keywords: Optional[List[str]] = None, fetch_details: bool = True):
        super().__init__()
        self.default_keywords = [kw.strip() for kw in (keywords or []) if kw.strip()]
        self.fetch_details = fetch_details
        self.session = self._build_session()

    def _fetch_page(self, keyword: str, page: int) -> Optional[Dict[str, Any]]:
        """Fetches and decodes the JSON body for a given keyword and page number."""
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
            logger.warning(f"[JobsDB] Request failed (keyword='{keyword}', page={page}): {e}")
        except Exception as e:
            logger.warning(f"[JobsDB] Error fetching page (keyword='{keyword}', page={page}): {e}")
        return None

    def _fetch_detail_description(self, raw_id: str) -> Optional[str]:
        """
        Fetches full job description from SEEK's detail API endpoint for a job ID.
        Handles errors gracefully and falls back to None on any failure.
        """
        url = self.DETAIL_URL.format(job_id=raw_id)
        try:
            response = self.session.get(url, params=self.BASE_PARAMS, timeout=self.TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.warning(f"[JobsDB] Detail request failed (job_id='{raw_id}'): {e}")
            return None
        except Exception as e:
            logger.warning(f"[JobsDB] Error fetching detail (job_id='{raw_id}'): {e}")
            return None

        content_text: Optional[str] = None
        try:
            data = response.json()
            if isinstance(data, dict):
                candidate = (
                    data.get("jobDetail")
                    or data.get("description")
                    or data.get("content")
                    or (data.get("job") or {}).get("content")
                    or (data.get("jobDetail") or {}).get("job", {}).get("content")
                )
                if isinstance(candidate, dict):
                    candidate = (
                        candidate.get("content")
                        or candidate.get("text")
                        or candidate.get("description")
                    )
                if isinstance(candidate, str) and candidate.strip():
                    content_text = candidate.strip()
        except Exception:
            if response.text and (
                "<html" in response.text.lower()
                or "<body" in response.text.lower()
                or "<p>" in response.text.lower()
            ):
                content_text = response.text.strip()

        if not content_text:
            return None

        cleaned = re.sub(r"<[^>]+>", " ", content_text)
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or None

    def _parse_job(
        self,
        item: Dict[str, Any],
        known_ids: Optional[set[str]] = None,
    ) -> Optional[RawJob]:
        """Maps an API record into a normalized RawJob instance."""
        raw_id = str(item.get("id") or "").strip()
        if not raw_id:
            return None

        job_id = raw_id if raw_id.startswith("jobsdb_") else f"jobsdb_{raw_id}"

        locations = [
            loc.get("label", "") for loc in (item.get("locations") or [])
        ]

        work_bits = list(item.get("workTypes") or [])
        arrangements = (item.get("workArrangements") or {}).get("data") or []
        for arrangement in arrangements:
            label = (arrangement.get("label") or {}).get("text", "")
            if label:
                work_bits.append(label)

        advertiser = item.get("advertiser") or {}
        company = (item.get("companyName") or advertiser.get("description") or "").strip()
        title = (item.get("title") or "").strip()
        if not title or not company:
            return None

        teaser = (item.get("teaser") or "").strip()
        bullet_points = [str(b).strip() for b in (item.get("bulletPoints") or []) if str(b).strip()]

        # Combine teaser and bullet points for description if full body isn't available
        desc_parts = []
        if teaser:
            desc_parts.append(teaser)
        if bullet_points:
            desc_parts.append("\n".join(f"- {b}" for b in bullet_points))
        fallback_desc = "\n\n".join(desc_parts) if desc_parts else None

        if known_ids and job_id in known_ids:
            description = fallback_desc
        elif self.fetch_details:
            time.sleep(self.REQUEST_DELAY)
            detail_desc = self._fetch_detail_description(raw_id)
            description = detail_desc if detail_desc else fallback_desc
        else:
            description = fallback_desc

        listing_date = str(item.get("listingDate") or "").strip()
        salary_str = (item.get("salaryLabel") or "").strip() or None
        min_salary, max_salary, currency = parse_salary(salary_str, description)

        return RawJob(
            id=job_id,
            title=title,
            company=company,
            url=self.JOB_URL.format(job_id=raw_id),
            location=", ".join(filter(None, locations)) or None,
            salary=salary_str,
            work_type=" / ".join(dict.fromkeys(filter(None, work_bits))) or None,
            description=description,
            source="jobsdb",
            posted_at=listing_date or None,
            teaser=teaser or None,
            bullet_points=bullet_points,
            listing_date=listing_date or None,
            min_salary=min_salary,
            max_salary=max_salary,
            currency=currency,
        )

    def scrape(
        self,
        keywords: Optional[List[str]] = None,
        limit: int = 50,
        known_ids: Optional[set[str]] = None,
    ) -> List[RawJob]:
        """
        Executes search across keywords and returns deduplicated RawJob list.
        """
        search_keywords = keywords if keywords is not None else self.default_keywords
        if not search_keywords:
            search_keywords = ["python developer"]

        jobs: List[RawJob] = []
        seen_ids: set[str] = set()

        for keyword in search_keywords:
            keyword = keyword.strip()
            if not keyword:
                continue

            logger.info(f"[JobsDB] Searching: '{keyword}'")
            keyword_count = 0

            for page in range(1, self.MAX_PAGES + 1):
                if keyword_count >= limit:
                    break

                if page > 1 or keyword != search_keywords[0]:
                    time.sleep(self.REQUEST_DELAY)

                payload = self._fetch_page(keyword, page)
                if not payload:
                    break

                items = payload.get("data") or []
                if not items:
                    break

                for item in items:
                    if keyword_count >= limit:
                        break

                    job = self._parse_job(item, known_ids=known_ids)
                    if not job or job.id in seen_ids:
                        continue

                    seen_ids.add(job.id)
                    jobs.append(job)
                    keyword_count += 1

                try:
                    total = int(payload.get("totalCount") or 0)
                except (ValueError, TypeError):
                    total = 0
                if page * self.PAGE_SIZE >= total:
                    break

            logger.info(f"[JobsDB] '{keyword}' -> {keyword_count} new job(s)")

        if not jobs:
            logger.warning(
                f"[JobsDB] No jobs returned. Verify search endpoint: {self.SEARCH_URL}"
            )

        logger.info(f"[JobsDB] Total unique jobs: {len(jobs)}")
        return jobs
