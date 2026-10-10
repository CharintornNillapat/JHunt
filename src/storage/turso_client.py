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
from typing import Any, Dict, List, Optional, Union

import libsql_client

from src.extractor.schemas import ExtractedJob

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

        # 1. Jobs table
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                url TEXT NOT NULL,
                location TEXT,
                salary TEXT,
                work_type TEXT,
                raw_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Skills extracted table
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS skills_extracted (
                job_id TEXT PRIMARY KEY,
                experience_level TEXT,
                must_have_skills TEXT,
                nice_to_have_skills TEXT,
                frameworks TEXT,
                databases TEXT,
                cloud_infra TEXT,
                tools TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
            );
        """)

        # 3. Generated portfolio blueprints table
        self.client.execute("""
            CREATE TABLE IF NOT EXISTS generated_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                role TEXT NOT NULL,
                difficulty TEXT,
                domain TEXT,
                tech_stack TEXT,
                spec_markdown TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def sync_jobs(self, jobs_list: Union[List[Dict[str, Any]], Dict[str, Any]]) -> int:
        """
        Inserts or ignores scraped jobs into Turso `jobs` table.
        Returns count of synced jobs.
        """
        if not self.client or not jobs_list:
            return 0

        if isinstance(jobs_list, dict):
            items = [jobs_list]
        else:
            items = list(jobs_list)

        synced_count = 0
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

            try:
                self.client.execute(
                    """
                    INSERT OR IGNORE INTO jobs (
                        id, title, company, url, location, salary, work_type, raw_content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
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
                )
                synced_count += 1
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to sync job {job_id}: {e}")

        return synced_count

    def sync_extracted_skills(self, skills_data: Any) -> int:
        """
        Inserts extracted skills metadata into Turso `skills_extracted` table.
        Supports single dict, list of dicts, or tuples of (job_id, ExtractedJob).
        Returns count of synced records.
        """
        if not self.client or not skills_data:
            return 0

        # Normalize skills_data into a list of normalized records
        records = self._normalize_skills_payload(skills_data)
        synced_count = 0

        for r in records:
            job_id = r.get("job_id")
            if not job_id:
                continue

            try:
                self.client.execute(
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
                        extracted_at = CURRENT_TIMESTAMP;
                    """,
                    [
                        str(job_id),
                        str(r.get("experience_level") or "Unknown"),
                        self._to_json_str(r.get("must_have_skills")),
                        self._to_json_str(r.get("nice_to_have_skills")),
                        self._to_json_str(r.get("frameworks")),
                        self._to_json_str(r.get("databases")),
                        self._to_json_str(r.get("cloud_infra")),
                        self._to_json_str(r.get("tools")),
                    ],
                )
                synced_count += 1
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to sync extracted skills for job {job_id}: {e}")

        return synced_count

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

    def close(self) -> None:
        """Closes the underlying client connection if applicable."""
        if self.client and hasattr(self.client, "close"):
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None

    @staticmethod
    def _to_json_str(val: Any) -> str:
        """Serializes list/object to JSON string safely."""
        if val is None:
            return "[]"
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)

    @staticmethod
    def _normalize_skills_payload(skills_data: Any) -> List[Dict[str, Any]]:
        """Normalizes various input formats into standardized dicts."""
        records: List[Dict[str, Any]] = []

        if isinstance(skills_data, dict):
            if "job_id" in skills_data:
                # Single dict containing job_id
                records.append(TursoClient._extract_dict_skills(skills_data))
            else:
                # Dict of {job_id: ExtractedJob or dict}
                for j_id, item in skills_data.items():
                    rec = TursoClient._extract_item_skills(j_id, item)
                    if rec:
                        records.append(rec)
        elif isinstance(skills_data, (list, tuple)):
            for item in skills_data:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    j_id, sub_item = item
                    rec = TursoClient._extract_item_skills(str(j_id), sub_item)
                    if rec:
                        records.append(rec)
                elif isinstance(item, dict) and "job_id" in item:
                    records.append(TursoClient._extract_dict_skills(item))

        return records

    @staticmethod
    def _extract_dict_skills(d: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts skill fields from a dict."""
        extracted = d.get("extracted")
        if isinstance(extracted, ExtractedJob):
            return {
                "job_id": d.get("job_id"),
                "experience_level": extracted.experience_level,
                "must_have_skills": extracted.must_have_skills,
                "nice_to_have_skills": extracted.nice_to_have_skills,
                "frameworks": extracted.frameworks,
                "databases": extracted.databases,
                "cloud_infra": extracted.cloud_infra,
                "tools": extracted.tools,
            }
        return d

    @staticmethod
    def _extract_item_skills(job_id: str, item: Any) -> Optional[Dict[str, Any]]:
        """Extracts skill fields from ExtractedJob or dict with given job_id."""
        if isinstance(item, ExtractedJob):
            return {
                "job_id": job_id,
                "experience_level": item.experience_level,
                "must_have_skills": item.must_have_skills,
                "nice_to_have_skills": item.nice_to_have_skills,
                "frameworks": item.frameworks,
                "databases": item.databases,
                "cloud_infra": item.cloud_infra,
                "tools": item.tools,
            }
        elif isinstance(item, dict):
            copy_d = dict(item)
            copy_d["job_id"] = job_id
            return copy_d
        return None
