# Plan: Task 2.1 — Pre-Aggregated Rollup Table (`skill_stats`)

**Date:** 2026-10-13  
**Task ID:** 2.1  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 2.1), `docs/audits/2026-10-12-architecture-reflection.md` (Section 2.3, Section 3), `AGENTS.md` (Storage & Cost invariants)

---

## Goal
Implement a pre-aggregated `skill_stats` rollup table in storage and populate it in a single transaction during the daily pipeline run, allowing Next.js `/analytics` to serve market intelligence and salary benchmarks via a single fast query without scanning raw `skills_extracted` records.

---

## Disagreements / Alignment Notes
1. **Schema Column Naming (`remediation-plan.md` vs `architecture-reflection.md`)**:  
   `architecture-reflection.md` Section 3 sketches `skill, jobs, salary_n, salary_mid_thb`. `remediation-plan.md` Task 2.1 defines:
   ```sql
   CREATE TABLE IF NOT EXISTS skill_stats (
       skill TEXT PRIMARY KEY,
       category TEXT,
       job_count INTEGER NOT NULL,
       salary_count INTEGER DEFAULT 0,
       avg_salary_thb INTEGER,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```
   We follow the explicit DDL in `remediation-plan.md` because storing `category` (`language`, `framework`, `database`, `cloud`, `tool`) allows the web dashboard to instantly group metrics without re-classifying strings in serverless memory.
2. **Aggregation Strategy (Python Pipeline vs Serverless SQL)**:  
   Rather than running complex `json_each` joins on serverless Vercel functions, the pipeline in `main.py` computes the rollup across all extracted jobs and applies a full replacement (`DELETE FROM skill_stats; INSERT INTO skill_stats ...`) in a single batch transaction. Next.js `/analytics` then only performs a lightweight `SELECT * FROM skill_stats ORDER BY job_count DESC`.
3. **Resilient Fallback**:  
   If `skill_stats` has zero rows (e.g. before the first rollup execution), `web/src/lib/turso.ts` falls back gracefully to querying `skills_extracted`, ensuring zero downtime or empty dashboards during deployment transitions.

---

## Current Behavior (Evidence)
1. **Full Table Scans on Every Page View**:  
   In `web/src/lib/turso.ts:140-158`, every request to `/analytics` runs:
   - `SELECT COUNT(*) AS total FROM jobs`
   - `SELECT COUNT(DISTINCT title) AS total FROM generated_projects`
   - `SELECT * FROM skills_extracted WHERE (experience_level IS NULL OR experience_level != 'Non-Tech')`
   - `SELECT s.skill_name, COUNT(DISTINCT j.id) as sample_count, ROUND(AVG((j.min_salary + j.max_salary) / 2)) as avg_salary FROM skills_extracted s JOIN jobs j ON s.job_id = j.id ...`
2. **Serverless CPU & Memory Overhead**:  
   In `web/src/lib/turso.ts:228-272`, Next.js parses JSON strings from every skill record in memory across 6 different columns on every visit, classifying into `KNOWN_LANGUAGES`, `KNOWN_CLOUDS`, etc. This amplifies Turso free-tier read quota consumption with traffic.
3. **Absence of Pre-Aggregated Rollup Table**:  
   Neither `schema.py`, `db.py`, nor `turso_client.py` has a `skill_stats` table or rollup calculation routine.

---

## Changes

### 1. `src/storage/schema.py`
- Define `SKILL_STATS_DDL`:
  ```python
  SKILL_STATS_DDL = """
      CREATE TABLE IF NOT EXISTS skill_stats (
          skill TEXT PRIMARY KEY,
          category TEXT,
          job_count INTEGER NOT NULL,
          salary_count INTEGER DEFAULT 0,
          avg_salary_thb INTEGER,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  """
  ```
- Add `SKILL_STATS_DDL` to `TABLE_STATEMENTS`.
- Add index statements to `INDEX_STATEMENTS`:
  - `CREATE INDEX IF NOT EXISTS idx_skill_stats_category ON skill_stats(category)`
  - `CREATE INDEX IF NOT EXISTS idx_skill_stats_job_count ON skill_stats(job_count DESC)`
- Update `EXPECTED_INDEXES` to include `idx_skill_stats_category` and `idx_skill_stats_job_count`.

