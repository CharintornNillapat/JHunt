# src/extractor/salary_backfill.py
"""
Deterministic Historical Salary Backfill Engine.
Iterates over historical job postings with unparsed salaries in storage,
applies parse_salary() to raw salary fields and description text,
and performs batch updates against Turso or local SQLite.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Union

from src.extractor.salary_parser import parse_salary
from src.storage import DatabaseManager, TursoClient, get_storage

logger = logging.getLogger(__name__)


def backfill_salaries(
    storage: Optional[Union[DatabaseManager, TursoClient]] = None,
    limit: Optional[int] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Backfills unparsed job salaries in storage.

    Args:
        storage: Storage instance (TursoClient or DatabaseManager). Defaults to get_storage().
        limit: Optional maximum number of candidate jobs to fetch.
        dry_run: If True, previews parsed results without modifying storage.

    Returns:
        Dict containing execution metrics:
        - total_candidates: Number of unparsed jobs fetched
        - parsed_count: Number of jobs where salary was successfully parsed
        - applied_count: Number of jobs updated in storage (0 if dry_run)
        - currencies: Counter mapping of currency -> count
        - updates: List of update dicts [{"id": ..., "min_salary": ..., "max_salary": ..., "currency": ...}]
    """
    owned_storage = False
    if storage is None:
        storage = get_storage()
        owned_storage = True

    try:
        candidates = storage.get_unparsed_salary_jobs(limit=limit)
        updates: List[Dict[str, Any]] = []
        currencies: Dict[str, int] = {}

        for job in candidates:
            raw_salary = job.get("salary")
            desc = job.get("description")
            if not desc and job.get("raw_content"):
                raw_content = job.get("raw_content")
                if isinstance(raw_content, str):
                    try:
                        parsed_rc = json.loads(raw_content)
                        if isinstance(parsed_rc, dict):
                            desc = parsed_rc.get("description")
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(raw_content, dict):
                    desc = raw_content.get("description")

            min_sal, max_sal, curr = parse_salary(raw_salary, desc)
            if min_sal is not None or max_sal is not None:
                updates.append({
                    "id": job["id"],
                    "min_salary": min_sal,
                    "max_salary": max_sal,
                    "currency": curr,
                })
                currencies[curr] = currencies.get(curr, 0) + 1

        applied_count = 0
        if not dry_run and updates:
            applied_count = storage.update_job_salaries_batch(updates)

        mode_str = "[DRY-RUN] " if dry_run else "[APPLY] "
        logger.info(
            f"{mode_str}Salary backfill: {len(candidates)} candidates, "
            f"{len(updates)} parsed, {applied_count} applied to storage. "
            f"Currencies: {currencies}"
        )

        return {
            "total_candidates": len(candidates),
            "parsed_count": len(updates),
            "applied_count": applied_count,
            "currencies": currencies,
            "updates": updates,
        }
    finally:
        if owned_storage and hasattr(storage, "close"):
            storage.close()

