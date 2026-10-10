# src/extractor/llm_extractor.py
"""
Gemini LLM Extractor using Google GenAI SDK (Free Tier).
Extracts canonical skills, tools, cloud platforms, and experience levels
into structured Pydantic ExtractedJob models with exponential backoff and rate limiting.
"""
from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import Any, Dict, List, Optional, Union

from google import genai
from google.genai import types

from src.extractor.schemas import ExtractedJob
from src.extractor.text_sanitizer import build_sanitized_job_prompt
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)

_UNSET = object()
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = "gemini-1.5-flash"
DEFAULT_RATE_LIMIT_DELAY = 4.0  # Safe for 15 RPM free tier
MAX_RETRIES = 4
INITIAL_BACKOFF = 2.0


class DailyQuotaExhaustedError(Exception):
    """Raised when the Gemini free-tier daily request quota is completely exhausted."""
    pass


def is_daily_quota_exhausted(err_str: str) -> bool:
    """
    Detects whether an error message indicates the daily quota
    (e.g. GenerateRequestsPerDayPerProjectPerModel or long retry-after delay)
    has been exhausted, rather than a transient burst/RPM limit.
    """
    err_lower = err_str.lower()
    if "generaterequestsperday" in err_lower:
        return True
    if "quota" in err_lower or "exhausted" in err_lower or "429" in err_lower or "retry" in err_lower:
        if "per day" in err_lower or "daily" in err_lower:
            return True
        if re.search(r"retry\s+(?:in|after)\s+\d+\s*(?:h|hr|hour)", err_lower):
            return True
        min_match = re.search(r"retry\s+(?:in|after)\s+(\d+)\s*(?:m|min|minute)", err_lower)
        if min_match:
            try:
                if int(min_match.group(1)) >= 1:
                    return True
            except ValueError:
                return True
    return False


NON_TECH_ROLE_TERMS = [
    "sales", "economic", "research", "hr", "human resource",
    "accountant", "accounting", "finance", "financial", "marketing",
    "admin", "administrative", "customer service", "telesales", "recruiter",
    "recruitment", "legal", "purchasing", "procurement", "auditor",
    "audit", "cashier", "clerk", "receptionist", "content creator",
    "copywriter", "office manager",
    # Thai terms
    "ฝ่ายขาย", "บัญชี", "การเงิน", "ทรัพยากรบุคคล", "ธุรการ", "จัดซื้อ",
]

CORE_TECH_TERMS = [
    "developer", "engineer", "programmer", "data", "devops",
    "cloud", "ai", "software", "backend", "frontend", "fullstack",
    "full stack", "architect", "machine learning", "ml", "qa",
    "tester", "sre", "database", "dba", "infrastructure", "security",
    "sysadmin", "cyber",
    # Thai terms
    "นักพัฒนา", "โปรแกรมเมอร์", "วิศวกร", "ไอที",
]


def is_tech_job(job_or_title: Union[Dict[str, Any], str], description: Optional[str] = None) -> bool:
    """
    Quick heuristic filter to skip obvious non-tech jobs (e.g. Sales, Economic Research, HR, Accountant)
    unless they match core tech keywords (developer, engineer, programmer, data, devops, cloud, ai).
    """
    if isinstance(job_or_title, dict):
        title = str(job_or_title.get("title") or "").strip()
        if not description:
            description = str(job_or_title.get("teaser") or job_or_title.get("description") or "").strip()
    else:
        title = str(job_or_title or "").strip()

    t_lower = title.lower()

    has_non_tech = any(
        re.search(rf"\b{re.escape(k)}\b", t_lower) or (k in t_lower and not k.isascii())
        for k in NON_TECH_ROLE_TERMS
    )
    if not has_non_tech:
        return True

    # If title has non-tech keywords, keep only if it explicitly matches core tech keywords
    has_core_tech = any(
        re.search(rf"\b{re.escape(k)}\b", t_lower) or (k in t_lower and not k.isascii())
        for k in CORE_TECH_TERMS
    )
    return bool(has_core_tech)


