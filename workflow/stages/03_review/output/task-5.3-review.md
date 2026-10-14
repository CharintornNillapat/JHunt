# Review: Task 5.3: JobsDB Scraper Detail Page Fetch for Unseen Jobs

**Date:** 2026-10-14  
**Task ID:** 5.3  
**Reviewer:** Review Agent  
**Status:** APPROVED  
**Target:** `src/scrapers/jobsdb.py`, `tests/test_scrapers.py`, `docs/contexts/task-ledger.md`  

---

## 1. Executive Summary

Task 5.3 upgrades the JobsDB scraper adapter (`src/scrapers/jobsdb.py`) to query SEEK's detail REST API endpoint for newly discovered, unseen jobs. This provides rich, complete job descriptions to downstream LLM skill extraction and salary parsing pipelines. At the same time, known job IDs (`known_ids`) bypass detail round-trips to prevent redundant network calls and rate-limiting issues. All changes are verified hermetically with four targeted unit tests in `tests/test_scrapers.py`.

---

## 2. Deliverables & Invariants Verification

### 2.1 JobsDB Scraper Implementation (`src/scrapers/jobsdb.py`)
- **Detail URL Constant**: Defined `DETAIL_URL = "https://th.jobsdb.com/api/jobsearch/v5/job/{job_id}"`.
- **Configurable Detail Fetching**: Added `fetch_details: bool = True` to `__init__()`.
- **Detail Extraction Method (`_fetch_detail_description`)**:
  - Queries `DETAIL_URL` with `self.BASE_PARAMS` and `timeout=self.TIMEOUT`.
  - Resiliently extracts content from nested candidate paths (`jobDetail`, `description`, `content`, `job.content`, `jobDetail.job.content`).
  - Strips HTML tags (`re.sub(r"<[^>]+>", " ", text)`), unescapes HTML entities, and normalizes whitespace.
  - Fail-open error handling: catches `requests.exceptions.RequestException` and general exceptions, logging warnings and returning `None`.
- **Parsing Logic & Optimization (`_parse_job`)**:
  - Accepts `known_ids: Optional[set[str]] = None`.
  - If `job_id in known_ids`: skips detail request and retains fast search fallback description (teaser and bullet points).
  - If unseen and `fetch_details=True`: enforces rate-limit throttle `time.sleep(self.REQUEST_DELAY)`, requests detail text, and falls back to teaser/bullets on any failure.
  - Passes final resolved `description` to `parse_salary(salary_str, description)` to maximize unstructured salary discovery.
- **Batch Ingestion Loop (`scrape`)**:
  - Forwards `known_ids=known_ids` into `_parse_job(item, known_ids=known_ids)`.

### 2.2 Hermetic Test Suite Coverage (`tests/test_scrapers.py`)
- Added `@patch("time.sleep")` to existing tests to ensure fast, non-blocking execution.
- Added four targeted unit tests in `TestJobsDBScraper`:
  1. `test_jobsdb_skips_detail_fetch_for_known_ids`: Confirms known IDs bypass detail requests (`mock_get.call_count == 1`) and preserve fallback descriptions.
  2. `test_jobsdb_detail_fetch_success_for_unseen_job`: Verifies detail JSON parsing, HTML tag stripping, description assignment, and `REQUEST_DELAY` throttling.
  3. `test_jobsdb_detail_fetch_failure_falls_back_to_teaser`: Confirms that network timeouts on detail requests fail open without crashing.
  4. `test_jobsdb_fetch_details_disabled`: Confirms that setting `fetch_details=False` disables all detail GET requests.
- All tests execute hermetically with zero real outbound network traffic.

### 2.3 Task Ledger (`docs/contexts/task-ledger.md`)
- Task 5.3 marked complete under Phase 5.

---

## 3. Verification & Quality Gates

### 3.1 Python Hermetic Test Suite
- **Command**: `uv run python -m unittest discover tests`
- **Result**: **203 passed in 16.461s** (0 failures, 0 errors, completely offline).
- **Hermetic Integrity**: Full test suite runs offline with mocked clients and blanked credentials; zero network requests made.

### 3.2 Next.js Web Build & Lint
- **Command**: `cd web; npm run lint ; npm run build`
- **Result**:
  - `eslint`: 0 warnings, 0 errors.
  - `next build`: Next.js 16.4.0 (Turbopack) compiled cleanly and validated all static and dynamic routes.

### 3.3 Style & antislop Protocol Compliance
- **R-02 (Copywriting)**: 0 em dashes introduced across all touched files.
- **R-35 (Craftsmanship)**: Clean error handling, exact ID prefix preservation, and strict backward compatibility.

---

## 4. What Was NOT Verified
- Live network requests against SEEK production servers (`python main.py run ...` is restricted per `AGENTS.md` safety rules).

---

## 5. Conclusion
Task 5.3 meets all requirements defined in `workflow/stages/01_spec/output/task-5.3-spec.md`. The implementation is approved.
