# src/scrapers/jobthai.py
"""
JobThai scraper targeting Software Engineering and IT Programmer job positions.
Communicates via JobThai's GraphQL API service with resilient fallback handling
for banner-only and missing-description job formats.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from src.models import RawJob
from src.scrapers.base import BaseScraper
from src.extractor.salary_parser import parse_salary

logger = logging.getLogger("JHunt.Scrapers.JobThai")


class JobThaiScraper(BaseScraper):
    """
    Scraper for JobThai (www.jobthai.com) IT / Software Engineering categories.
    Queries JobThai's public GraphQL API for search listings and detailed requirements.
    """

    GRAPHQL_URL = "https://api.jobthai.com/v1/graphql"
    JOB_URL = "https://www.jobthai.com/en/company/job/{job_id}"

    SEARCH_HASH = "8c21badbcb9da924a3ed99c6d2f16d34758a045523495b4458f2a970c70cd0b2"

    SEARCH_QUERY = """
    query ($searchJobsFilter: JobsSearchFilter, $orderBy: JobOrderBy, $staticDataVersion: StaticDataVersion) {
      searchJobs(filter: $searchJobsFilter, orderBy: $orderBy, staticDataVersion: $staticDataVersion) {
        data {
          total
          data {
            id
            companyID
            jobTitle
            companyName
            salary
            updatedAt
            province { name }
            district { name }
            tags
          }
        }
      }
    }
    """

    RAW_DATA_QUERY = """
    query ($id: Int!, $l: Language) {
      getJobRawData(id: $id, l: $l) {
        data {
          properties
          description
          benefit
          salary
        }
      }
    }
    """

    PAGE_SIZE = 20
    MAX_PAGES = 3
    REQUEST_DELAY = 0.5

    def __init__(self, fetch_details: bool = True):
        super().__init__()
        self.fetch_details = fetch_details
        self.session = self._build_session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "apollo-require-preflight": "true",
            "Accept": "application/json",
        })

    def _search_page(self, keyword: str, page: int = 1) -> Optional[Dict[str, Any]]:
        """
        Queries JobThai GraphQL searchJobs endpoint using persisted query or fallback POST.
        """
        variables = {
            "searchJobsFilter": {"keyword": keyword, "l": "en", "page": page},
            "orderBy": "UPDATED_AT_DESC",
            "staticDataVersion": {},
        }

        # 1. Try GET with Persisted Query (low bandwidth, CDN friendly)
        get_params = {
            "variables": json.dumps(variables),
            "extensions": json.dumps({
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.SEARCH_HASH,
                }
            }),
        }

        try:
            resp = self.session.get(self.GRAPHQL_URL, params=get_params, timeout=self.TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and "searchJobs" in data["data"]:
                    return data["data"]["searchJobs"]
        except requests.exceptions.RequestException as e:
            logger.debug(f"[JobThai] GET persisted query failed, trying POST fallback: {e}")

        # 2. Fallback to POST with direct query
        try:
            payload = {
                "query": self.SEARCH_QUERY,
                "variables": variables,
            }
            resp = self.session.post(self.GRAPHQL_URL, json=payload, timeout=self.TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("searchJobs")
        except requests.exceptions.RequestException as e:
            logger.warning(f"[JobThai] Search failed (keyword='{keyword}', page={page}): {e}")
            return None
        except Exception as e:
            logger.warning(f"[JobThai] Error processing search (keyword='{keyword}', page={page}): {e}")
            return None

    def _fetch_job_description(self, job_id_int: int) -> str:
        """
        Queries getJobRawData for the full text description and required properties.
        Handles missing descriptions or banner-only formats gracefully without raising.
        """
        if not self.fetch_details or job_id_int <= 0:
            return ""

        try:
            payload = {
                "query": self.RAW_DATA_QUERY,
                "variables": {"id": job_id_int, "l": "en"},
            }
            resp = self.session.post(self.GRAPHQL_URL, json=payload, timeout=self.TIMEOUT)
            if resp.status_code != 200:
                return ""

            raw_data = resp.json().get("data", {}).get("getJobRawData", {}).get("data")
            if not raw_data or not isinstance(raw_data, dict):
                return ""

            desc_parts: List[str] = []
            main_desc = str(raw_data.get("description") or "").strip()
            if main_desc:
                desc_parts.append(main_desc)

            properties = raw_data.get("properties") or []
            if isinstance(properties, list):
                props_clean = [str(p).strip() for p in properties if str(p).strip()]
                if props_clean:
                    desc_parts.append("Qualifications:\n" + "\n".join(f"- {p}" for p in props_clean))

            return "\n\n".join(desc_parts)
        except Exception as e:
            logger.debug(f"[JobThai] Detail fetch exception for job {job_id_int} (graceful fallback): {e}")
            return ""

    def _parse_job(
        self,
        item: Dict[str, Any],
        known_ids: Optional[set[str]] = None,
    ) -> Optional[RawJob]:
        """Converts JobThai GraphQL record into normalized RawJob instance."""
        raw_id = item.get("id")
        if not raw_id:
            return None

        try:
            numeric_id = int(raw_id)
        except (ValueError, TypeError):
            numeric_id = 0

        job_id_str = str(raw_id).strip()
        job_id = job_id_str if job_id_str.startswith("jobthai_") else f"jobthai_{job_id_str}"

        title = str(item.get("jobTitle") or "").strip()
        company = str(item.get("companyName") or "").strip()
        if not title or not company:
            return None

        # Location extraction
        prov = (item.get("province") or {}).get("name") if isinstance(item.get("province"), dict) else ""
        dist = (item.get("district") or {}).get("name") if isinstance(item.get("district"), dict) else ""
        location = ", ".join(filter(None, [dist, prov])) or None

        salary = str(item.get("salary") or "").strip() or None
        posted_at = str(item.get("updatedAt") or "").strip() or None
        tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()]

        url = self.JOB_URL.format(job_id=job_id_str)

        # Retrieve job description, handling banner-only / missing formats gracefully
        if known_ids and job_id in known_ids:
            description = ""
        elif self.fetch_details:
            time.sleep(self.REQUEST_DELAY)
            description = self._fetch_job_description(numeric_id)
        else:
            description = ""
        min_salary, max_salary, currency = parse_salary(salary, description)

        return RawJob(
            id=job_id,
            title=title,
            company=company,
            location=location,
            salary=salary,
            description=description,
            url=url,
            source="jobthai",
            posted_at=posted_at,
            tags=tags,
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
        """Scrapes tech jobs matching keywords from JobThai."""
        search_keywords = keywords if keywords is not None else ["python", "programmer", "developer"]
        jobs: List[RawJob] = []
        seen_ids: set[str] = set()

        for kw in search_keywords:
            kw = kw.strip()
            if not kw:
                continue

            logger.info(f"[JobThai] Searching: '{kw}'")
            keyword_count = 0

            for page in range(1, self.MAX_PAGES + 1):
                if keyword_count >= limit:
                    break

                if page > 1 or kw != search_keywords[0]:
                    time.sleep(self.REQUEST_DELAY)

                search_res = self._search_page(kw, page=page)
                if not search_res:
                    break

                search_data = search_res.get("data")
                if isinstance(search_data, list):
                    items = search_data
                    total = len(items)
                elif isinstance(search_data, dict):
                    items = search_data.get("data", [])
                    try:
                        total = int(search_data.get("total") or 0)
                    except (ValueError, TypeError):
                        total = 0
                else:
                    items = []
                    total = 0

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

                if page * self.PAGE_SIZE >= total:
                    break

            logger.info(f"[JobThai] '{kw}' -> {keyword_count} new job(s)")

        logger.info(f"[JobThai] Total unique jobs: {len(jobs)}")
        return jobs
