# Plan: Task 1.4 — Schema & Index Reconciliation

**Date:** 2026-10-13  
**Task ID:** 1.4  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 1.4), `docs/audits/2026-10-12-architecture-reflection.md` (Section 2.3, Section 3.1 P1 row), `AGENTS.md` (Storage invariants)

---

## Goal
Reconcile database indexes and schema definitions by indexing `generated_projects(role)` instead of virtual `target_role`, pruning obsolete write-overhead indexes (`idx_jobs_posted_at`, `idx_jobs_source`, `idx_skills_experience`), and guarding all DDL execution in `TursoClient.init_schema()` with defensive error handling.

---

## Disagreements / Alignment Notes
1. **`target_role` vs `role`**:
   `AGENTS.md` notes: `"in Turso, skills_extracted.job_id is the PRIMARY KEY, and generated_projects has no target_role column."`
   `schema.py` previously defined `idx_projects_role ON generated_projects(target_role)`, which provoked `SQL_INPUT_ERROR: no such column: target_role` on Turso whenever indexes were created. Aligning the index statement to `idx_projects_role ON generated_projects(role)` eliminates the error and correctly speeds up queries filtering by `role`.
2. **Production Index Dropping**:
   Per `AGENTS.md`, any SQL modifying production Turso (`DROP INDEX`) will not be executed directly by agents. The DDL for dropping the obsolete indexes from live Turso is provided under **Production Touch Points** for the operator to run.

---

## Current Behavior (Evidence)
1. **Failing Index in CI and Local Startup (`idx_projects_role`)**:  
   In `src/storage/schema.py:29`, `idx_projects_role` targets `generated_projects(target_role)`. Live Turso has no `target_role` column, producing a recurring warning:  
   `[WARNING] [TursoClient] Batch index creation failed (SQL_INPUT_ERROR: no such column: target_role)`.
2. **Obsolete Indexes Imposing Write Overhead**:  
   In `src/storage/schema.py:24-27`:
   - `idx_jobs_posted_at ON jobs(posted_at DESC)` is never referenced by any application query in `src/` or `web/`.
   - `idx_jobs_source ON jobs(source)` is never queried.
   - `idx_skills_experience ON skills_extracted(experience_level)` indexes a low-cardinality column that only participates in `!=` checks.
3. **Table DDL Lacks Defensive Error Handling in `TursoClient.init_schema()`**:  
   In `src/storage/turso_client.py:326-333`, table creation DDL (`self.client.batch(table_stmts)`) runs outside a `try ... except` block. If a table creation statement raises a transient or non-fatal error, `init_schema()` crashes rather than falling back gracefully.

---

## Changes

### 1. `src/storage/schema.py`
- Update `GENERATED_PROJECTS_DDL` to remove the virtual `target_role` column definition so the DDL matches Turso's live table structure.
- Update `INDEX_STATEMENTS`:
  - Change `"CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects(target_role)"` to `"CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects(role)"`.
  - Remove `"CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC)"`.
  - Remove `"CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)"`.
  - Remove `"CREATE INDEX IF NOT EXISTS idx_skills_experience ON skills_extracted(experience_level)"`.
- Update `EXPECTED_INDEXES` accordingly:
  - Keep: `idx_skills_name`, `idx_skills_job_id`, `idx_projects_created_at`, `idx_projects_role`.
  - Exclude: `idx_jobs_posted_at`, `idx_jobs_source`, `idx_skills_experience`.

### 2. `src/storage/turso_client.py`
- Enclose table DDL execution in `init_schema()` in a defensive `try ... except` block:
  - If `self.client.batch(table_stmts)` fails, log a warning and fall back to isolated execution of each table statement.
- Ensure index creation in `_create_indexes()` continues to execute cleanly without batch failure warnings on `target_role`.

### 3. `src/storage/db.py`
- Remove the obsolete virtual column migration check for `target_role` in `_init_db()` (`PRAGMA table_xinfo` check and `ALTER TABLE generated_projects ADD COLUMN target_role`).
- Retain existing table migrations and apply updated `SCHEMA_STATEMENTS`.

---

## Tests to Add / Update

### In `tests/test_storage.py`:
1. `test_idx_projects_role_indexes_role_column`:
   - **Asserts**: Verifies that `idx_projects_role` is created on column `role` and present in `sqlite_master` without requiring `target_role`.
   - **Why it fails today**: `schema.py` attempts to index `target_role`.
2. `test_obsolete_indexes_removed_from_expected_indexes`:
   - **Asserts**: Verifies that `idx_jobs_posted_at`, `idx_jobs_source`, and `idx_skills_experience` are absent from `EXPECTED_INDEXES` and `ALL_INDEX_STATEMENTS`.
   - **Why it fails today**: `EXPECTED_INDEXES` currently includes all three obsolete indexes.
3. `test_turso_init_schema_table_batch_failure_falls_back_to_isolated_statements`:
   - **Asserts**: Mocks `client.batch` to fail on table statements; verifies `init_schema()` does not crash and executes statements individually.
   - **Why it fails today**: `init_schema()` table creation lacks defensive fallback handling.
4. `test_turso_init_schema_no_target_role_warning`:
   - **Asserts**: Simulates a Turso database with `generated_projects` without `target_role`; verifies `init_schema()` completes with batch success and zero `target_role` errors.
   - **Why it fails today**: Batch index creation fails due to missing `target_role`.

---

## Out of Scope
- Dropping indexes in live production Turso directly (human operator will run).
- Task 1.5: Blueprint prompt constraints and markdown exporter polish.
- Phase 2: `skill_stats` rollup table creation.

---

## Production Touch Points (Turso Database)

### Optional Cleanup SQL (for human operator to run against live Turso):
```sql
-- Drop obsolete unused indexes
DROP INDEX IF EXISTS idx_jobs_posted_at;
DROP INDEX IF EXISTS idx_jobs_source;
DROP INDEX IF EXISTS idx_skills_experience;

-- Re-create role index on the actual 'role' column if needed
DROP INDEX IF EXISTS idx_projects_role;
CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects(role);
```
