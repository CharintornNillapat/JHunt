# src/storage/turso_client.py
"""
Turso Cloud Database (LibSQL) Integration Module.
Provides cloud persistence synchronization for jobs, extracted skills,
and generated portfolio blueprints. Gracefully falls back to local SQLite
when credentials are missing or connection fails.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import libsql_client

from src.extractor.schemas import ExtractedJob
from src.storage.schema import SCHEMA_STATEMENTS

logger = logging.getLogger(__name__)


class TursoClient:
    """
    Manages synchronization with Turso (LibSQL) cloud database.
    If credentials are missing or the connection cannot be established,
    it logs an info message and gracefully acts as a no-op fallback.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        raw_url = (database_url or os.getenv("TURSO_DATABASE_URL") or "").strip().strip('"').strip("'")
        raw_token = (auth_token or os.getenv("TURSO_AUTH_TOKEN") or "").strip().strip('"').strip("'")

        # Automatically normalize libsql:// to https:// to use standard HTTPS transport
        # and prevent WebSocket 400 handshake failures in CI/local runs.
        if raw_url.startswith("libsql://"):
            raw_url = "https://" + raw_url[len("libsql://"):]

        self.database_url = raw_url
        self.db_url = raw_url
        self.auth_token = raw_token
        self.client: Any = None  # set before connecting so the failure path below can test it

        if client is not None:
            self.client = client
            try:
                self.init_tables()
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to initialize tables with client ({e}).")
        elif self.database_url:
            try:
                self.client = libsql_client.create_client_sync(
                    url=self.database_url,
                    auth_token=self.auth_token or None,
                )
                self.init_tables()
                logger.info(f"[TursoClient] Connected to Turso cloud database: {self.database_url}")
            except Exception as e:
                logger.warning(
                    f"[TursoClient] Failed to initialize Turso client ({e}). "
                    "Gracefully falling back to local SQLite."
                )
                if self.client is not None:
                    try:
                        self.client.close()
                    except Exception:
                        pass
                self.client = None
        else:
            logger.info(
                "[TursoClient] Turso credentials not provided. "
                "Gracefully falling back to local SQLite."
            )
            self.client = None

    @property
    def is_available(self) -> bool:
        """Returns True if the Turso client is initialized and ready."""
        return self.client is not None

    def close(self) -> None:
        """Closes the underlying LibSQL client connection if open."""
        if self.client is not None:
            try:
                if hasattr(self.client, "close"):
                    self.client.close()
            except Exception as e:
                logger.debug(f"[TursoClient] Error closing client: {e}")
            finally:
                self.client = None

    def init_tables(self) -> None:
        """Initializes tables in Turso cloud database if they do not exist."""
        if not self.client:
            return
        self.client.batch(list(SCHEMA_STATEMENTS))

    def sync_jobs(self, jobs_list: Union[List[Dict[str, Any]], Dict[str, Any]]) -> int:
        """
        Inserts or ignores scraped jobs into the Turso `jobs` table in one round trip.
        Returns the number of rows sent, or 0 if the batch failed.
        """
        if not self.client or not jobs_list:
            return 0

        if isinstance(jobs_list, dict):
            items = [jobs_list]
        else:
            items = list(jobs_list)

        stmts = []
        for job in items:
            job_id = str(job.get("id") or "").strip()
            if not job_id:
                continue

            raw_content = job.get("raw_content")
            if raw_content is None:
                raw_payload = {
                    "teaser": job.get("teaser", ""),
                    "bullet_points": job.get("bullet_points", []),
                    "listing_date": job.get("listing_date", ""),
                }
                raw_content_str = json.dumps(raw_payload, ensure_ascii=False)
            elif isinstance(raw_content, dict):
                raw_content_str = json.dumps(raw_content, ensure_ascii=False)
            else:
                raw_content_str = str(raw_content)

            stmts.append((
                "INSERT OR IGNORE INTO jobs (id, title, company, url, location, salary, work_type, raw_content) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    job_id,
                    str(job.get("title") or "").strip(),
                    str(job.get("company") or "").strip(),
                    str(job.get("url") or "").strip(),
                    str(job.get("location") or "").strip(),
                    str(job.get("salary") or "").strip(),
                    str(job.get("work_type") or "").strip(),
                    raw_content_str,
                ],
            ))

        return self._run_batch(stmts, "jobs")

    def sync_extracted_skills(self, skills_data: Any) -> int:
        """
        Inserts extracted skills metadata into Turso `skills_extracted` table.
        Supports single dict or list of dicts.
        Returns count of synced records.
        """
        if not self.client or not skills_data:
            return 0

        raw_items = [skills_data] if isinstance(skills_data, dict) else list(skills_data)
        stmts = []
        for item in raw_items:
            r = self._normalize_skill_record(item)
            if not r or not r.get("job_id"):
                continue
            stmts.append((
                """
                INSERT INTO skills_extracted (
                    job_id, experience_level, must_have_skills, nice_to_have_skills,
                    frameworks, databases, cloud_infra, tools
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    experience_level = excluded.experience_level,
                    must_have_skills = excluded.must_have_skills,
                    nice_to_have_skills = excluded.nice_to_have_skills,
                    frameworks = excluded.frameworks,
                    databases = excluded.databases,
                    cloud_infra = excluded.cloud_infra,
                    tools = excluded.tools,
                    extracted_at = CURRENT_TIMESTAMP
                """,
                [
                    str(r["job_id"]),
                    str(r.get("experience_level") or "Unknown"),
                    self._to_json_str(r.get("must_have_skills")),
                    self._to_json_str(r.get("nice_to_have_skills")),
                    self._to_json_str(r.get("frameworks")),
                    self._to_json_str(r.get("databases")),
                    self._to_json_str(r.get("cloud_infra")),
                    self._to_json_str(r.get("tools")),
                ],
            ))

        return self._run_batch(stmts, "skills_extracted")

    def _run_batch(self, stmts: List[Tuple[str, List[Any]]], table: str) -> int:
        """Sends all statements in one round trip (one transaction). Returns rows sent, or 0 on failure."""
        if not stmts:
            return 0
        try:
            self.client.batch(stmts)
            return len(stmts)
        except Exception as e:
            logger.warning(f"[TursoClient] Batch sync of {len(stmts)} {table} row(s) failed: {e}")
            return 0

    def has_blueprint(self, title: str) -> bool:
        """True when Turso already holds a blueprint with this title. False on error (caller may save again)."""
        if not self.client:
            return False
        try:
            rs = self.client.execute("SELECT 1 FROM generated_projects WHERE title = ? LIMIT 1", [title.strip()])
            return len(rs.rows) > 0
        except Exception as e:
            logger.warning(f"[TursoClient] Blueprint lookup failed: {e}")
            return False

    def sync_blueprint(
        self,
        title: str,
        role: str,
        difficulty: str = "Intermediate",
        domain: str = "",
        tech_stack: Union[List[str], str] = "",
        spec_markdown: str = "",
        **kwargs: Any,
    ) -> bool:
        """
        Inserts generated project blueprint into Turso `generated_projects` table.
        Returns True on success, False otherwise.
        """
        if not self.client:
            return False

        if isinstance(tech_stack, list):
            stack_str = json.dumps(tech_stack, ensure_ascii=False)
        else:
            stack_str = str(tech_stack)

        try:
            self.client.execute(
                """
                INSERT INTO generated_projects (
                    title, role, difficulty, domain, tech_stack, spec_markdown
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                [
                    str(title).strip(),
                    str(role).strip(),
                    str(difficulty or "Intermediate").strip(),
                    str(domain).strip(),
                    stack_str,
                    str(spec_markdown),
                ],
            )
            return True
        except Exception as e:
            logger.error(f"[TursoClient] Failed to sync blueprint '{title}': {e}")
            return False

    @staticmethod
    def _to_json_str(val: Any) -> str:
        """Serializes list/object to JSON string safely."""
        if val is None:
            return "[]"
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)

    @staticmethod
    def _normalize_skill_record(item: Any) -> Optional[Dict[str, Any]]:
        """Extracts normalized record dict from ExtractedJob or dict."""
        if not isinstance(item, dict):
            return None
        job_id = item.get("job_id")
        extracted = item.get("extracted")
        if isinstance(extracted, ExtractedJob):
            return {
                "job_id": job_id,
                "experience_level": extracted.experience_level,
                "must_have_skills": extracted.must_have_skills,
                "nice_to_have_skills": extracted.nice_to_have_skills,
                "frameworks": extracted.frameworks,
                "databases": extracted.databases,
                "cloud_infra": extracted.cloud_infra,
                "tools": extracted.tools,
            }
        return item

