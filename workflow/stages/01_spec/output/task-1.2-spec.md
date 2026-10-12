# Plan: Task 1.2 — One-Time Historical Salary Backfill

**Date:** 2026-10-12  
**Task ID:** 1.2  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 1.2), `docs/audits/2026-10-12-architecture-reflection.md` (Section 1 row P1, Section 2.2)

---

## Goal
Backfill historical job records in storage by querying unparsed jobs (`min_salary IS NULL`), parsing their raw salary text and description with `parse_salary()`, and batch-updating `min_salary`, `max_salary`, and `currency` safely and idempotently.

---

## Disagreements / Alignment Notes
1. **New Top-Level Directory (`scripts/`)**:
   `docs/audits/2026-10-12-remediation-plan.md` proposes `scripts/backfill_salaries.py`. Because `scripts/` does not currently exist, creating it is a new top-level directory (which requires explicit user approval under `AGENTS.md`). In addition to `scripts/backfill_salaries.py`, a `main.py backfill-salaries` CLI subcommand will be provided so the routine can also be executed seamlessly from the main CLI entrypoint.
2. **Salary Source**:
   While the remediation plan highlights `salary IS NOT NULL`, many listings store the raw compensation in `raw_content` (job description) when `salary` was empty or `"Negotiable"`. The backfill engine will check raw `salary` text first, falling back to `description` in `raw_content` with anchor keywords, consistent with Task 1.1 rules.

---

## Current Behavior (Evidence)
- In production Turso, only 3 out of 259 rows have `min_salary` populated (`docs/audits/2026-10-12-architecture-reflection.md:12, 101`).
- Neither `DatabaseManager` nor `TursoClient` provides an interface to query jobs needing salary backfill or batch-update salary columns on existing records.
- Historical rows scraped prior to the introduction of salary parser columns remain `NULL`, starving downstream analytics (`web/src/app/analytics`) of compensation sample size.

---

## Changes

### 1. `src/storage/db.py` (Local SQLite Engine)
- Add `get_unparsed_salary_jobs(limit: Optional[int] = None) -> List[Dict[str, Any]]`:
  ```sql
  SELECT j.id, j.salary, j.raw_content
  FROM jobs j
  WHERE j.min_salary IS NULL AND j.max_salary IS NULL
    AND (
      (j.salary IS NOT NULL AND trim(j.salary) != '')
      OR (j.raw_content IS NOT NULL AND trim(j.raw_content) != '')
    )
  ORDER BY j.created_at DESC
  ```
- Add `update_job_salaries_batch(updates: List[Dict[str, Any]]) -> int`:
  - Parameterized `UPDATE jobs SET min_salary = ?, max_salary = ?, currency = ? WHERE id = ?`.

### 2. `src/storage/turso_client.py` (Cloud LibSQL Engine)
- Add `get_unparsed_salary_jobs(limit: Optional[int] = None) -> List[Dict[str, Any]]`:
  - Matching parameterized query for Turso.
- Add `update_job_salaries_batch(updates: List[Dict[str, Any]]) -> int`:
  - Parameterized updates against Turso client.

### 3. `scripts/backfill_salaries.py` (Standalone Backfill Tool)
- Self-contained CLI tool supporting:
  - `--dry-run` (default: True, previews candidate updates without writing).
  - `--apply` (writes updates to active storage).
  - `--limit <N>` (optional batch capping).
  - Summary report printed with utf-8 encoding: total candidates, newly parsed count, currency breakdown.

### 4. `main.py` (CLI Subcommand)
- Register `backfill-salaries` subcommand routing to backfill engine:
  ```powershell
  uv run python main.py backfill-salaries --dry-run
  uv run python main.py backfill-salaries --apply
  ```

### 5. `docs/contexts/task-ledger.md`
- Mark Task 1.2 complete upon verification.

---

## Tests to Add

### In `tests/test_storage.py`:
1. `test_get_unparsed_salary_jobs`:
   - **Asserts**: Inserts one job with `min_salary=None, salary='30k'` and one with `min_salary=50000`. Verifies only the unparsed job is returned.
   - **Why it fails today**: Method `get_unparsed_salary_jobs` does not exist.
2. `test_update_job_salaries_batch`:
   - **Asserts**: Batch-updates salary fields and verifies values in SQLite.
   - **Why it fails today**: Method `update_job_salaries_batch` does not exist.
3. `test_turso_update_job_salaries_batch_mock`:
   - **Asserts**: Calls `turso.update_job_salaries_batch()` on mock client; verifies parameterized `UPDATE` statement execution.
   - **Why it fails today**: Method does not exist on `TursoClient`.

### In `tests/test_cli.py`:
4. `test_backfill_salaries_dry_run_leaves_db_unchanged`:
   - **Asserts**: Running backfill with dry-run parses candidates but leaves `min_salary` as `NULL`.
   - **Why it fails today**: Subcommand / backfill module does not exist.
5. `test_backfill_salaries_apply_persists_parsed_values`:
   - **Asserts**: Running backfill with `--apply` updates the database rows with parsed salaries.
   - **Why it fails today**: Subcommand / backfill module does not exist.

---

## Out of Scope
- Altering existing non-null salaries.
- Web UI or Next.js changes.
- Gemini extraction quota.

---

## Production Touch Points (Turso Database)

### Read-Only Pre-Check (run by human before applying):
```sql
SELECT 
    COUNT(*) AS total_jobs,
    SUM(CASE WHEN min_salary IS NOT NULL THEN 1 ELSE 0 END) AS already_parsed,
    SUM(CASE WHEN min_salary IS NULL AND salary IS NOT NULL AND trim(salary) != '' THEN 1 ELSE 0 END) AS unparsed_with_salary_header,
    SUM(CASE WHEN min_salary IS NULL THEN 1 ELSE 0 END) AS total_unparsed
FROM jobs;
```

### Execution Command (run by human after implementation):
```powershell
# 1. Preview changes (no database writes):
uv run python main.py backfill-salaries --dry-run

# 2. Apply changes to active database:
uv run python main.py backfill-salaries --apply
```

### Read-Only Post-Check:
```sql
SELECT 
    COUNT(*) AS total_jobs,
    SUM(CASE WHEN min_salary IS NOT NULL THEN 1 ELSE 0 END) AS now_parsed,
    SUM(CASE WHEN min_salary IS NULL THEN 1 ELSE 0 END) AS remaining_unparsed
FROM jobs;
```
