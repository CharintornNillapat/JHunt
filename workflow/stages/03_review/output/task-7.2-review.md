# Review: Task 7.2: JobsDB Detail Fetch Circuit Breaker and Per-Run Dedupe

- **Task ID:** 7.2
- **Date:** 2026-10-15
- **Reviewer:** Claude Code (REVIEWER session)
- **Target files:** `src/scrapers/jobsdb.py`, `tests/test_scrapers.py`, `docs/contexts/task-ledger.md`
- **Status:** APPROVED

```
Task: 7.2
Verdict: PASS
Tests: 208 passed (run by reviewer)
Blocking: none
```

---

## 1. Executive Summary
The Builder added a per-run circuit breaker to the JobsDB detail fetch, and moved the dedupe-by-job-ID check ahead of `_parse_job` so duplicates never trigger a detail request. Both causes of the CI budget exhaustion in run 38710734201 are removed:
- unbounded failed detail requests, each preceded by a 1 s sleep
- repeat fetches of IDs already seen under earlier keywords

The implementation follows the spec line for line. The Builder also added the optional fourth test the spec allowed.

---

## 2. Deliverables & Invariants Verification

| Spec item | Evidence | Result |
|---|---|---|
| 1a. `DETAIL_FAILURE_LIMIT = 3` | `jobsdb.py:44` | PASS |
| 1b. State in `__init__`, reset per `scrape()` | `jobsdb.py:51-52` and `jobsdb.py:228-229` | PASS |
| 1c. `_normalize_id` helper, used by `_parse_job` | `jobsdb.py:124-129`, `jobsdb.py:138`. `raw_id` is kept for URLs, so `url` output is unchanged. | PASS |
| 1d. Breaker in the detail branch | `jobsdb.py:172-185`. When the breaker is open, the code falls through to `else: fallback_desc` with no sleep and no request. A success resets the counter. The warning is logged once, at the trip. | PASS |
| 1e. Dedupe before `_parse_job` | `jobsdb.py:258-260`. The `keyword_count` and limit semantics are unchanged. | PASS |
| 1f. Docstring | `jobsdb.py:220`, no em dash | PASS |
| 2. Tests | Spec tests (a), (b) and (c), plus the optional `test_jobsdb_failed_detail_id_not_refetched_under_later_keyword` | PASS |
| 3. Ledger | `task-ledger.md:145`, under Phase 7 | PASS |

**Scope (`git diff --stat`):** `docs/contexts/task-ledger.md`, `src/scrapers/jobsdb.py`, `tests/test_scrapers.py`, plus the Builder's own `build-report.md`. Nothing unplanned. (Task 7.1 is already committed as `ec7348a`.)

**Root cause:** both causes are fixed at the source, not just the symptom.
- The failure loop is bounded per run.
- Dedupe now runs before the expensive call, not after it.

The endpoint's 404 itself is out of scope, as the spec says.

**Tests prove the change (reviewer ran them):**
- **Against the old scraper:** I extracted `HEAD` into the scratchpad with `git archive`, dropped in the new `tests/test_scrapers.py`, and ran the suite. **All 4 new tests FAIL; the other 26 pass.**
- **Mutation, missing reset:** I removed the success-path reset (`self._detail_failures = 0` at `jobsdb.py:176`) in a scratch copy. Only `test_jobsdb_detail_breaker_resets_on_success` fails. So test (b) really guards the reset clause, not just the trip.
- **What each test depends on:**
  - (a) depends on `jobsdb.py:172` (`not self._detail_breaker_open`) and the trip at `:179-180`.
  - (b) depends on `:176`.
  - (c) and the fourth test depend on `:258-260`.

**Invariants touched:**
- **Job IDs:** the `jobsdb_{id}` prefix is preserved; the helper produces the same key as before. Holds.
- **Fail open:** a tripped breaker returns every job with the teaser and bullet-point description, and never raises. Holds.
- **Hermetic tests:** every new test patches `requests.Session.get` and `time.sleep`. No env, storage or clients. Holds.
- **Security:** the new log line has no URL or secrets, only the failure count. Holds.
- **Other invariants:** no SQL, LLM, Telegram, state or workflow changes, so they are not affected.

---

## 3. Verification & Quality Gates (run by reviewer)
- **Full suite:** `uv run python -m unittest discover tests`: **Ran 208 tests, OK** (baseline 204 + 4).
- **Test-first:** 4/4 new tests fail on the `HEAD` scraper (see above).
- **Mutation:** a breaker without the success reset is caught by test (b).
- **Web:** not touched, so lint and build are not required.
- **R-02:** 0 em dashes in the lines added to all three target files.

---

## 4. What Was NOT Verified
- Live JobsDB and SEEK behavior. No real detail request was made. The next CI run is the first real check: expect at most 3 `Detail request failed` lines, then one breaker warning, and a JobsDB step that finishes well under the 10-minute budget.
- Whether the detail endpoint can return content at all. Out of scope: follow-up task to find the real SEEK detail endpoint, which needs your approval for a live probe.

---

## 5. Conclusion
**APPROVED.** All gates passed.

Non-blocking:
- `src/scrapers/jobsdb.py:139`: `if not raw_id or not job_id:` repeats a check, because `_normalize_id` already returns `None` when `raw_id` is empty. `if not job_id:` is enough.
- `tests/test_scrapers.py`: test (b) does not assert `mock_sleep.call_count == 6`. Test (a) already covers sleeps stopping with the breaker, so this is optional.
- `_normalize_id` runs twice for each new item (in `scrape()` and in `_parse_job`). The cost is negligible, so no change is needed.

Rule candidates:
- AGENTS.md (Scrapers): "Dedupe by job ID before any per-job network call; any per-job remote call needs a per-run failure breaker."