### 2. `src/storage/db.py` (Local SQLite)
- Implement `refresh_skill_stats() -> int`:
  - Aggregates unique tech tags per job from `skills_extracted` (ignoring `experience_level == 'Non-Tech'`).
  - Joins with `jobs` where `currency = 'THB'`, `min_salary IS NOT NULL`, `max_salary IS NOT NULL` to calculate `salary_count` and `avg_salary_thb = round(avg((min + max) / 2))`.
  - Classifies categories (`language`, `framework`, `database`, `cloud`, `tool`, `other`).
  - Executes in a single transaction: `DELETE FROM skill_stats;` followed by `executemany("INSERT INTO skill_stats ...")`.
  - Returns total rows populated.
- Implement `get_skill_stats(category: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]`.

### 3. `src/storage/turso_client.py` (Turso LibSQL)
- Implement `refresh_skill_stats() -> int`:
  - Computes the aggregation dictionary.
  - Builds batch statements: `[("DELETE FROM skill_stats", [])]` and `[("INSERT INTO skill_stats (skill, category, job_count, salary_count, avg_salary_thb) VALUES (?, ?, ?, ?, ?)", [...]), ...]`.
  - Executes atomically using `self.client.batch(...)` (or fallback loop if batch unavailable).
- Implement `get_skill_stats(category: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]`.

### 4. `main.py`
- In `run_full_pipeline()` and `run_analytics_pipeline()`:
  - Call `active_storage.refresh_skill_stats()` right after LLM extraction / clustering step.
  - Log summary: `[Main] Pre-aggregated skill_stats rollup updated with N skills.`

### 5. `web/src/lib/turso.ts`
- In `getMarketAnalytics()`:
  - Query `skill_stats`:
    `SELECT skill, category, job_count, salary_count, avg_salary_thb FROM skill_stats ORDER BY job_count DESC`
  - If `skill_stats` contains rows:
    - Partition by `category` (`language` -> `languages`, `cloud` -> `clouds`, `database` -> `databases`, `framework` -> `frameworks`).
    - Map `top_compensated_skills` from rows with `salary_count >= 1` and `avg_salary_thb > 0` sorted by `avg_salary_thb DESC` (limit 10).
    - Skip the raw `SELECT * FROM skills_extracted` and in-memory parsing loop.
  - If `skill_stats` is empty or query fails:
    - Fall back to current `skills_extracted` query path.

---

## Tests to Add / Update

### In `tests/test_storage.py`:
1. `test_skill_stats_table_created`:
   - **Asserts**: Verifies that `skill_stats` table and its indexes (`idx_skill_stats_category`, `idx_skill_stats_job_count`) are created in SQLite and present in `EXPECTED_INDEXES`.
   - **Why it fails today**: `skill_stats` is not defined in `schema.py`.
2. `test_refresh_skill_stats_aggregates_counts_and_thb_salaries`:
   - **Asserts**: Inserts jobs with varying currencies (THB, USD, NULL) and skills. Runs `db.refresh_skill_stats()`. Verifies `job_count`, `salary_count`, and `avg_salary_thb` accurately match expected math, and that non-THB or missing salaries are excluded from salary calculations.
   - **Why it fails today**: `refresh_skill_stats()` does not exist.
3. `test_refresh_skill_stats_turso_batch`:
   - **Asserts**: Mocks `TursoClient.client.batch` and verifies `refresh_skill_stats()` issues an atomic batch containing a `DELETE FROM skill_stats` followed by `INSERT INTO skill_stats`.
   - **Why it fails today**: Method does not exist on `TursoClient`.

### In `tests/test_cli.py`:
4. `test_run_full_pipeline_refreshes_skill_stats`:
   - **Asserts**: Verifies that `run_full_pipeline` calls `refresh_skill_stats()` on active storage.
   - **Why it fails today**: `run_full_pipeline` does not invoke rollup refresh.

---

## Out of Scope
- Task 2.2: Statistically honest telemetry UI badges and n >= 5 threshold (Phase 2 next task).
- Task 2.3: ISR revalidation route (`/api/revalidate`) and webhook call from GitHub Actions.
- Task 2.4: Eliminating duplicate client mount query in `SkillGapMatcher.tsx`.

---

## Production Touch Points (Turso Database)

### Optional Cleanup / DDL (for operator to run against live Turso if desired):
```sql
-- Create table and indexes ahead of pipeline run (also handled automatically on startup by init_schema())
CREATE TABLE IF NOT EXISTS skill_stats (
    skill TEXT PRIMARY KEY,
    category TEXT,
    job_count INTEGER NOT NULL,
    salary_count INTEGER DEFAULT 0,
    avg_salary_thb INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_stats_category ON skill_stats(category);
CREATE INDEX IF NOT EXISTS idx_skill_stats_job_count ON skill_stats(job_count DESC);
```
