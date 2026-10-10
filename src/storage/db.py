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
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.extractor.schemas import ExtractedJob


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
        self._init_db()

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

    def _init_db(self) -> None:
        """Initializes tables and indexes if they do not already exist."""
        with self._connection() as conn:
            cursor = conn.cursor()

            # 1. Raw & normalized scraped jobs
            cursor.execute("""
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

            # 2. Structured LLM-extracted tech stacks & competencies
            cursor.execute("""
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

            # 3. Generated portfolio project blueprints
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generated_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    role TEXT NOT NULL,
                    domain_industry TEXT,
                    tech_stack TEXT,
                    file_path TEXT NOT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Indexes for performance and deduplication
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_skills_job_id ON skills_extracted (job_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_generated_at ON generated_projects (generated_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects (role);")

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
        file_path: Union[str, Path],
        domain_industry: str = "",
    ) -> int:
        """
        Records a newly generated project blueprint and returns its generated database ID.
        """
        stack_str = json.dumps(tech_stack) if isinstance(tech_stack, list) else str(tech_stack)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO generated_projects (title, role, domain_industry, tech_stack, file_path)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    title.strip(),
                    role.strip(),
                    domain_industry.strip(),
                    stack_str,
                    str(file_path),
                ),
            )
            return cursor.lastrowid or 0

    def get_generated_projects(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent generated project records."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM generated_projects
                ORDER BY generated_at DESC LIMIT ?;
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