EXTRACTION_SYSTEM_INSTRUCTION = """You are an expert technical recruiter and software engineering systems architect analyzing the Thailand tech job market.
Analyze the provided Job Description (JD) and extract canonical, standardized technical metadata into the required schema.

Extraction Rules:
1. Canonicalize naming: Normalize all skill/tool names to industry standard casing (e.g. 'Python', 'FastAPI', 'PostgreSQL', 'Redis', 'Docker', 'AWS', 'Kubernetes', 'Apache Kafka', 'Airflow', 'Go', 'TypeScript').
2. Accurate Categorization:
   - must_have_skills: Core programming languages and mandatory engineering proficiencies.
   - nice_to_have_skills: Bonus, preferred, or optional technical competencies.
   - frameworks: Application frameworks and libraries (e.g. FastAPI, Django, React, Express, Spring Boot).
   - databases: SQL, NoSQL, caches, and warehouses (e.g. PostgreSQL, Redis, MongoDB, MySQL, BigQuery).
   - cloud_infra: Cloud platforms and DevOps/infra tooling (e.g. AWS, GCP, Azure, Docker, Kubernetes, Terraform).
   - tools: Message brokers, CI/CD, orchestration, and developer utilities (e.g. Git, Kafka, GitHub Actions, Airflow).
3. Experience level classification:
   - 'Entry' (0-1 years / New Grad)
   - 'Junior' (1-3 years)
   - 'Mid' (3-5 years)
   - 'Senior' (5+ years)
   - 'Lead' (Staff, Principal, Team Lead)
   - 'Unknown' (If unspecified)
4. Strict truthfulness: Only extract skills that are explicitly mentioned or clearly required in the text.
"""


class GeminiExtractor:
    """
    Client wrapper for Gemini API structured skill extraction.
    Enforces exponential backoff, jitter, rate-limit pauses, and Pydantic validation.
    """

    def __init__(
        self,
        api_key: Any = _UNSET,
        model: Optional[str] = None,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        client: Any = _UNSET,
        model_name: Optional[str] = None,
    ):
        if api_key is _UNSET:
            self.api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        else:
            self.api_key = (api_key or "").strip()

        chosen_model = (model_name or model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)).strip()
        self.model = chosen_model
        self.model_name = chosen_model
        self.rate_limit_delay = rate_limit_delay
        self._last_call_time: float = 0.0

        if client is not _UNSET:
            self.client = client
        elif self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def _throttle(self) -> None:
        """Enforces a minimum pause between API calls to honor free tier RPM quotas."""
        if self._last_call_time > 0:
            elapsed = time.monotonic() - self._last_call_time
            sleep_needed = self.rate_limit_delay - elapsed
            if sleep_needed > 0:
                time.sleep(sleep_needed)

    def extract_job(
        self,
        job_text: str,
        fallback_title: str = "",
        fallback_company: str = "",
    ) -> Optional[ExtractedJob]:
        """
        Extracts structured tech stack data from sanitized job text.
        Returns ExtractedJob on success, or None on failure after retries.
        Raises DailyQuotaExhaustedError if 429 indicates daily limit exhausted.
        """
        if not self.client:
            logger.warning("[GeminiExtractor] No API key configured; skipping extraction.")
            return None

        prompt = f"Please extract the technical specifications from this job posting:\n\n{job_text}"

        config = types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ExtractedJob,
            temperature=0.1,
        )

        backoff = INITIAL_BACKOFF
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                self._last_call_time = time.monotonic()
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )

                extracted: Optional[ExtractedJob] = None
                # Check parsed object first
                if hasattr(response, "parsed") and isinstance(response.parsed, ExtractedJob):
                    extracted = response.parsed
                elif hasattr(response, "text") and response.text:
                    extracted = ExtractedJob.model_validate_json(response.text)

                if extracted is not None:
                    # Fill fallback metadata if missing from model output
                    if not extracted.job_title and fallback_title:
                        extracted.job_title = fallback_title
                    if not extracted.company and fallback_company:
                        extracted.company = fallback_company
                    return extracted

                logger.warning(f"[GeminiExtractor] Attempt {attempt}: Empty or unparseable response.")

            except Exception as e:
                err_str = str(e)
                if is_daily_quota_exhausted(err_str):
                    logger.error(
                        f"[GeminiExtractor] Gemini daily quota exhausted ({err_str[:160]}). "
                        "Failing fast without retrying."
                    )
                    raise DailyQuotaExhaustedError(f"Daily quota exhausted: {err_str}") from e

                is_rate_limit = (
                    "429" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "rate limit" in err_str.lower()
                    or "quota" in err_str.lower()
                )
                is_transient = is_rate_limit or "503" in err_str or "timeout" in err_str.lower()

                if is_transient and attempt < MAX_RETRIES:
                    jitter = random.uniform(0.2, 1.0)
                    sleep_time = backoff + jitter
                    logger.warning(
                        f"[GeminiExtractor] Transient error ({err_str[:120]}). "
                        f"Retrying in {sleep_time:.1f}s (attempt {attempt}/{MAX_RETRIES})..."
                    )
                    time.sleep(sleep_time)
                    backoff *= 2.0
                    continue

                logger.error(f"[GeminiExtractor] Error extracting job (attempt {attempt}): {e}")
                if not is_transient:
                    break

        return None


