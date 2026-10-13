# Build Report: Task 1.4 — Schema & Index Reconciliation

**Task:** 1.4  
**Spec Reference:** `workflow/stages/01_spec/output/task-1.4-spec.md`  
**Test Suite:** 187 passed (`uv run python -m unittest discover tests`)

---

## Changes Implemented

1. **`src/storage/schema.py` (Schema & Index Alignment)**:
   - Updated `GENERATED_PROJECTS_DDL` to remove the virtual `target_role` column, matching live Turso table structure.
   - Updated `INDEX_STATEMENTS`:
     - Changed `"CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects(target_role)"` to `"CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects(role)"`.
     - Pruned obsolete write-overhead indexes: `idx_jobs_posted_at`, `idx_jobs_source`, and `idx_skills_experience`.
   - Updated `EXPECTED_INDEXES` to match active index set (`idx_skills_name`, `idx_skills_job_id`, `idx_projects_created_at`, `idx_projects_role`).

2. **`src/storage/turso_client.py` (Defensive Table DDL Execution)**:
   - Enclosed table DDL execution in `init_schema()` in a defensive `try ... except` block with warning logging.
   - Falls back gracefully to isolated execution of each table statement if `self.client.batch(table_stmts)` fails.

3. **`src/storage/db.py` (Migration Cleanup)**:
   - Removed the obsolete virtual column migration check for `target_role` in `_init_db()` (`PRAGMA table_xinfo` check and `ALTER TABLE generated_projects ADD COLUMN target_role`).
   - Retained table migrations and cleanly executed updated `SCHEMA_STATEMENTS`.

---

## Tests Added & Verified

- **`tests/test_storage.py`**:
  - `test_idx_projects_role_indexes_role_column`: Verifies `idx_projects_role` is created on column `role` and present in `sqlite_master` without requiring `target_role`.
  - `test_obsolete_indexes_removed_from_expected_indexes`: Verifies `idx_jobs_posted_at`, `idx_jobs_source`, and `idx_skills_experience` are absent from `EXPECTED_INDEXES` and `ALL_INDEX_STATEMENTS`.
  - `test_turso_init_schema_table_batch_failure_falls_back_to_isolated_statements`: Verifies table batch failures fall back to isolated single-statement execution without crashing `init_schema()`.
  - `test_turso_init_schema_no_target_role_warning`: Simulates a Turso database with `generated_projects` without `target_role`; verifies `init_schema()` completes with batch success and zero `target_role` warnings.

---

## Verification Status

- **Hermetic Unit Tests**: 187 passed, 0 failures, 0 errors.
- **Production Touch Points**: None executed by agent (zero writes to Turso, zero Telegram calls, zero Gemini network calls).
- **Needs Human Operator**: Optional live Turso index cleanup SQL provided in `workflow/stages/01_spec/output/task-1.4-spec.md`.
