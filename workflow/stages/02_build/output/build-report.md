# Build Report: Task 1.2 — One-Time Historical Salary Backfill

**Task:** 1.2  
**Spec Reference:** `workflow/stages/01_spec/output/task-1.2-spec.md`  
**Test Suite:** 178 passed (`uv run python -m unittest discover tests`)

---

## Changes Implemented

1. **`src/storage/db.py` (Local SQLite Engine)**:
   - Implemented `get_unparsed_salary_jobs(limit: Optional[int] = None) -> List[Dict[str, Any]]`: Queries `jobs` where `min_salary IS NULL AND max_salary IS NULL` with non-empty `salary` or `raw_content`, ordered by `created_at DESC`.
   - Implemented `update_job_salaries_batch(updates: List[Dict[str, Any]]) -> int`: Parameterized batch `UPDATE jobs SET min_salary = ?, max_salary = ?, currency = ? WHERE id = ?`.

2. **`src/storage/turso_client.py` (Cloud LibSQL Engine)**:
   - Implemented `get_unparsed_salary_jobs(limit: Optional[int] = None) -> List[Dict[str, Any]]`: Queries Turso client with parameterized query and unpacks `raw_content` into standardized job dicts.
   - Implemented `update_job_salaries_batch(updates: List[Dict[str, Any]]) -> int`: Parameterized batch update executed via `_run_batch`.

3. **`src/extractor/salary_backfill.py` (Backfill Engine)**:
   - Implemented `backfill_salaries(storage, limit, dry_run)`:
     - Fetches candidate unparsed jobs from active storage.
     - Parses `salary` and `description` (from `raw_content`) via deterministic `parse_salary()`.
     - In `--apply` mode (`dry_run=False`), writes batch updates to storage.
     - Tracks metrics: candidate count, newly parsed count, applied count, and currency frequency.
     - Wrapped execution in `try ... finally:` ensuring caller or locally owned storage is closed cleanly.

4. **`scripts/backfill_salaries.py` (Standalone Backfill Tool)**:
   - Standalone CLI runner with `--dry-run` (default), `--apply`, and `--limit <N>`.
   - Reconfigures stdout for UTF-8 on Windows and prints summary table.
   - Wrapped execution in `try ... finally:` to invoke `if hasattr(storage, "close"): storage.close()`, resolving open `aiohttp` session/connector leak.

5. **`main.py` (CLI Subcommand)**:
   - Registered `backfill-salaries` subcommand with `--dry-run` and `--apply` mutually exclusive options and `--limit`.
   - Implemented `run_backfill_pipeline` routing to backfill engine.
   - Wrapped execution in `try ... finally:` to invoke `if hasattr(storage, "close"): storage.close()`, resolving open `aiohttp` session/connector leak.

6. **`docs/contexts/task-ledger.md`**:
   - Marked Task 1.2 complete under Phase 1.

---

## Tests Added & Verified

- **`tests/test_storage.py`**:
  - `test_get_unparsed_salary_jobs`: Asserts retrieval of unparsed jobs with salary or raw_content, excluding already-parsed records.
  - `test_update_job_salaries_batch`: Asserts parameterized batch update of `min_salary`, `max_salary`, `currency`.
  - `test_turso_get_unparsed_salary_jobs_with_mock`: Asserts mock Turso execute call with parameterized SQL and unpacked fields.
  - `test_turso_update_job_salaries_batch_mock`: Asserts batch updates executed with parameterized statements.
- **`tests/test_cli.py`**:
  - `test_backfill_salaries_subcommand_args`: Verifies `--dry-run`, `--apply`, and `--limit` flag parsing.
  - `test_main_routes_backfill_salaries`: Verifies `main.py` subcommand routing.
  - `test_backfill_salaries_dry_run_leaves_db_unchanged`: Asserts dry-run parses candidates while leaving database rows `NULL`.
  - `test_backfill_salaries_apply_persists_parsed_values`: Asserts apply mode persists parsed values to SQLite.
  - `test_standalone_script_backfill_salaries`: Asserts `scripts/backfill_salaries.py` runs cleanly in both dry-run and apply modes.
  - `test_run_backfill_pipeline_closes_storage_in_finally`: Verifies `main.py:run_backfill_pipeline` invokes `storage.close()` upon normal exit and exceptions.
  - `test_scripts_backfill_salaries_closes_storage_in_finally`: Verifies `scripts/backfill_salaries.py:main` invokes `storage.close()` upon normal exit and exceptions.

---

## Verification Status

- **Hermetic Unit Tests**: 178 passed, 0 failures, 0 errors.
- **Production Execution**: Live Turso database run has NOT been executed (per `AGENTS.md` policy; human must run `uv run python main.py backfill-salaries --dry-run` followed by `--apply`).
