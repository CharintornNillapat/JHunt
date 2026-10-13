# Build Report: Task 2.1 — Pre-Aggregated Rollup Table (`skill_stats`)

**Task:** 2.1  
**Spec Reference:** `workflow/stages/01_spec/output/task-2.1-spec.md`  
**Test Suite:** 195 passed (`uv run python -m unittest discover tests`), `npm run lint` & `npm run build` passed.

---

## Changes Implemented

1. **`src/storage/schema.py` (Schema & Helper Definition)**:
   - Defined `SKILL_STATS_DDL` creating `skill_stats` (`skill TEXT PRIMARY KEY`, `category TEXT`, `job_count INTEGER NOT NULL`, `salary_count INTEGER DEFAULT 0`, `avg_salary_thb INTEGER`, `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`).
   - Added `SKILL_STATS_DDL` to `TABLE_STATEMENTS`.
   - Added `idx_skill_stats_category` and `idx_skill_stats_job_count` to `INDEX_STATEMENTS` and `EXPECTED_INDEXES`.
   - Added canonicalization and category classification helpers (`canonicalize_skill_name`, `classify_skill_category`, `aggregate_skill_stats`).

2. **`src/storage/db.py` (Local SQLite Rollup)**:
   - Implemented `refresh_skill_stats() -> int`: queries joined `skills_extracted` and `jobs` (filtering out `Non-Tech`), computes deduplicated skill metrics and THB average salaries, and executes a full replacement (`DELETE FROM skill_stats; INSERT INTO skill_stats ...`) in a single transaction.
   - Implemented `get_skill_stats(category=None, limit=None) -> List[Dict[str, Any]]`: retrieves sorted pre-aggregated stats.

3. **`src/storage/turso_client.py` (Turso LibSQL Rollup)**:
   - Implemented `refresh_skill_stats() -> int`: computes rollup and sends an atomic batch transaction containing `DELETE FROM skill_stats` followed by parameterized `INSERT INTO skill_stats` via `client.batch()`.
   - Implemented `get_skill_stats(category=None, limit=None) -> List[Dict[str, Any]]`: queries `skill_stats` from Turso cloud.

4. **`main.py` (Pipeline Rollup Refresh)**:
   - Invoked `active_storage.refresh_skill_stats()` in both `run_full_pipeline()` and `run_analyze_pipeline()` right after LLM extraction / clustering.
   - Logged summary message: `[Main] Pre-aggregated skill_stats rollup updated with N skills.`

5. **`web/src/lib/turso.ts` (Next.js Dashboard Integration & Resilient Fallback)**:
   - In `getMarketAnalytics()`: queries `skill_stats` first.
   - If `skill_stats` has rows, maps categories (`language`, `cloud`, `database`, `framework`) and `top_compensated_skills` directly from the rollup, eliminating table scans on `skills_extracted` and in-memory JSON parsing.
   - If `skill_stats` is empty or unavailable, seamlessly falls back to legacy raw scan of `skills_extracted`.

---

## Tests Added & Verified

- **`tests/test_storage.py`**:
  - `test_skill_stats_table_created`: Verifies `skill_stats` table and indexes are created in SQLite and present in `EXPECTED_INDEXES`.
  - `test_refresh_skill_stats_aggregates_counts_and_thb_salaries`: Verifies multi-job insertion with THB, non-THB, and missing salaries accurately calculates `job_count`, `salary_count`, and `avg_salary_thb` while excluding non-THB and `Non-Tech` rows.
  - `test_refresh_skill_stats_turso_batch`: Verifies `TursoClient.refresh_skill_stats()` issues an atomic batch containing `DELETE FROM skill_stats` and `INSERT INTO skill_stats`.
- **`tests/test_cli.py`**:
  - `test_run_full_pipeline_refreshes_skill_stats`: Verifies `run_full_pipeline` calls `refresh_skill_stats()` on active storage.

---

## Verification Status

- **Hermetic Unit Tests**: 195 passed, 0 failures, 0 errors (`uv run python -m unittest discover tests`).
- **Web Verification**:
  - `npm run lint` passed (clean exit 0).
  - `npm run build` passed (Turbopack production build compiled successfully in 1480ms, all routes generated cleanly).
- **Production Touch Points**: None executed by agent (no writes to live Turso, no Telegram messages sent, no Gemini quota spent).
- **Needs Human Operator**: Optional live Turso DDL provided in `workflow/stages/01_spec/output/task-2.1-spec.md`.
