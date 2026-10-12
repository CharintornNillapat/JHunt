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
from urllib.parse import urlparse

import libsql_client

from src.extractor.schemas import ExtractedJob
from src.storage.schema import (
    ALL_INDEX_STATEMENTS,
    SCHEMA_STATEMENTS,
    TABLE_STATEMENTS,
)

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
                self.init_schema()
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to initialize schema with client ({e}).")
        elif self.database_url:
            try:
                self.client = libsql_client.create_client_sync(
                    url=self.database_url,
                    auth_token=self.auth_token or None,
                )
                self.init_schema()
                logger.info("[TursoClient] Connected to Turso cloud database.")
            except Exception as e:
                logger.warning(
                    f"[TursoClient] Failed to initialize Turso client ({self._redact(e)}). "
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

    def _redact(self, text: object) -> str:
        """Removes the database URL and its hostname from text that is about to be logged."""
        out = str(text)
        host = urlparse(self.database_url).hostname if self.database_url else None
        for secret in (self.database_url, host):
            if secret:
                out = out.replace(secret, "<turso-db>")
        return out

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

    def _execute_ddl(self, sql: str) -> None:
        """Executes a single DDL statement safely using execute() or batch()."""
        if not self.client:
            return
        if hasattr(self.client, "execute"):
            self.client.execute(sql)
        elif hasattr(self.client, "batch"):
            self.client.batch([sql])

    def _get_jobs_columns(self) -> set[str]:
        """Inspects existing column names of jobs table in Turso."""
        if not self.client:
            return set()
        try:
            if hasattr(self.client, "execute"):
                rs = self.client.execute("PRAGMA table_info(jobs);")
            elif hasattr(self.client, "batch"):
                res = self.client.batch(["PRAGMA table_info(jobs);"])
                rs = res[0] if res else None
            else:
                return set()

            rows = getattr(rs, "rows", None)
            if rows is None:
                if hasattr(rs, "fetchall"):
                    try:
                        rows = rs.fetchall()
                    except Exception:
                        rows = None
                elif hasattr(rs, "__iter__") and not isinstance(rs, (str, bytes)):
                    try:
                        rows = list(rs)
                    except Exception:
                        rows = None

            if not rows:
                return set()

            cols: set[str] = set()
            for row in rows:
                if hasattr(row, "__getitem__"):
                    try:
                        cols.add(str(row["name"]).strip().lower())
                    except (TypeError, KeyError, IndexError):
                        if len(row) > 1:
                            cols.add(str(row[1]).strip().lower())
                elif hasattr(row, "name"):
                    cols.add(str(row.name).strip().lower())
            return cols
        except Exception as e:
            logger.debug(f"[TursoClient] Failed to inspect jobs columns ({e}).")
            return set()

    def _migrate_jobs_schema(self) -> None:
        """
        Self-healing schema migration for jobs table in Turso.
        Ensures min_salary, max_salary, and currency columns exist.
        """
        if not self.client:
            return

        cols = self._get_jobs_columns()
        if not cols:
            return

        if "min_salary" not in cols:
            try:
                logger.info("[TursoClient] Adding missing column 'min_salary' to jobs...")
                self._execute_ddl("ALTER TABLE jobs ADD COLUMN min_salary INTEGER;")
                cols.add("min_salary")
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to add column 'min_salary': {e}")

        if "max_salary" not in cols:
            try:
                logger.info("[TursoClient] Adding missing column 'max_salary' to jobs...")
                self._execute_ddl("ALTER TABLE jobs ADD COLUMN max_salary INTEGER;")
                cols.add("max_salary")
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to add column 'max_salary': {e}")

        if "currency" not in cols:
            try:
                logger.info("[TursoClient] Adding missing column 'currency' to jobs...")
                self._execute_ddl("ALTER TABLE jobs ADD COLUMN currency TEXT DEFAULT 'THB';")
                cols.add("currency")
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to add column 'currency': {e}")

        if "extract_attempts" not in cols:
            try:
                logger.info("[TursoClient] Adding missing column 'extract_attempts' to jobs...")
                self._execute_ddl("ALTER TABLE jobs ADD COLUMN extract_attempts INTEGER DEFAULT 0;")
                cols.add("extract_attempts")
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to add column 'extract_attempts': {e}")

    def _get_skills_extracted_columns(self) -> set[str]:
        """Inspects existing column names of skills_extracted table in Turso."""
        if not self.client:
            return set()
        try:
            if hasattr(self.client, "execute"):
                rs = self.client.execute("PRAGMA table_info(skills_extracted);")
            elif hasattr(self.client, "batch"):
                res = self.client.batch(["PRAGMA table_info(skills_extracted);"])
                rs = res[0] if res else None
            else:
                return set()

            rows = getattr(rs, "rows", None)
            if rows is None:
                if hasattr(rs, "fetchall"):
                    try:
                        rows = rs.fetchall()
                    except Exception:
                        rows = None
                elif hasattr(rs, "__iter__") and not isinstance(rs, (str, bytes)):
                    try:
                        rows = list(rs)
                    except Exception:
                        rows = None

            if not rows:
                return set()

            cols: set[str] = set()
            for row in rows:
                if hasattr(row, "__getitem__"):
                    try:
                        cols.add(str(row["name"]).strip().lower())
                    except (TypeError, KeyError, IndexError):
                        if len(row) > 1:
                            cols.add(str(row[1]).strip().lower())
                elif hasattr(row, "name"):
                    cols.add(str(row.name).strip().lower())
            return cols
        except Exception as e:
            logger.debug(f"[TursoClient] Failed to inspect skills_extracted columns ({e}).")
            return set()

    def _migrate_skills_extracted_schema(self) -> None:
        """
        Self-healing schema migration for skills_extracted table in Turso.
        Renames legacy 'skill' -> 'skill_name', adds 'skill_name' if missing,
        and ensures 'category' column exists.
        """
        if not self.client:
            return

        cols = self._get_skills_extracted_columns()
        if not cols:
            return

        # 1. Ensure skill_name column exists
        if "skill_name" not in cols:
            if "skill" in cols:
                try:
                    logger.info("[TursoClient] Migrating legacy column 'skill' to 'skill_name'...")
                    self._execute_ddl("ALTER TABLE skills_extracted RENAME COLUMN skill TO skill_name;")
                    cols.remove("skill")
                    cols.add("skill_name")
                except Exception as e:
                    logger.warning(f"[TursoClient] Failed to rename 'skill' to 'skill_name': {e}")
            else:
                try:
                    logger.info("[TursoClient] Adding missing column 'skill_name' to skills_extracted...")
                    self._execute_ddl("ALTER TABLE skills_extracted ADD COLUMN skill_name TEXT;")
                    cols.add("skill_name")
                except Exception as e:
                    logger.warning(f"[TursoClient] Failed to add column 'skill_name': {e}")

        # 2. Ensure category column exists
        if "category" not in cols:
            try:
                logger.info("[TursoClient] Adding missing column 'category' to skills_extracted...")
                self._execute_ddl("ALTER TABLE skills_extracted ADD COLUMN category TEXT;")
                cols.add("category")
            except Exception as e:
                logger.warning(f"[TursoClient] Failed to add column 'category': {e}")

    def _create_indexes(self) -> None:
        """
        Creates B-Tree indexes with isolated error handling.
        Tries batch execution first for low latency; falls back to isolated single-statement
        execution if batch fails, ensuring non-blocking resilience.
        """
        if not self.client:
            return

        index_stmts = list(ALL_INDEX_STATEMENTS)
        try:
            if hasattr(self.client, "batch"):
                self.client.batch(index_stmts)
                return
        except Exception as batch_err:
            logger.warning(
                f"[TursoClient] Batch index creation failed ({batch_err}); "
                "falling back to isolated index execution."
            )

        for stmt in index_stmts:
            try:
                self._execute_ddl(stmt)
            except Exception as e:
                logger.warning(f"[TursoClient] Non-fatal error creating index ({e}): {stmt}")

    def init_schema(self) -> None:
        """
        Initializes unified schema tables, executes self-healing migrations,
        and applies performance B-Tree indexes with isolated resilience.
        """
        if not self.client:
            return

        # 1. Run table creation statements first
        table_stmts = list(TABLE_STATEMENTS)
        if hasattr(self.client, "batch"):
            self.client.batch(table_stmts)
        else:
            for stmt in table_stmts:
                self._execute_ddl(stmt)

        # 2. Self-healing migration for legacy columns
        try:
            self._migrate_jobs_schema()
            self._migrate_skills_extracted_schema()
        except Exception as e:
            logger.warning(f"[TursoClient] Schema migration check encountered non-fatal error: {e}")

        # 3. Resilient index creation
        try:
            self._create_indexes()
        except Exception as e:
            logger.warning(f"[TursoClient] Index creation encountered non-fatal error: {e}")

    def init_tables(self) -> None:
        """Backwards-compatible alias for init_schema."""
        self.init_schema()

    def init_db(self) -> None:
        """Backwards-compatible alias for init_schema."""
        self.init_schema()

    def save_job(self, job: Dict[str, Any]) -> bool:
        """
        Persists a scraped job into Turso `jobs` table if not already present.
        Returns True if inserted, False if it was already stored or failed.
        """
        return self.sync_jobs([job]) > 0

    def save_jobs(self, jobs_list: Union[List[Dict[str, Any]], Dict[str, Any]]) -> int:
        """Alias for sync_jobs providing unified storage interface."""
        return self.sync_jobs(jobs_list)

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

            min_salary = job.get("min_salary")
            max_salary = job.get("max_salary")
            currency = job.get("currency") or "THB"
            if min_salary is None and max_salary is None and (job.get("salary") or job.get("description")):
                from src.extractor.salary_parser import parse_salary
                min_salary, max_salary, currency = parse_salary(job.get("salary"), job.get("description"))

            raw_content = job.get("raw_content")
            if raw_content is None:
                raw_payload = {
                    "teaser": job.get("teaser", "") or "",
                    "bullet_points": job.get("bullet_points", []) or [],
                    "listing_date": job.get("listing_date", "") or job.get("posted_at", "") or "",
                    "description": job.get("description", "") or "",
                }
                raw_content_str = json.dumps(raw_payload, ensure_ascii=False)
            elif isinstance(raw_content, dict):
                raw_content_str = json.dumps(raw_content, ensure_ascii=False)
            else:
                raw_content_str = str(raw_content)

            stmts.append((
                "INSERT OR IGNORE INTO jobs (id, title, company, url, location, salary, work_type, raw_content, posted_at, source, min_salary, max_salary, currency) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    job_id,
                    str(job.get("title") or "").strip(),
                    str(job.get("company") or "").strip(),
                    str(job.get("url") or "").strip(),
                    str(job.get("location") or "").strip(),
                    str(job.get("salary") or "").strip(),
                    str(job.get("work_type") or "").strip(),
                    raw_content_str,
                    str(job.get("posted_at") or job.get("listing_date") or "").strip() or None,
                    str(job.get("source") or "").strip() or None,
                    min_salary,
                    max_salary,
                    str(currency or "THB").strip(),
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

            skill_name = str(r.get("skill_name") or (r.get("must_have_skills")[0] if isinstance(r.get("must_have_skills"), list) and r.get("must_have_skills") else "")).strip() or None
            stmts.append((
                """
                INSERT INTO skills_extracted (
                    job_id, experience_level, must_have_skills, nice_to_have_skills,
                    frameworks, databases, cloud_infra, tools, skill_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    experience_level = excluded.experience_level,
                    must_have_skills = excluded.must_have_skills,
                    nice_to_have_skills = excluded.nice_to_have_skills,
                    frameworks = excluded.frameworks,
                    databases = excluded.databases,
                    cloud_infra = excluded.cloud_infra,
                    tools = excluded.tools,
                    skill_name = COALESCE(excluded.skill_name, skills_extracted.skill_name),
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
                    skill_name,
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

    def get_unprocessed_jobs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves jobs from Turso `jobs` table that have not yet had skills extracted.
        Returns a list of standardized job dicts.
        """
        if not self.client:
            return []
        query = """
            SELECT j.*
            FROM jobs j
            LEFT JOIN skills_extracted s ON j.id = s.job_id
            WHERE s.job_id IS NULL AND (j.extract_attempts IS NULL OR j.extract_attempts < 3)
            ORDER BY j.created_at DESC
        """
        params: List[Any] = []
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params = [limit]

        try:
            rs = self.client.execute(query, params)
            return [self._row_to_job(rs.columns, row) for row in rs.rows]
        except Exception as e:
            logger.warning(f"[TursoClient] Failed to get unprocessed jobs: {e}")
            return []

    def increment_extract_attempts(self, job_ids: List[str]) -> None:
        """Increments extract_attempts counter for the specified job IDs in Turso."""
        if not self.client or not job_ids:
            return
        try:
            for jid in job_ids:
                self.client.execute(
                    "UPDATE jobs SET extract_attempts = COALESCE(extract_attempts, 0) + 1 WHERE id = ?;",
                    [str(jid)],
                )
        except Exception as e:
            logger.warning(f"[TursoClient] Failed to increment extract_attempts: {e}")

    def save_extracted_skills(self, job_id: str, extracted: ExtractedJob) -> None:
        """Persists or updates structured LLM extracted skills for a job in Turso."""
        self.sync_extracted_skills([{"job_id": job_id, "extracted": extracted}])

    def save_extracted_skills_batch(self, items: List[Dict[str, Any]]) -> int:
        """Alias for sync_extracted_skills providing unified storage interface."""
        return self.sync_extracted_skills(items)

    def get_extracted_skills(self, job_id: str) -> Optional[ExtractedJob]:
        """Retrieves extracted skills for a job ID from Turso, or None if not yet extracted."""
        if not self.client:
            return None
        try:
            rs = self.client.execute(
                """
                SELECT s.*, j.title, j.company
                FROM skills_extracted s
                JOIN jobs j ON s.job_id = j.id
                WHERE s.job_id = ? LIMIT 1;
                """,
                [str(job_id)],
            )
            if not rs.rows:
                return None
            return self._row_to_extracted_job(rs.columns, rs.rows[0])
        except Exception as e:
            logger.warning(f"[TursoClient] Failed to get extracted skills for job '{job_id}': {e}")
            return None

    def get_all_extracted_skills(self) -> List[ExtractedJob]:
        """Retrieves all extracted skills across all analyzed jobs from Turso cloud."""
        if not self.client:
            return []
        try:
            rs = self.client.execute(
                """
                SELECT s.*, j.title, j.company
                FROM skills_extracted s
                JOIN jobs j ON s.job_id = j.id
                WHERE s.experience_level != 'Non-Tech'
                ORDER BY s.extracted_at DESC;
                """
            )
            return [self._row_to_extracted_job(rs.columns, row) for row in rs.rows]
        except Exception as e:
            logger.warning(f"[TursoClient] Failed to get all extracted skills: {e}")
            return []

    def get_top_skill_cooccurrences(self, min_count: int = 1) -> List[Dict[str, Any]]:
        """
        Computes pairwise co-occurrences of tech stack components across all
        extracted jobs in Turso cloud.
        """
        from src.analyzer.cluster_analyzer import compute_pairwise_cooccurrences

        all_skills = self.get_all_extracted_skills()
        pair_counts = compute_pairwise_cooccurrences(all_skills)
        return [
            {"tech_a": pair[0], "tech_b": pair[1], "count": count}
            for pair, count in pair_counts.most_common()
            if count >= min_count
        ]

    def record_generated_project(
        self,
        title: str,
        role: str,
        tech_stack: Union[List[str], str],
        difficulty: str = "",
        domain: str = "",
        spec_markdown: str = "",
    ) -> int:
        """Records a generated blueprint into Turso and returns 1 on success, 0 on failure."""
        success = self.sync_blueprint(
            title=title,
            role=role,
            difficulty=difficulty,
            domain=domain,
            tech_stack=tech_stack,
            spec_markdown=spec_markdown,
        )
        return 1 if success else 0

    def has_generated_project(self, title: str) -> bool:
        """True when Turso already holds a blueprint with this title."""
        return self.has_blueprint(title)

    def get_generated_projects(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent generated project records from Turso."""
        if not self.client:
            return []
        try:
            rs = self.client.execute(
                """
                SELECT * FROM generated_projects
                ORDER BY created_at DESC LIMIT ?;
                """,
                [limit],
            )
            return [self._row_to_dict(rs.columns, row) for row in rs.rows]
        except Exception as e:
            logger.warning(f"[TursoClient] Failed to get generated projects: {e}")
            return []

    @staticmethod
    def _row_to_dict(columns: Any, row: Any) -> Dict[str, Any]:
        """Converts a LibSQL Row or tuple into a standardized dict."""
        data: Dict[str, Any] = {}
        for idx, col in enumerate(columns):
            try:
                data[col] = row[col]
            except (TypeError, KeyError, IndexError):
                data[col] = row[idx] if idx < len(row) else None
        return data

    @classmethod
    def _row_to_job(cls, columns: Any, row: Any) -> Dict[str, Any]:
        """Converts a LibSQL Row into a standardized job dict, unpacking raw_content."""
        data = cls._row_to_dict(columns, row)
        raw_content = data.get("raw_content")
        if raw_content:
            try:
                parsed_raw = json.loads(raw_content)
                data.update(parsed_raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return data

    @classmethod
    def _row_to_extracted_job(cls, columns: Any, row: Any) -> ExtractedJob:
        """Parses a LibSQL database row into an ExtractedJob Pydantic model."""
        data = cls._row_to_dict(columns, row)

        def safe_json_list(val: Any) -> List[str]:
            if not val:
                return []
            try:
                res = json.loads(val)
                return res if isinstance(res, list) else []
            except (json.JSONDecodeError, TypeError):
                return []

        return ExtractedJob(
            job_title=str(data.get("title") or ""),
            company=str(data.get("company") or ""),
            experience_level=str(data.get("experience_level") or "Unknown"),
            must_have_skills=safe_json_list(data.get("must_have_skills")),
            nice_to_have_skills=safe_json_list(data.get("nice_to_have_skills")),
            frameworks=safe_json_list(data.get("frameworks")),
            databases=safe_json_list(data.get("databases")),
            cloud_infra=safe_json_list(data.get("cloud_infra")),
            tools=safe_json_list(data.get("tools")),
        )

