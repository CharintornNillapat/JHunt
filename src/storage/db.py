# src/storage/db.py
"""
SQLite persistence layer for Job Market Intelligence & Portfolio Ideation.
Maintains data at `data/market.db` with relational integrity, deduplication,
and tech stack extraction persistence.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.extractor.schemas import ExtractedJob
from src.storage.schema import LEGACY_PROJECTS_MIGRATION, SCHEMA_STATEMENTS


DEFAULT_DB_PATH = Path(r"data/market.db")


class DatabaseManager:
    """
    Manages local SQLite database operations for jobs, extracted skills,
    and generated portfolio blueprints.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        env_path = os.getenv("MARKET_DB_PATH")
        if db_path is not None:
            self.db_path = Path(db_path)
        elif env_path:
            self.db_path = Path(env_path)
        else:
            self.db_path = DEFAULT_DB_PATH

        self._ensure_db_dir()
        self.init_db()

    def _ensure_db_dir(self) -> None:
        """Ensures parent directory for the database file exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self):
        """Creates a SQLite connection with foreign keys and row factory enabled, closing it on exit."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Applies the shared schema and creates indexes, safely migrating legacy tables if needed."""
        self._init_db()

    def _init_db(self) -> None:
        """Applies the shared schema, first migrating a legacy generated_projects table."""
        with self._connection() as conn:
            legacy_cols = {row["name"] for row in conn.execute("PRAGMA table_info(generated_projects)")}
            if "domain_industry" in legacy_cols:
                for statement in LEGACY_PROJECTS_MIGRATION:
                    conn.execute(statement)

            # Ensure columns exist if tables already existed prior to indexing
            jobs_cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
            if jobs_cols:
                if "posted_at" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN posted_at TIMESTAMP")
                if "source" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN source TEXT")

            skills_cols = {row["name"] for row in conn.execute("PRAGMA table_info(skills_extracted)")}
            if skills_cols:
                if "skill_name" not in skills_cols:
                    conn.execute("ALTER TABLE skills_extracted ADD COLUMN skill_name TEXT")

            proj_cols = {row["name"] for row in conn.execute("PRAGMA table_xinfo(generated_projects)")}
            if proj_cols:
                if "target_role" not in proj_cols:
                    conn.execute("ALTER TABLE generated_projects ADD COLUMN target_role TEXT GENERATED ALWAYS AS (role) VIRTUAL")

            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)

    # ── Job Operations ────────────────────────────────────────────────────────

    def save_job(self, job: Dict[str, Any]) -> bool:
        """
        Persists a scraped job into the jobs table if not already present.
        Returns True if inserted, False if it was already stored (duplicate).
        """
        job_id = str(job.get("id") or "").strip()
        if not job_id:
            return False

        raw_payload = {
            "teaser": job.get("teaser", ""),
            "bullet_points": job.get("bullet_points", []),
            "listing_date": job.get("listing_date", ""),
        }

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (id, title, company, url, location, salary, work_type, raw_content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING;
                """,
                (
                    job_id,
                    job.get("title", "").strip(),
                    job.get("company", "").strip(),
                    job.get("url", "").strip(),
                    job.get("location", "").strip(),
                    job.get("salary", "").strip(),
                    job.get("work_type", "").strip(),
                    json.dumps(raw_payload, ensure_ascii=False),
                ),
            )
            return cursor.rowcount > 0

    def get_unprocessed_jobs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves jobs from `jobs` table that have not yet had skills extracted.
        Returns a list of job dicts.
        """
        query = """
            SELECT j.*
            FROM jobs j
            LEFT JOIN skills_extracted s ON j.id = s.job_id
            WHERE s.job_id IS NULL
            ORDER BY j.created_at ASC
        """
        params: Tuple[Any, ...] = ()
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params = (limit,)

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Dict[str, Any]:
        """Converts a database row into a standardized job dict."""
        data = dict(row)
        raw_content = data.get("raw_content")
        if raw_content:
            try:
                parsed_raw = json.loads(raw_content)
                data.update(parsed_raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return data

    # ── Skills Operations ─────────────────────────────────────────────────────

    def save_extracted_skills(self, job_id: str, extracted: ExtractedJob) -> None:
        """Persists or updates structured LLM extracted skills for a job."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
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
                (
                    str(job_id),
                    extracted.experience_level,
                    json.dumps(extracted.must_have_skills, ensure_ascii=False),
                    json.dumps(extracted.nice_to_have_skills, ensure_ascii=False),
                    json.dumps(extracted.frameworks, ensure_ascii=False),
                    json.dumps(extracted.databases, ensure_ascii=False),
                    json.dumps(extracted.cloud_infra, ensure_ascii=False),
                    json.dumps(extracted.tools, ensure_ascii=False),
                ),
            )

    def get_extracted_skills(self, job_id: str) -> Optional[ExtractedJob]:
        """Retrieves extracted skills for a job ID, or None if not yet extracted."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.*, j.title, j.company
                FROM skills_extracted s
                JOIN jobs j ON s.job_id = j.id
                WHERE s.job_id = ? LIMIT 1;
                """,
                (str(job_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_extracted_job(row)

    def get_all_extracted_skills(self) -> List[ExtractedJob]:
        """Retrieves all extracted skills across all analyzed jobs."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, j.title, j.company
                FROM skills_extracted s
                JOIN jobs j ON s.job_id = j.id
                WHERE s.experience_level != 'Non-Tech'
                ORDER BY s.extracted_at DESC;
            """)
            rows = cursor.fetchall()
            return [self._row_to_extracted_job(row) for row in rows]

    @staticmethod
    def _row_to_extracted_job(row: sqlite3.Row) -> ExtractedJob:
        """Parses a database row into an ExtractedJob Pydantic model."""
        def safe_json_list(val: Any) -> List[str]:
            if not val:
                return []
            try:
                res = json.loads(val)
                return res if isinstance(res, list) else []
            except (json.JSONDecodeError, TypeError):
                return []

        return ExtractedJob(
            job_title=row["title"],
            company=row["company"],
            experience_level=row["experience_level"] or "Unknown",
            must_have_skills=safe_json_list(row["must_have_skills"]),
            nice_to_have_skills=safe_json_list(row["nice_to_have_skills"]),
            frameworks=safe_json_list(row["frameworks"]),
            databases=safe_json_list(row["databases"]),
            cloud_infra=safe_json_list(row["cloud_infra"]),
            tools=safe_json_list(row["tools"]),
        )

    # ── Market Analytics & Co-occurrences ─────────────────────────────────────

    def get_top_skill_cooccurrences(self, min_count: int = 1) -> List[Dict[str, Any]]:
        """
        Computes pairwise co-occurrences of tech stack components across all
        extracted jobs in the database using shared helper.
        Returns list of {'tech_a': str, 'tech_b': str, 'count': int} sorted descending.
        """
        from src.analyzer.cluster_analyzer import compute_pairwise_cooccurrences

        all_skills = self.get_all_extracted_skills()
        pair_counts = compute_pairwise_cooccurrences(all_skills)
        return [
            {"tech_a": pair[0], "tech_b": pair[1], "count": count}
            for pair, count in pair_counts.most_common()
            if count >= min_count
        ]


    # ── Generated Projects Operations ─────────────────────────────────────────

    def record_generated_project(
        self,
        title: str,
        role: str,
        tech_stack: Union[List[str], str],
        difficulty: str = "",
        domain: str = "",
        spec_markdown: str = "",
    ) -> int:
        """Records a generated blueprint (same columns as Turso) and returns its row id."""
        stack_str = json.dumps(tech_stack, ensure_ascii=False) if isinstance(tech_stack, list) else str(tech_stack)
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO generated_projects (title, role, difficulty, domain, tech_stack, spec_markdown)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (title.strip(), role.strip(), difficulty.strip(), domain.strip(), stack_str, spec_markdown),
            )
            return cursor.lastrowid or 0

    def has_generated_project(self, title: str) -> bool:
        """True when a blueprint with this exact title is already recorded."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM generated_projects WHERE title = ? LIMIT 1;", (title.strip(),)
            ).fetchone()
            return row is not None

    def get_generated_projects(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent generated project records."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM generated_projects
                ORDER BY created_at DESC LIMIT ?;
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
