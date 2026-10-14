# Plan: Task 5.3: JobsDB Scraper Detail Page Fetch for Unseen Jobs

**Date:** 2026-10-14  
**Task ID:** 5.3  
**Reference:** `docs/contexts/task-ledger.md` (Phase 5), `src/scrapers/jobsdb.py`, `src/scrapers/base.py`, `tests/test_scrapers.py`, `antislop` Skill Suite (Mode 1 DURING)  

---

## Goal

Upgrade the JobsDB scraper (`src/scrapers/jobsdb.py`) to fetch full job descriptions from SEEK's detail API endpoint for newly discovered, unseen jobs while bypassing detail network requests for known IDs, backed by resilient error handling, request throttling, and hermetic unit tests in `tests/test_scrapers.py`.

---

## antislop & Engineering Protocol (Mode 1: DURING)

This specification strictly adheres to the `antislop` suite (`antislop`, `antislop-code`, `antislop-copywriting`) and repository invariants:

1. **R-02 (Copywriting)**:
   - Zero em-dashes anywhere in source code, docstrings, logger messages, or markdown documentation.
   - Use colons, hyphens, periods, or parentheses instead.
2. **R-35 (Craftsmanship Verification)**:
   - Resilient detail parsing: support nested JSON payloads (`jobDetail`, `description`, `content`, `job.content`) and HTML tag stripping with entity unescaping.
   - Fail-open fallback: any detail fetch network failure, timeout, or non-200 response must gracefully fall back to teaser and bullet points without interrupting the ingestion loop.
   - Rate limit respect: enforce `time.sleep(self.REQUEST_DELAY)` between detail requests for unseen jobs.
   - Hermetic test suite: all unit tests must mock `requests.Session.get` and patch `time.sleep` with zero outbound network calls.
3. **Repository Guardrails & Invariants (`AGENTS.md`)**:
   - Job IDs maintain prefix: `jobsdb_{raw_id}`.
   - `_validate_job` invariant: salary field remains optional; do not drop jobs with empty salary.
   - Parameterized, non-destructive, and offline-verified.

---

## Current Behavior (Evidence)

1. **Teaser-Only Descriptions (`src/scrapers/jobsdb.py:91-100`)**:
   - `_parse_job()` only constructs a description from the top-level search listing's `teaser` and `bulletPoints`:
     ```python
     teaser = (item.get("teaser") or "").strip()
     bullet_points = [str(b).strip() for b in (item.get("bulletPoints") or []) if str(b).strip()]
     desc_parts = []
     if teaser:
         desc_parts.append(teaser)
     if bullet_points:
         desc_parts.append("\n".join(f"- {b}" for b in bullet_points))
     description = "\n\n".join(desc_parts) if desc_parts else None
     ```
   - Search listings omit full responsibilities, detailed qualifications, and specific framework requirements, constraining Gemini tech skill extraction and salary parser context.

2. **Missing `known_ids` Optimization (`src/scrapers/jobsdb.py:125-175`)**:
   - Although `scrape()` accepts `known_ids: Optional[set[str]] = None`, it does not forward `known_ids` to `_parse_job()`.
   - In contrast, both `BlognoneScraper` (`src/scrapers/blognone.py:192`) and `JobThaiScraper` (`src/scrapers/jobthai.py:201`) use `known_ids` to bypass detail network round-trips for previously seen jobs.

3. **No Detail Endpoint Definition**:
   - `JobsDBScraper` has `SEARCH_URL` and `JOB_URL`, but lacks `DETAIL_URL` for SEEK's public job detail REST API (`https://th.jobsdb.com/api/jobsearch/v5/job/{job_id}`).

---

## Changes

### 1. Scraper Implementation (`src/scrapers/jobsdb.py`)

- **Class Constants & Imports**:
  - Ensure `import html` and `import re` are imported.
  - Define endpoint:
    ```python
    DETAIL_URL = "https://th.jobsdb.com/api/jobsearch/v5/job/{job_id}"
    ```

- **Constructor**:
  ```python
  def __init__(self, keywords: Optional[List[str]] = None, fetch_details: bool = True):
      super().__init__()
      self.default_keywords = [kw.strip() for kw in (keywords or []) if kw.strip()]
      self.fetch_details = fetch_details
      self.session = self._build_session()
  ```

