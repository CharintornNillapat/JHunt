# Build Report: Task 7.2 - JobsDB Detail Fetch Circuit Breaker and Per-Run Dedupe

## Summary
- **Task ID**: 7.2
- **Status**: BUILT
- **Target**: Protect CI budget by implementing a per-run circuit breaker in JobsDBScraper that trips after 3 consecutive detail failures, and deduping job IDs before detail fetch across keywords in scrape().

---

## 1. Deliverables & Modified Files

### 1.1 `src/scrapers/jobsdb.py`
- **Class Constant**: Added `DETAIL_FAILURE_LIMIT = 3` next to `REQUEST_DELAY`.
- **Breaker State**: Initialized `self._detail_failures = 0` and `self._detail_breaker_open = False` in `__init__`, and reset both at the start of each `scrape()` run so each pipeline run gets a fresh attempt.
- **ID Normalization Helper**: Added `@staticmethod _normalize_id(item: Dict[str, Any]) -> Optional[str]` as the authoritative deduplication key provider maintaining the `jobsdb_{id}` prefix invariant.
- **Detail Branch Circuit Breaker**: Updated `_parse_job` to only attempt detail requests when `not self._detail_breaker_open`. On success, resets `_detail_failures = 0`. On failure (`detail_desc is None`), increments `_detail_failures`, and upon reaching `DETAIL_FAILURE_LIMIT`, sets `_detail_breaker_open = True` and logs a single warning. Falls back to listing teaser and bullet points.
- **Pre-Fetch Deduplication**: Updated `scrape()` loop over search results to check `job_id in seen_ids` before calling `_parse_job(item, ...)`, eliminating redundant detail HTTP requests and 1.0s sleeps for duplicate jobs appearing under multiple search keywords.
- **Docstring**: Updated `scrape()` docstring without em dashes.

### 1.2 `tests/test_scrapers.py`
- Added 4 hermetic unit tests to `TestJobsDBScraper`:
  1. `test_jobsdb_detail_breaker_trips_after_consecutive_failures`: Confirms breaker trips after 3 consecutive 404s, skipping subsequent detail requests and sleeps across 5 unseen jobs.
  2. `test_jobsdb_detail_breaker_resets_on_success`: Confirms consecutive failure counter resets on successful detail fetch, requiring 3 consecutive failures to trip.
  3. `test_jobsdb_duplicate_ids_across_keywords_not_refetched`: Confirms identical job IDs across multiple keywords are fetched only once, avoiding duplicate detail requests and sleeps.
  4. `test_jobsdb_failed_detail_id_not_refetched_under_later_keyword`: Confirms a job whose detail fetch failed under an earlier keyword is not refetched under later keywords.
- Confirmed that all 4 tests failed on the unmodified codebase before the implementation was applied.

### 1.3 `docs/contexts/task-ledger.md`
- Appended Task 7.2 under `#### Phase 7: Build & Dependency Hygiene (P7)` with checkbox checked.

---

## 2. Verification & Quality Gates

### 2.1 Test-First Regression Verification
- Command: `uv run python -m unittest tests.test_scrapers -v`
- Result before fix: **4 failed** (`test_jobsdb_detail_breaker_trips_after_consecutive_failures`, `test_jobsdb_detail_breaker_resets_on_success`, `test_jobsdb_duplicate_ids_across_keywords_not_refetched`, `test_jobsdb_failed_detail_id_not_refetched_under_later_keyword`), 26 passed.
- Result after fix: **30 passed in 5.565s** (OK, 0 failures, 0 errors).

### 2.2 Full Python Test Suite
- Command: `uv run python -m unittest discover tests`
- Result: **208 passed in 13.650s** (OK, 0 failures, 0 errors, completely hermetic).

### 2.3 Scope & Hygiene Verification
- `git diff --stat`: Strictly modified only `src/scrapers/jobsdb.py`, `tests/test_scrapers.py`, `docs/contexts/task-ledger.md`, and this build report.
- `Select-String` scan for em dashes (`\u2014`): 0 found across all touched files.

---

## 3. What Was NOT Verified
- Live outbound requests against JobsDB / SEEK detail endpoint (prohibited per hermetic testing and `AGENTS.md` rules).
- Live CI cron run in GitHub Actions.
