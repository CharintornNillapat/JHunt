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
            elif legacy_cols and "provenance" not in legacy_cols:
                conn.execute("ALTER TABLE generated_projects ADD COLUMN provenance TEXT DEFAULT 'llm'")

            # Ensure columns exist if tables already existed prior to indexing
            jobs_cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
            if jobs_cols:
                if "posted_at" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN posted_at TIMESTAMP")
                if "source" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN source TEXT")
                if "min_salary" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN min_salary INTEGER")
                if "max_salary" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN max_salary INTEGER")
                if "currency" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN currency TEXT DEFAULT 'THB'")
                if "extract_attempts" not in jobs_cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN extract_attempts INTEGER DEFAULT 0")

            skills_cols = {row["name"] for row in conn.execute("PRAGMA table_info(skills_extracted)")}
            if skills_cols:
                if "skill_name" not in skills_cols:
                    if "skill" in skills_cols:
                        conn.execute("ALTER TABLE skills_extracted RENAME COLUMN skill TO skill_name")
                    else:
                        conn.execute("ALTER TABLE skills_extracted ADD COLUMN skill_name TEXT")
                if "category" not in skills_cols:
                    conn.execute("ALTER TABLE skills_extracted ADD COLUMN category TEXT")

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

        min_salary = job.get("min_salary")
        max_salary = job.get("max_salary")
        currency = job.get("currency") or "THB"
        if min_salary is None and max_salary is None and (job.get("salary") or job.get("description")):
            from src.extractor.salary_parser import parse_salary
            min_salary, max_salary, currency = parse_salary(job.get("salary"), job.get("description"))

        raw_payload = {
            "teaser": job.get("teaser", "") or "",
            "bullet_points": job.get("bullet_points", []) or [],
            "listing_date": job.get("listing_date", "") or job.get("posted_at", "") or "",
            "description": job.get("description", "") or "",
        }

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (id, title, company, url, location, salary, work_type, raw_content, posted_at, source, min_salary, max_salary, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING;
                """,
                (
                    job_id,
                    str(job.get("title") or "").strip(),
                    str(job.get("company") or "").strip(),
                    str(job.get("url") or "").strip(),
                    str(job.get("location") or "").strip(),
                    str(job.get("salary") or "").strip(),
                    str(job.get("work_type") or "").strip(),
                    json.dumps(raw_payload, ensure_ascii=False),
                    str(job.get("posted_at") or job.get("listing_date") or "").strip() or None,
                    str(job.get("source") or "").strip() or None,
                    min_salary,
                    max_salary,
                    str(currency or "THB").strip(),
                ),
            )
            return cursor.rowcount > 0

    def save_jobs(self, jobs_list: Union[List[Dict[str, Any]], Dict[str, Any]]) -> int:
        """
        Persists a batch of scraped jobs into the jobs table.
        Returns the count of newly inserted rows.
        """
        if not jobs_list:
            return 0
        items = [jobs_list] if isinstance(jobs_list, dict) else list(jobs_list)
        inserted_count = 0
        with self._connection() as conn:
            cursor = conn.cursor()
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

                raw_payload = {
                    "teaser": job.get("teaser", "") or "",
                    "bullet_points": job.get("bullet_points", []) or [],
                    "listing_date": job.get("listing_date", "") or job.get("posted_at", "") or "",
                    "description": job.get("description", "") or "",
                }
                cursor.execute(
                    """
                    INSERT INTO jobs (id, title, company, url, location, salary, work_type, raw_content, posted_at, source, min_salary, max_salary, currency)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING;
                    """,
                    (
                        job_id,
                        str(job.get("title") or "").strip(),
                        str(job.get("company") or "").strip(),
                        str(job.get("url") or "").strip(),
                        str(job.get("location") or "").strip(),
                        str(job.get("salary") or "").strip(),
                        str(job.get("work_type") or "").strip(),
                        json.dumps(raw_payload, ensure_ascii=False),
                        str(job.get("posted_at") or job.get("listing_date") or "").strip() or None,
                        str(job.get("source") or "").strip() or None,
                        min_salary,
                        max_salary,
                        str(currency or "THB").strip(),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted_count += 1
        return inserted_count

    def get_unprocessed_jobs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves jobs from `jobs` table that have not yet had skills extracted.
        Returns a list of job dicts.
        """
        query = """
            SELECT j.*
            FROM jobs j
            LEFT JOIN skills_extracted s ON j.id = s.job_id
            WHERE s.job_id IS NULL AND (j.extract_attempts IS NULL OR j.extract_attempts < 3)
            ORDER BY j.created_at DESC
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

    def increment_extract_attempts(self, job_ids: List[str]) -> None:
        """Increments extract_attempts counter for the specified job IDs."""
        if not job_ids:
            return
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "UPDATE jobs SET extract_attempts = COALESCE(extract_attempts, 0) + 1 WHERE id = ?",
                [(str(jid),) for jid in job_ids],
            )

    def get_unparsed_salary_jobs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves jobs from `jobs` table that have not had salary parsed (both min_salary and max_salary are NULL),
        and have raw salary or raw_content text available.
        Returns a list of standardized job dicts.
        """
        query = """
            SELECT j.id, j.salary, j.raw_content
            FROM jobs j
            WHERE j.min_salary IS NULL AND j.max_salary IS NULL
              AND (
                (j.salary IS NOT NULL AND trim(j.salary) != '')
                OR (j.raw_content IS NOT NULL AND trim(j.raw_content) != '')
              )
            ORDER BY j.created_at DESC
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

    def update_job_salaries_batch(self, updates: List[Dict[str, Any]]) -> int:
        """
        Batch updates min_salary, max_salary, and currency for existing jobs.
        Returns the number of updated records.
        """
        if not updates:
            return 0
        params = []
        for u in updates:
            job_id = str(u.get("id") or u.get("job_id") or "").strip()
            if not job_id:
                continue
            params.append((
                u.get("min_salary"),
                u.get("max_salary"),
                str(u.get("currency") or "THB").strip(),
                job_id,
            ))
        if not params:
            return 0
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                UPDATE jobs
                SET min_salary = ?, max_salary = ?, currency = ?
                WHERE id = ?;
                """,
                params,
            )
            return cursor.rowcount if cursor.rowcount >= 0 else len(params)

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
        skill_name = str(extracted.must_have_skills[0]).strip() if extracted.must_have_skills else None
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
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
                    skill_name,
                ),
            )

    def save_extracted_skills_batch(self, items: List[Dict[str, Any]]) -> int:
        """Persists or updates a batch of extracted skills for jobs."""
        if not items:
            return 0
        for item in items:
            job_id = item.get("job_id")
            extracted = item.get("extracted")
            if job_id and isinstance(extracted, ExtractedJob):
                self.save_extracted_skills(str(job_id), extracted)
        return len(items)

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

    def refresh_skill_stats(self) -> int:
        """
        Recomputes pre-aggregated skill_stats rollup table in a single atomic transaction.
        Returns total number of rows populated.
        """
        from src.storage.schema import aggregate_skill_stats

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    s.job_id,
                    s.skill_name,
                    s.category,
                    s.must_have_skills,
                    s.nice_to_have_skills,
                    s.frameworks,
                    s.databases,
                    s.cloud_infra,
                    s.tools,
                    j.min_salary,
                    j.max_salary,
                    j.currency
                FROM skills_extracted s
                LEFT JOIN jobs j ON s.job_id = j.id
                WHERE (s.experience_level IS NULL OR s.experience_level != 'Non-Tech')
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            stats = aggregate_skill_stats(raw_rows)

            cursor.execute("DELETE FROM skill_stats;")
            if stats:
                cursor.executemany(
                    """
                    INSERT INTO skill_stats (skill, category, job_count, salary_count, avg_salary_thb)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            s["skill"],
                            s["category"],
                            s["job_count"],
                            s["salary_count"],
                            s["avg_salary_thb"],
                        )
                        for s in stats
                    ],
                )
            return len(stats)

    def get_skill_stats(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        min_salary_count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves pre-aggregated skill statistics from skill_stats.
        If min_salary_count is provided, filters for skills with at least that many salary samples
        and orders by avg_salary_thb DESC.
        """
        query = "SELECT skill, category, job_count, salary_count, avg_salary_thb, updated_at FROM skill_stats"
        conditions: List[str] = []
        params: List[Any] = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if min_salary_count is not None and min_salary_count > 0:
            conditions.append("salary_count >= ?")
            params.append(min_salary_count)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if min_salary_count is not None and min_salary_count > 0:
            query += " ORDER BY avg_salary_thb DESC, job_count DESC"
        else:
            query += " ORDER BY job_count DESC"

        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


    # ── Generated Projects Operations ─────────────────────────────────────────

    def record_generated_project(
        self,
        title: str,
        role: str,
        tech_stack: Union[List[str], str],
        difficulty: str = "",
        domain: str = "",
        spec_markdown: str = "",
        provenance: str = "llm",
    ) -> int:
        """Records a generated blueprint (same columns as Turso) and returns its row id."""
        stack_str = json.dumps(tech_stack, ensure_ascii=False) if isinstance(tech_stack, list) else str(tech_stack)
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO generated_projects (title, role, difficulty, domain, tech_stack, spec_markdown, provenance)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (title.strip(), role.strip(), difficulty.strip(), domain.strip(), stack_str, spec_markdown, (provenance or "llm").strip()),
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

    def close(self) -> None:
        """No-op for DatabaseManager since connections are managed per context manager."""
        pass
