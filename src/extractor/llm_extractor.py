# src/extractor/llm_extractor.py
"""
Gemini LLM Extractor using Google GenAI SDK (Free Tier).
Extracts canonical skills, tools, cloud platforms, and experience levels
into structured Pydantic ExtractedJob models with exponential backoff and rate limiting.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from google.genai import types

from src.extractor.gemini_client import BaseGeminiService, DailyQuotaExhaustedError
from src.extractor.schemas import BatchExtractedJob, ExtractedJob
from src.extractor.text_cleaner import clean_job_description
from src.extractor.text_sanitizer import build_sanitized_job_prompt

if TYPE_CHECKING:
    # Annotation only: a runtime import closes the cycle storage.db -> extractor -> storage.db.
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


EXTRACTION_SYSTEM_INSTRUCTION = """You are a technical recruiter analyzing job postings from the Thailand tech market.
You receive a JSON array of postings. Each has an integer "id", a "title", a "company" and a "description".
Return one entry per posting, copying its "id" exactly, with canonical technical metadata in the required schema.
Never merge, skip or reorder ids: an entry whose id is not in the input is discarded.

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
4. Strict truthfulness: Only extract skills that are explicitly mentioned or clearly required in that posting's own text.
"""

# One request covers this many jobs. The free tier allows ~20 requests/day per model,
# so 30 jobs cost 2 requests instead of 30.
BATCH_SIZE = 15
MAX_DESCRIPTION_CHARS = 1500  # keeps a full batch well under the model's input budget


class GeminiExtractor(BaseGeminiService):
    """Batch skill extraction over Gemini structured output, with the base class's retries and circuit breaker."""

    def extract_batch(self, jobs: List[Dict[str, Any]]) -> Dict[str, ExtractedJob]:
        """
        Extracts up to BATCH_SIZE jobs in one request.
        Returns {job_id: ExtractedJob} for the jobs the model answered; unanswered
        jobs are absent and stay in the queue for the next run.
        Raises DailyQuotaExhaustedError when the daily quota is gone or the circuit is open.
        """
        if not jobs:
            return {}

        payload = []
        for i, job in enumerate(jobs):
            raw_desc = job.get("description")
            if raw_desc is not None and str(raw_desc).strip():
                desc_text = str(raw_desc)
            else:
                desc_text = build_sanitized_job_prompt(job, max_chars=MAX_DESCRIPTION_CHARS)
            cleaned_desc = clean_job_description(desc_text, max_chars=MAX_DESCRIPTION_CHARS)
            payload.append({
                "id": i,
                "title": str(job.get("title") or ""),
                "company": str(job.get("company") or ""),
                "description": cleaned_desc,
            })
        config = types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=list[BatchExtractedJob],
            temperature=0.1,
        )
        items = self._generate(json.dumps(payload, ensure_ascii=False), config, list[BatchExtractedJob]) or []

        results: Dict[str, ExtractedJob] = {}
        for item in items:
            if not 0 <= item.id < len(jobs):
                logger.warning(f"[GeminiExtractor] Discarding answer for unknown id {item.id}.")
                continue
            job = jobs[item.id]
            job_id = str(job["id"])
            if job_id in results:
                continue
            extracted = ExtractedJob.model_validate(item.model_dump(exclude={"id"}))
            extracted.job_title = extracted.job_title or str(job.get("title") or "")
            extracted.company = extracted.company or str(job.get("company") or "")
            results[job_id] = extracted
        return results


def process_unprocessed_jobs(
    db: DatabaseManager,
    extractor: Optional[GeminiExtractor] = None,
    limit: Optional[int] = None,
    turso: Optional[Any] = None,
) -> int:
    """
    Extracts skills for queued jobs in batches of BATCH_SIZE per Gemini request.
    Non-tech jobs are marked 'Non-Tech' without an API call. `limit` caps how many
    tech jobs are sent this run. Stops cleanly on DailyQuotaExhaustedError.
    Returns the number of jobs extracted.
    """
    if extractor is None:
        extractor = GeminiExtractor()

    # Fetch extra candidates so non-tech jobs don't starve the limit.
    fetch_limit = (limit * 3) if (limit is not None and limit > 0) else None
    unprocessed = db.get_unprocessed_jobs(limit=fetch_limit)
    if not unprocessed:
        logger.info("[BatchExtractor] No unprocessed jobs in queue.")
        return 0

    tech_jobs: List[Dict[str, Any]] = []
    for job in unprocessed:
        if is_tech_job(job):
            tech_jobs.append(job)
            continue
        title, company = job.get("title", ""), job.get("company", "")
        logger.info(f"[BatchExtractor] Skipping non-tech job: '{title}' ({company})")
        db.save_extracted_skills(
            str(job["id"]),
            ExtractedJob(job_title=title, company=company, experience_level="Non-Tech"),
        )

    if limit is not None and limit > 0:
        tech_jobs = tech_jobs[:limit]
    batches = [tech_jobs[i:i + BATCH_SIZE] for i in range(0, len(tech_jobs), BATCH_SIZE)]
    logger.info(f"[BatchExtractor] Extracting {len(tech_jobs)} tech job(s) in {len(batches)} request(s)...")

    success_count = 0
    for n, batch in enumerate(batches, start=1):
        try:
            results = extractor.extract_batch(batch)
        except DailyQuotaExhaustedError as e:
            logger.warning(f"[BatchExtractor] Gemini unavailable ({e}). Leaving the rest queued for the next run.")
            break
        except Exception as e:
            logger.warning(f"[BatchExtractor] Batch {n}/{len(batches)} failed unexpectedly ({e}); left queued.")
            continue

        for job_id, extracted in results.items():
            db.save_extracted_skills(job_id, extracted)
        if turso and results:
            turso.sync_extracted_skills(
                [{"job_id": job_id, "extracted": extracted} for job_id, extracted in results.items()]
            )
        success_count += len(results)
        missing = len(batch) - len(results)
        logger.info(
            f"[BatchExtractor] Batch {n}/{len(batches)}: {len(results)} extracted"
            + (f", {missing} unanswered and left queued." if missing else ".")
        )

    logger.info(f"[BatchExtractor] Completed: {success_count} job(s) extracted.")
    return success_count
