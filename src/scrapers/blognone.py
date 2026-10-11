# src/scrapers/blognone.py
"""
Blognone Jobs scraper targeting Thailand's premier tech and IT developer job board.
Extracts job listings from Blognone's server-rendered state and job postings schema.
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from src.models import RawJob
from src.scrapers.base import BaseScraper
from src.extractor.salary_parser import parse_salary

logger = logging.getLogger("JHunt.Scrapers.Blognone")


class BlognoneScraper(BaseScraper):
    """
    Scraper for jobs.blognone.com catering to Thailand software engineering and tech roles.
    Parses embedded SSR state and schema.org JobPosting metadata into normalized RawJob items.
    """

    BASE_URL = "https://jobs.blognone.com"
    SEARCH_URL = "https://jobs.blognone.com/search"

    PAGE_SIZE = 15
    MAX_PAGES = 3
    REQUEST_DELAY = 0.5

    def __init__(self, fetch_details: bool = True):
        super().__init__()
        self.fetch_details = fetch_details
        self.session = self._build_session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
        })

    def _extract_ssr_json(self, html_text: str) -> Optional[Dict[str, Any]]:
        """Extracts and parses the embedded state JSON from the Blognone HTML page."""
        script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html_text, re.DOTALL)
        for s in script_matches:
            if "jobs-api.blognone.com" in s:
                start = s.find('{"api"')
                if start == -1:
                    start = s.find('{')
                if start != -1:
                    raw = s[start:].strip()
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        pass

        pattern = r'(\{"api":\{"endpoint":"https:(?:\\u002F|/){2}jobs-api\.blognone\.com".*?\})\s*</script>'
        match = re.search(pattern, html_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _fetch_page(self, keyword: str, page: int = 1) -> Optional[Dict[str, Any]]:
        """Requests the search results page and extracts the structured JSON state."""
        params = {"q": keyword, "page": page}
        try:
            response = self.session.get(self.SEARCH_URL, params=params, timeout=self.TIMEOUT)
            response.raise_for_status()
            return self._extract_ssr_json(response.text)
        except requests.exceptions.RequestException as e:
            logger.warning(f"[Blognone] Search request failed (keyword='{keyword}', page={page}): {e}")
            return None
        except Exception as e:
            logger.warning(f"[Blognone] Error processing page (keyword='{keyword}', page={page}): {e}")
            return None

    def _fetch_detail_description(self, job_url: str) -> Optional[str]:
        """
        Attempts to fetch the job detail page and parse JobPosting JSON-LD or meta description.
        Returns cleaned text description, or None if unavailable.
        """
        if not self.fetch_details or not job_url:
            return None

        try:
            response = self.session.get(job_url, timeout=self.TIMEOUT)
            response.raise_for_status()
            text = response.text

            # 1. Check for schema.org JobPosting JSON-LD
            ld_matches = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', text, re.DOTALL)
            for ld_text in ld_matches:
                try:
                    data = json.loads(ld_text)
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        raw_desc = data.get("description")
                        if raw_desc:
                            # Strip HTML tags
                            clean = re.sub(r"<[^>]+>", " ", raw_desc)
                            clean = html.unescape(clean)
                            clean = re.sub(r"\s+", " ", clean).strip()
                            if clean:
                                return clean
                except Exception:
                    continue

            # 2. Check for og:description meta tag
            meta_match = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', text)
            if meta_match:
                content = html.unescape(meta_match.group(1)).strip()
                if content:
                    return content

        except Exception as e:
            logger.debug(f"[Blognone] Detail fetch failed for {job_url}: {e}")

        return None

    def _format_salary(self, item: Dict[str, Any]) -> Optional[str]:
        """Formats the salary range if disclosed."""
        try:
            s_min = float(item.get("salary_min") or 0)
            s_max = float(item.get("salary_max") or 0)
            fmt = str(item.get("salary_display_format") or "").strip()
            if s_min > 0 and s_max > 0:
                return f"{s_min:,.0f} - {s_max:,.0f} THB"
            elif s_min > 0:
                return f"From {s_min:,.0f} THB"
            elif s_max > 0:
                return f"Up to {s_max:,.0f} THB"
            elif fmt and fmt.upper() != "NEGOTIABLE":
                return fmt
        except (ValueError, TypeError):
            pass
        return None

    def _parse_job(self, item: Dict[str, Any]) -> Optional[RawJob]:
        """Converts Blognone listing record into normalized RawJob instance."""
        slug = str(item.get("slug") or "").strip()
        title = str(item.get("title") or "").strip()
        if not slug or not title:
            return None

        job_id = slug if slug.startswith("blognone_") else f"blognone_{slug}"

        company_info = item.get("company") or {}
        company_name = (
            company_info.get("name_en")
            or company_info.get("name_th")
            or company_info.get("slug")
            or ""
        ).strip()
        company_slug = company_info.get("slug", "")

        url = f"{self.BASE_URL}/company/{company_slug}/job/{slug}" if company_slug else f"{self.BASE_URL}/job/{slug}"

        location_parts = [
            str(item.get("district") or "").strip(),
            str(item.get("province") or "").strip(),
        ]
        location = ", ".join(filter(None, location_parts)) or None

        salary = self._format_salary(item)
        work_type = str(item.get("type") or "").strip() or None
        skills = [str(s).strip() for s in (item.get("skills") or []) if str(s).strip()]
        posted_at = str(item.get("updated") or "").strip() or None

        # Build fallback description from level, skills, and work_type
        level = str(item.get("level") or "").strip()
        summary_lines = [f"Position: {title}", f"Company: {company_name}"]
        if level:
            summary_lines.append(f"Seniority Level: {level}")
        if work_type:
            summary_lines.append(f"Employment Type: {work_type}")
        if skills:
            summary_lines.append(f"Technical Stack: {', '.join(skills)}")
        fallback_desc = "\n".join(summary_lines)

        # Attempt to retrieve detail description if available
        detail_desc = self._fetch_detail_description(url)
        description = detail_desc if detail_desc else fallback_desc

        min_salary, max_salary, currency = parse_salary(salary, description)

        return RawJob(
            id=job_id,
            title=title,
            company=company_name or "Tech Company",
            location=location,
            salary=salary,
            work_type=work_type,
            description=description,
            url=url,
            source="blognone",
            posted_at=posted_at,
            tags=skills,
            teaser=fallback_desc,
            min_salary=min_salary,
            max_salary=max_salary,
            currency=currency,
        )

    def scrape(self, keywords: Optional[List[str]] = None, limit: int = 50) -> List[RawJob]:
        """Scrapes tech positions matching keywords from Blognone Jobs."""
        search_keywords = keywords if keywords is not None else ["developer", "data"]
        jobs: List[RawJob] = []
        seen_ids: set[str] = set()

        for kw in search_keywords:
            kw = kw.strip()
            if not kw:
                continue

            logger.info(f"[Blognone] Searching: '{kw}'")
            keyword_count = 0

            for page in range(1, self.MAX_PAGES + 1):
                if len(jobs) >= limit:
                    break

                if page > 1 or kw != search_keywords[0]:
                    time.sleep(self.REQUEST_DELAY)

                payload = self._fetch_page(kw, page=page)
                if not payload:
                    break

                items = payload.get("r", {}).get("data", {}).get("jobs", [])
                if not items:
                    break

                for item in items:
                    if len(jobs) >= limit:
                        break

                    job = self._parse_job(item)
                    if not job or job.id in seen_ids:
                        continue

                    seen_ids.add(job.id)
                    jobs.append(job)
                    keyword_count += 1

                try:
                    jobs_count = int(payload.get("r", {}).get("data", {}).get("jobs_count") or 0)
                except (ValueError, TypeError):
                    jobs_count = 0
                if page * self.PAGE_SIZE >= jobs_count:
                    break

            logger.info(f"[Blognone] '{kw}' -> {keyword_count} new job(s)")
            if len(jobs) >= limit:
                break

        logger.info(f"[Blognone] Total unique jobs: {len(jobs)}")
        return jobs