- **Detail Fetch Method (`_fetch_detail_description`)**:
  - Add method `_fetch_detail_description(self, raw_id: str) -> Optional[str]`:
    - Formats `DETAIL_URL` with `job_id=raw_id`.
    - Queries `self.session.get(url, params=self.BASE_PARAMS, timeout=self.TIMEOUT)`.
    - Catches `requests.exceptions.RequestException` and logs a warning with graceful fallback.
    - Decodes JSON payload and checks nested paths:
      - `data.get("jobDetail")`
      - `data.get("description")`
      - `data.get("content")`
      - `(data.get("job") or {}).get("content")`
      - `(data.get("jobDetail") or {}).get("job", {}).get("content")`
    - If payload is string or dictionary containing text, strip HTML tags via `re.sub(r"<[^>]+>", " ", text)`, unescape HTML entities via `html.unescape()`, normalize whitespace, and return cleaned text.
    - If JSON decoding fails, attempt HTML extraction from `response.text`.
    - Returns `None` if content is empty or extraction fails.

- **Record Parsing (`_parse_job`)**:
  - Update signature:
    ```python
    def _parse_job(
        self,
        item: Dict[str, Any],
        known_ids: Optional[set[str]] = None,
    ) -> Optional[RawJob]:
    ```
  - Construct fallback description from `teaser` and `bullet_points`:
    ```python
    fallback_desc = "\n\n".join(desc_parts) if desc_parts else None
    ```
  - Apply detail fetch decision matrix:
    ```python
    if known_ids and job_id in known_ids:
        description = fallback_desc
    elif self.fetch_details:
        time.sleep(self.REQUEST_DELAY)
        detail_desc = self._fetch_detail_description(raw_id)
        description = detail_desc if detail_desc else fallback_desc
    else:
        description = fallback_desc
    ```
  - Pass final `description` to `parse_salary(salary_str, description)`.

- **Batch Ingestion Loop (`scrape`)**:
  - Pass `known_ids` into `_parse_job(item, known_ids=known_ids)` at line 168.

### 2. Unit Test Suite (`tests/test_scrapers.py`)

- **Preserve Existing Tests**:
  - Ensure existing tests in `TestJobsDBScraper` continue to execute swiftly (e.g. patching `time.sleep` where necessary).
- **Add Targeted Unit Tests in `TestJobsDBScraper`**:
  1. `test_jobsdb_skips_detail_fetch_for_known_ids`:
     - Calls `scraper.scrape(known_ids={"jobsdb_78901234"})`.
     - Asserts no detail GET request is made for the known job ID.
     - Asserts fallback teaser/bullet description is retained.
  2. `test_jobsdb_detail_fetch_success_for_unseen_job`:
     - Calls `scraper.scrape(known_ids=set())`.
     - Mocks search response for `SEARCH_URL` and detail response (`{"jobDetail": "<p>Build microservices with FastAPI and Postgres.</p>"}`) for `DETAIL_URL`.
     - Patches `time.sleep` and asserts `time.sleep` is called with `self.scraper.REQUEST_DELAY`.
     - Asserts resulting `job.description` contains the cleaned detail text.
  3. `test_jobsdb_detail_fetch_failure_falls_back_to_teaser`:
     - Mocks `DETAIL_URL` request to raise `requests.exceptions.RequestException("Network timeout")`.
     - Patches `time.sleep`.
     - Asserts scraper completes without error and returns `RawJob` with teaser/bullet fallback description.
  4. `test_jobsdb_fetch_details_disabled`:
     - Instantiates `JobsDBScraper(keywords=["python developer"], fetch_details=False)`.
     - Calls `scraper.scrape()`.
     - Asserts no detail requests are made and `time.sleep` is not invoked for detail fetches.

### 3. Task Ledger Tracking (`docs/contexts/task-ledger.md`)
- Record Task 5.3 completion under Phase 5.

---

## Verification Plan

1. **Python Hermetic Test Suite**:
   - Run `uv run python -m unittest discover tests`.
   - Verify all 203 unit tests pass (199 existing + 4 new scraper tests).
   - Ensure zero live network requests occur and execution is fast (< 20s).

2. **Next.js Web Lint & Production Build**:
   - Run `cd web; npm run lint ; npm run build`.
   - Verify 0 ESLint errors/warnings and successful compilation.

3. **antislop Copywriting Audit**:
   - Verify zero em-dashes across all modified files (`src/scrapers/jobsdb.py`, `tests/test_scrapers.py`, `docs/contexts/task-ledger.md`).
