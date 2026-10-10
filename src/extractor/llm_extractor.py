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

from src.extractor.gemini_client import (
    BaseGeminiService,
    DailyQuotaExhaustedError,
    is_daily_quota_exhausted,
    is_transient_error,
    calculate_backoff_sleep,
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    DEFAULT_RATE_LIMIT_DELAY,
    MAX_RETRIES,
    INITIAL_BACKOFF,
    _UNSET,
)
from src.extractor.schemas import ExtractedJob
from src.extractor.text_sanitizer import build_sanitized_job_prompt
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


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


class GeminiExtractor(BaseGeminiService):
    """
    Client wrapper for Gemini API structured skill extraction.
    Enforces exponential backoff, jitter, rate-limit pauses, and Pydantic validation.
    """


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

        current_model = self.model
        consecutive_503 = 0
        backoff = INITIAL_BACKOFF

        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                self._last_call_time = time.monotonic()
                response = self.client.models.generate_content(
                    model=current_model,
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

                is_503 = "503" in err_str or "service unavailable" in err_str.lower() or "unavailable" in err_str.lower()
                is_rate_limit = (
                    "429" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "rate limit" in err_str.lower()
                    or "quota" in err_str.lower()
                )
                is_transient = is_503 or is_rate_limit or "timeout" in err_str.lower()

                if is_503:
                    consecutive_503 += 1
                    # Fallback model: if gemini-3.8-flash returns 503 after 2 attempts, fall back to gemini-2.5-flash
                    if consecutive_503 >= 2 and current_model == "gemini-3.8-flash":
                        logger.warning(
                            f"[GeminiExtractor] Model {current_model} received {consecutive_503} consecutive 503 errors. "
                            f"Falling back to {FALLBACK_MODEL} for attempt {attempt + 1}."
                        )
                        current_model = FALLBACK_MODEL

                if is_transient and attempt < MAX_RETRIES:
                    if is_503:
                        wait_schedule = [5.0, 10.0, 20.0]
                        base_wait = wait_schedule[min(consecutive_503 - 1, len(wait_schedule) - 1)]
                        jitter = random.uniform(0.5, 2.0)
                        sleep_time = base_wait + jitter
                    else:
                        jitter = random.uniform(0.2, 1.0)
                        sleep_time = backoff + jitter
                        backoff *= 2.0

                    logger.warning(
                        f"[GeminiExtractor] Transient error ({err_str[:120]}). "
                        f"Retrying in {sleep_time:.1f}s (attempt {attempt}/{MAX_RETRIES}, model: {current_model})..."
                    )
                    time.sleep(sleep_time)
                    continue

                if is_503:
                    logger.warning(
                        f"[GeminiExtractor] Retries exhausted for job '{fallback_title}' due to 503 Service Unavailable. "
                        "Proceeding to next job."
                    )
                else:
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
        except Exception as e:
            logger.warning(f"[BatchExtractor] Unexpected error extracting job {job_id}: {e}. Skipping.")
            extracted = None

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
