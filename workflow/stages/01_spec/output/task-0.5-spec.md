# Plan: Task 0.5 — Prevent Ingestion Queue Starvation & Poison Record Deadlock

**Date:** 2026-10-12  
**Task ID:** 0.5  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 0.5), `docs/audits/2026-10-12-architecture-reflection.md` (Section 1 & 2)

---

## Goal
Eliminate queue starvation by ordering unprocessed jobs by newest first (`ORDER BY j.created_at DESC`) and bypassing poison records after 3 extraction failures using an `extract_attempts` counter.

---

## Disagreements / Alignment Notes
- None. `2026-10-12-remediation-plan.md` (Task 0.5) and `2026-10-12-architecture-reflection.md` (Section 1 row P1 and Section 2) agree on `ORDER BY created_at DESC`, adding `extract_attempts INTEGER DEFAULT 0` to `jobs`, and filtering with `extract_attempts < 3`.

---

## Current Behavior (Evidence)
1. **Oldest-First Queue Starvation:**  
   In `src/storage/db.py:218` and `src/storage/turso_client.py:575`, `get_unprocessed_jobs()` uses `ORDER BY j.created_at ASC`. If an early batch encounters an unexpected failure (safety filters, unparseable response, or malformed data), those same oldest records are perpetually returned at the front of the queue, preventing newly scraped jobs from ever being extracted.
2. **Missing Poison Record Bypass & Attempt Tracking:**  
   Neither `jobs` in `src/storage/schema.py` nor Turso's live table contains an `extract_attempts` column. In `src/extractor/llm_extractor.py:213-214`, when an unexpected exception occurs in `extractor.extract_batch(batch)` or when items in a batch are returned unanswered, no attempt counter is incremented. Consequently, problematic records remain in the queue indefinitely.

---

## Changes

### 1. `src/storage/schema.py`
- Add `extract_attempts INTEGER DEFAULT 0` to `jobs` table definition in `TABLE_STATEMENTS`:
  ```sql
  CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      company TEXT NOT NULL,
      url TEXT NOT NULL,
      location TEXT,
      salary TEXT,
      work_type TEXT,
      raw_content TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      posted_at TIMESTAMP,
      source TEXT,
      min_salary INTEGER,
      max_salary INTEGER,
      currency TEXT DEFAULT 'THB',
      extract_attempts INTEGER DEFAULT 0
  )
  ```

### 2. `src/storage/db.py`
- In `_init_db()`:
  - Add self-healing migration for local SQLite:
    ```python
    if "extract_attempts" not in jobs_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN extract_attempts INTEGER DEFAULT 0")
    ```
- In `get_unprocessed_jobs(limit=None)`:
  - Update query to order descending and filter out poison records (`extract_attempts < 3` or `NULL`):
    ```sql
    SELECT j.*
    FROM jobs j
    LEFT JOIN skills_extracted s ON j.id = s.job_id
    WHERE s.job_id IS NULL AND (j.extract_attempts IS NULL OR j.extract_attempts < 3)
    ORDER BY j.created_at DESC
    ```
- Add `increment_extract_attempts(job_ids: List[str]) -> None`:
  - Parameterized update without f-string or string concatenation:
    ```python
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
    ```

### 3. `src/storage/turso_client.py`
- In `_migrate_jobs_schema()`:
  - Add self-healing migration for Turso:
    ```python
    if "extract_attempts" not in cols:
        try:
            logger.info("[TursoClient] Adding missing column 'extract_attempts' to jobs...")
            self._execute_ddl("ALTER TABLE jobs ADD COLUMN extract_attempts INTEGER DEFAULT 0;")
            cols.add("extract_attempts")
        except Exception as e:
            logger.warning(f"[TursoClient] Failed to add column 'extract_attempts': {e}")
    ```
- In `get_unprocessed_jobs(limit=None)`:
  - Update query to order descending and filter out poison records (`extract_attempts < 3` or `NULL`):
    ```sql
    SELECT j.*
    FROM jobs j
    LEFT JOIN skills_extracted s ON j.id = s.job_id
    WHERE s.job_id IS NULL AND (j.extract_attempts IS NULL OR j.extract_attempts < 3)
    ORDER BY j.created_at DESC
    ```
- Add `increment_extract_attempts(job_ids: List[str]) -> None`:
  - Parameterized single/batched execution for Turso:
    ```python
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
    ```