def process_unprocessed_jobs(
    db: DatabaseManager,
    extractor: Optional[GeminiExtractor] = None,
    limit: Optional[int] = None,
    turso: Optional[Any] = None,
) -> int:
    """
    Fetches un-extracted jobs from database, applies heuristic pre-filtering for non-tech roles,
    sanitizes text, invokes Gemini, and stores ExtractedJob records into skills_extracted table.
    Synchronizes extracted skills to Turso cloud database if available.
    Fails fast gracefully on DailyQuotaExhaustedError.
    Returns the count of successfully extracted jobs.
    """
    if extractor is None:
        extractor = GeminiExtractor()

    # If limit is specified, fetch more candidates so non-tech skipped jobs don't starve the limit
    fetch_limit = (limit * 3) if (limit is not None and limit > 0) else None
    unprocessed = db.get_unprocessed_jobs(limit=fetch_limit)
    if not unprocessed:
        logger.info("[BatchExtractor] No unprocessed jobs in queue.")
        return 0

    target_desc = f"up to {limit}" if limit else "all"
    logger.info(f"[BatchExtractor] Processing {target_desc} tech job(s) from {len(unprocessed)} candidate(s) in queue...")
    success_count = 0

    for idx, job in enumerate(unprocessed, start=1):
        if limit is not None and success_count >= limit:
            logger.info(f"[BatchExtractor] Reached extraction limit ({limit}). Stopping batch.")
            break

        job_id = str(job.get("id"))
        title = job.get("title", "")
        company = job.get("company", "")

        # Heuristic pre-filter for non-tech jobs
        if not is_tech_job(job):
            logger.info(f"[BatchExtractor] [{idx}/{len(unprocessed)}] Skipping non-tech job: '{title}' ({company})")
            empty_record = ExtractedJob(
                job_title=title,
                company=company,
                experience_level="Non-Tech",
            )
            db.save_extracted_skills(job_id, empty_record)
            continue

        logger.info(f"[BatchExtractor] [{idx}/{len(unprocessed)}] Extracting skills for: '{title}' ({company})")

        sanitized_prompt = build_sanitized_job_prompt(job)
        try:
            extracted = extractor.extract_job(
                job_text=sanitized_prompt,
                fallback_title=title,
                fallback_company=company,
            )
        except DailyQuotaExhaustedError as e:
            logger.warning(
                f"[BatchExtractor] Gemini daily quota exhausted ({e}). "
                "Terminating extraction batch gracefully and proceeding with remaining pipeline."
            )
            break

        if extracted:
            db.save_extracted_skills(job_id, extracted)
            if turso:
                turso.sync_extracted_skills({
                    "job_id": job_id,
                    "extracted": extracted,
                })
            success_count += 1
            logger.info(f"[BatchExtractor] Successfully saved skills for job {job_id} ({len(extracted.all_tech_stack)} tech tags).")
        else:
            logger.warning(f"[BatchExtractor] Failed to extract skills for job {job_id}. Skipping.")

    logger.info(f"[BatchExtractor] Completed batch: {success_count} jobs extracted.")
    return success_count
