# gemini_filter.py
"""
Semantic relevance filter for Thailand tech job postings.
Screening pass powered by Google GenAI SDK.
Drops non-engineering or excessive-seniority roles while failing open on API errors.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.extractor.gemini_client import DEFAULT_MODEL

logger = logging.getLogger(__name__)

BATCH_SIZE = 40
BATCH_DELAY = 4.0
KEEP_THRESHOLD = 4

PROMPT_HEADER = """You are screening job ads for a junior/entry-level software engineer in Thailand.

KEEP a job when it is a genuine engineering role in one of these areas, open to someone early in their career (0-3 years):
- Python development (backend, scripting, automation)
- Backend / full-stack engineering
- Data engineering, data analysis, data science
- Computer vision, machine learning, AI engineering

DROP a job when:
- It is not an engineering role — sales, marketing, admin, HR, recruitment, customer support, teaching.
- It requires substantial seniority: team lead, manager, architect, head of, or explicit demand for 5+ years of experience.
- It is unrelated technical work with no programming, e.g. hardware repair, IT helpdesk, network admin, QA manual testing.

For each job return:
- index: the job's index, exactly as given
- keep: true if it passes the rules above
- score: 0-10 confidence that this suits a junior software engineer
- reason: at most 15 words explaining the decision

Return one entry for every job in the list.

Jobs:
"""


class JobVerdict(BaseModel):
    index: int = Field(..., description="Index of the job in the batch")
    keep: bool = Field(..., description="Whether to keep the job")
    score: int = Field(default=KEEP_THRESHOLD, description="Confidence score 0-10")
    reason: str = Field(default="", description="Brief reason")


def _job_payload(index: int, job: Dict[str, Any]) -> Dict[str, Any]:
    """Minimum payload the model needs to score a job, saving tokens."""
    return {
        "index": index,
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "teaser": (job.get("teaser") or "")[:400],
        "bullet_points": (job.get("bullet_points") or [])[:4],
    }


def _call_gemini(
    client: genai.Client,
    batch_payload: List[Dict[str, Any]],
    model: str,
) -> Optional[List[JobVerdict]]:
    """Scores one batch using Google GenAI SDK. Returns parsed verdicts or None on failure."""
    prompt = PROMPT_HEADER + json.dumps(batch_payload, ensure_ascii=False, indent=1)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=list[JobVerdict],
        temperature=0.0,
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        if hasattr(response, "parsed") and isinstance(response.parsed, list):
            return response.parsed
        if hasattr(response, "text") and response.text:
            raw_list = json.loads(response.text)
            return [JobVerdict.model_validate(item) for item in raw_list]
    except Exception as e:
        logger.warning(f"[GeminiFilter] Batch scoring failed ({e}); failing open.")
    return None


def filter_semantically(jobs: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Drops jobs judged irrelevant to a junior software engineer.
    Fail-open by contract: disabled, unconfigured, or broken all return `jobs` unchanged.
    """
    if not config.get("gemini_enabled", False) or not jobs:
        return jobs

    api_key = (config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        logger.info("[GeminiFilter] GEMINI_API_KEY not set; skipping semantic filter (all jobs kept).")
        return jobs

    model = (config.get("gemini_model") or DEFAULT_MODEL).strip()
    client = genai.Client(api_key=api_key)

    keep_flags = {i: True for i in range(len(jobs))}
    judged = 0
    batches = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]
    print(f"[Gemini] Scoring {len(jobs)} job(s) with {model} in {len(batches)} batch(es)...")

    for batch_num, batch in enumerate(batches):
        offset = batch_num * BATCH_SIZE
        if batch_num > 0:
            time.sleep(BATCH_DELAY)

        payload = [_job_payload(offset + i, job) for i, job in enumerate(batch)]
        verdicts = _call_gemini(client, payload, model)

        if verdicts is None:
            print(f"[Gemini] Batch {batch_num + 1}/{len(batches)} failed — keeping all jobs in it.")
            continue

        for v in verdicts:
            idx = v.index
            if not (offset <= idx < offset + len(batch)):
                continue

            keep = v.keep and (v.score >= KEEP_THRESHOLD)
            keep_flags[idx] = keep
            judged += 1

            if not keep:
                reason = v.reason.strip() or "no reason given"
                print(f"[Gemini] Excluded (score {v.score}): {jobs[idx].get('title', '?')} — {reason}")

    kept = [job for i, job in enumerate(jobs) if keep_flags[i]]
    unjudged = len(jobs) - judged
    if unjudged:
        print(f"[Gemini] {unjudged} job(s) were not judged — kept by default.")
    print(f"[Gemini] Kept {len(kept)}/{len(jobs)} job(s).")
    return kept