### 4. `src/extractor/llm_extractor.py`
- In `extract_unprocessed_jobs()`:
  - When a batch fails unexpectedly (non-quota exception):
    ```python
    except Exception as e:
        logger.warning(f"[BatchExtractor] Batch {n}/{len(batches)} failed unexpectedly ({e}); left queued.")
        failed_ids = [str(job["id"]) for job in batch]
        if hasattr(active_storage, "increment_extract_attempts"):
            active_storage.increment_extract_attempts(failed_ids)
        if turso and turso is not active_storage and hasattr(turso, "increment_extract_attempts"):
            turso.increment_extract_attempts(failed_ids)
        continue
    ```
  - When a batch succeeds but some jobs are missing from `results` (unanswered by model):
    ```python
    missing_ids = [str(job["id"]) for job in batch if str(job["id"]) not in results]
    if missing_ids:
        if hasattr(active_storage, "increment_extract_attempts"):
            active_storage.increment_extract_attempts(missing_ids)
        if turso and turso is not active_storage and hasattr(turso, "increment_extract_attempts"):
            turso.increment_extract_attempts(missing_ids)
    ```
  - Note: `DailyQuotaExhaustedError` is preserved as-is without incrementing attempts, since quota depletion is an infrastructure limit rather than record poison.

### 5. `docs/contexts/task-ledger.md`
- Mark Task 0.5 as complete upon verification.

---

## Tests to Add

### In `tests/test_storage.py`:
1. `test_get_unprocessed_jobs_orders_descending`:
   - **Asserts**: Inserts jobs with explicit different `created_at` timestamps; asserts `get_unprocessed_jobs()` returns the newest posting first.
   - **Why it fails today**: Current SQL query specifies `ORDER BY j.created_at ASC`, returning the oldest job first.
2. `test_get_unprocessed_jobs_skips_poison_records`:
   - **Asserts**: Inserts a job with `extract_attempts = 3`; asserts `get_unprocessed_jobs()` ignores it.
   - **Why it fails today**: No `extract_attempts` filtering exists in the query.
3. `test_increment_extract_attempts_increments_counter`:
   - **Asserts**: Calls `db.increment_extract_attempts([job_id])` and verifies the database counter increments from 0 to 1, then to 2.
   - **Why it fails today**: Method `increment_extract_attempts` does not exist on `DatabaseManager`.
4. `test_turso_get_unprocessed_jobs_query_includes_desc_and_attempts_filter`:
   - **Asserts**: Calls `turso.get_unprocessed_jobs()` on mock Turso client; verifies executed SQL contains `ORDER BY j.created_at DESC` and `(j.extract_attempts IS NULL OR j.extract_attempts < 3)`.
   - **Why it fails today**: SQL query contains `ORDER BY j.created_at ASC` and lacks attempt filtering.
5. `test_turso_increment_extract_attempts`:
   - **Asserts**: Calls `turso.increment_extract_attempts(["job_1"])`; verifies client executes parameterized `UPDATE jobs SET extract_attempts ...`.
   - **Why it fails today**: Method `increment_extract_attempts` does not exist on `TursoClient`.

### In `tests/test_extractor.py`:
6. `test_unexpected_batch_failure_increments_extract_attempts`:
   - **Asserts**: Mocks unexpected exception in `extractor.extract_batch`; verifies `active_storage.increment_extract_attempts` is called with the batch's job IDs.
   - **Why it fails today**: Unexpected exceptions are caught and logged with `continue`, without calling `increment_extract_attempts`.
7. `test_unanswered_jobs_in_batch_increment_extract_attempts`:
   - **Asserts**: When `extract_batch` returns results for only a subset of the batch, verifies `active_storage.increment_extract_attempts` is called for the missing job IDs.
   - **Why it fails today**: Unanswered jobs are logged without updating attempt counters.

---

## Out of Scope
- Splitting a failed batch in half recursively (deferred to Phase 1 P1 tasks).
- Changing extraction batch size (stays 15 jobs per request).
- Web dashboard API or Next.js changes.

---

## Production Touch Points

### Turso Database DDL (for human to run if applying manually):
**Pre-check (Read-only):**
```sql
PRAGMA table_info(jobs);
```
*If `extract_attempts` is not in the column list:*
```sql
ALTER TABLE jobs ADD COLUMN extract_attempts INTEGER DEFAULT 0;
```
*Note: `TursoClient._migrate_jobs_schema()` will also perform this migration automatically on startup in a defensive try/except block.*

### Telegram / Gemini / CI:
- **Telegram**: No messages sent.
- **Gemini**: No quota spent; tests use hermetic mocks.
- **CI**: No workflow YAML modifications required.
