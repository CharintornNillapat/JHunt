# Plan: Task 7.2: JobsDB Detail Fetch Circuit Breaker and Per-Run Dedupe

**Date:** 2026-10-15
**Task ID:** 7.2
**Target paths (exhaustive):** `src/scrapers/jobsdb.py`, `tests/test_scrapers.py`, `docs/contexts/task-ledger.md`
**Reference:** CI run 38710734201, Task 5.3 (detail fetch origin), `AGENTS.md` (Invariants: Tests, Security, Job data)
**Skills:** `antislop`, `antislop-copywriting` (R-02: zero em dashes)

---

## Goal
Stop a dead JobsDB detail endpoint from eating the CI budget. Each `scrape()` run trips a breaker after 3 consecutive detail failures, and a job ID already handled earlier in the same run is never fetched again.

---

## Engineering & antislop Protocol Compliance
- **R-02:** zero em dashes (U+2014) in every line this task adds, including code comments, log strings, test names and the ledger line.
- **Fail open:** a tripped breaker never raises. Every job is still returned, with the listing teaser and bullet points as its description, exactly like the existing failure path at `jobsdb.py:166`.
- **Job IDs:** keep the `jobsdb_{id}` prefix rule (`jobsdb.py:131`). The dedupe key must be the same normalized ID that `_parse_job` produces.
- **Hermetic tests:** `requests.Session.get` and `time.sleep` are patched in every new test, as in the existing JobsDB tests. No `.env`, no storage, no clients.
- **Security:** log lines may contain the numeric job ID, nothing else from the request. The detail URL has no secrets, but do not log the session headers.
- **No new dependency, no new file, no workflow edit.**

---

## Current Behavior (Evidence)

1. **One detail request per unseen job, each preceded by a 1 s sleep.** `jobsdb.py:163-166`: if `fetch_details` is set and the job is not in `known_ids`, the code sleeps `REQUEST_DELAY` (1.0, `jobsdb.py:43`) and then calls `_fetch_detail_description`, which requests `DETAIL_URL` (`jobsdb.py:30`).
2. **No memory of failures.** `_fetch_detail_description` (`jobsdb.py:70-119`) returns `None` on any `RequestException`, including the HTTP 404 seen in run 38710734201. Nothing records that the previous call failed, so a dead endpoint costs `unseen_jobs x (1 s sleep + request)`.
3. **Dedupe runs after the detail fetch, not before.** In `scrape()` (`jobsdb.py:236-241`), `_parse_job(item, ...)` (which fetches the detail page) runs first. Only after that does `job.id in seen_ids` throw the duplicate away. The same job listed under several keywords is fetched once per keyword. This explains the CI log: 566 detail requests for 356 unique IDs. No duplicate is emitted today (the `seen_ids` check works), but its detail fetch and sleep are wasted.
4. **Retries make each failure slower for 429/5xx.** The session retries `429, 500, 502, 503, 504` up to 3 times with backoff (`base.py:45-51`). A 404 is not retried, so in this incident each failure cost about 1 s. A 5xx outage would cost several seconds per job, so the breaker matters even more there.
5. **Caller.** `main.py:114` calls `scraper.scrape(keywords=..., limit=..., known_ids=...)` once per pipeline run on a single `JobsDBScraper` instance (`src/scrapers/__init__.py:20`). The `scrape()` signature does not change.

---

## Proposed Changes

### 1. `src/scrapers/jobsdb.py`

**a. Class constant** next to `REQUEST_DELAY` (`jobsdb.py:43`):
```python
DETAIL_FAILURE_LIMIT = 3  # consecutive detail failures before the per-run breaker trips
```

**b. Breaker state.** Set it in `__init__`, so `_parse_job` works when tests call it directly, and reset it at the top of `scrape()`:
```python
self._detail_failures = 0
self._detail_breaker_open = False
```
Both attributes live on the instance, and `scrape()` resets them on every call. That makes the breaker per run: the next CI run tries the endpoint again.

**c. ID normalization helper.** This is the single source for the dedupe key. Replace the inline expression at `jobsdb.py:127-131` with it:
```python
@staticmethod
def _normalize_id(item: Dict[str, Any]) -> Optional[str]:
    raw_id = str(item.get("id") or "").strip()
    if not raw_id:
        return None
    return raw_id if raw_id.startswith("jobsdb_") else f"jobsdb_{raw_id}"
```
`_parse_job` still needs `raw_id` for `DETAIL_URL` and `JOB_URL`. Keep `raw_id = str(item.get("id") or "").strip()` there and derive `job_id` from the helper. URL output must stay byte-identical to the current code.

**d. Detail branch in `_parse_job`.** Replace `jobsdb.py:163-166`:
```python
elif self.fetch_details and not self._detail_breaker_open:
    time.sleep(self.REQUEST_DELAY)
    detail_desc = self._fetch_detail_description(raw_id)
    if detail_desc:
        self._detail_failures = 0
    else:
        self._detail_failures += 1
        if self._detail_failures >= self.DETAIL_FAILURE_LIMIT:
            self._detail_breaker_open = True
            logger.warning(
                f"[JobsDB] Detail fetch failed {self._detail_failures} times in a row; "
                "using listing teasers for the rest of this run."
            )
    description = detail_desc or fallback_desc
```
- When the breaker is open, the code falls through to the existing `else: description = fallback_desc` branch. There is no sleep and no request.
- **Failure definition:** any `None` from `_fetch_detail_description`. That covers HTTP errors (404, or 5xx after retries), network errors, and a 200 response with no extractable content. The last case is counted on purpose: a changed response shape would burn the budget the same way a 404 does.
- The warning is logged exactly once per run, when the breaker trips.

**e. Dedupe before parsing in `scrape()`.** Replace `jobsdb.py:236-241`:
```python
job_id = self._normalize_id(item)
if not job_id or job_id in seen_ids:
    continue

job = self._parse_job(item, known_ids=known_ids)
if not job:
    continue

seen_ids.add(job.id)
jobs.append(job)
keyword_count += 1
```
- A job whose detail fetch failed under keyword 1 is still added to `seen_ids` (it is returned with the teaser), so keyword 2 skips it. That covers "already seen or failed earlier".
- Items that `_parse_job` rejects (missing title or company, `jobsdb.py:147-148`) are rejected before any detail request. Leaving them out of `seen_ids` costs nothing.
- `keyword_count` and the `limit` semantics are unchanged: duplicates never counted toward the limit, and they still don't.

**f. Docstrings.** Update the `scrape()` docstring in one line: "Dedupes by job ID before detail fetch; detail fetch stops for the run after DETAIL_FAILURE_LIMIT consecutive failures." No em dashes.

### 2. `tests/test_scrapers.py`
Add the three tests below to `class TestJobsDBScraper`, using the existing decorator style: `@patch("time.sleep")` outermost, then `@patch("requests.Session.get")`. Shared shape for the mocks:
- A search response: a `MagicMock` with `.json.return_value = {"totalCount": N, "data": [...]}` and N ≤ 100, so there is a single page and no page sleep.
- A detail failure: a `MagicMock` whose `.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error: Not Found")`. This mirrors the CI incident.
- A detail success: `.json.return_value = {"jobDetail": "<p>Detail body for {id}</p>"}`.
- Dispatch on `"/job/" in url` (the same pattern as `test_jobsdb_detail_fetch_success_for_unseen_job`), and record the detail URLs that were called.
- Each listing item has `id`, `title`, `companyName`, and `teaser = f"Teaser {id}"`.

**(a) `test_jobsdb_detail_breaker_trips_after_consecutive_failures`**
- 5 unseen jobs (`known_ids=set()`), one keyword, every detail call returns 404.
- Assert: exactly **3** detail requests. `mock_sleep.call_count == 3`: one keyword and one page means no page sleeps, so every sleep is a detail sleep. 5 jobs returned. Every description contains `Teaser {id}`.
- Old code makes 5 detail requests and 5 sleeps, so this test fails there.

**(b) `test_jobsdb_detail_breaker_resets_on_success`**
- 8 unseen jobs. Detail outcomes by position: `fail, fail, OK, fail, fail, fail, -, -`.
- Assert: exactly **6** detail requests (jobs 7 and 8 are never fetched). Job 3's description contains `Detail body`. Jobs 1, 2, 4, 5 and 6 fall back to the teaser. 8 jobs returned.
- This test fails on old code, which makes 8 detail requests. It also fails on a breaker that does not reset: that one trips on the 3rd failure overall (request 4) and makes 4 requests. So it proves both the trip and the reset clause.

**(c) `test_jobsdb_duplicate_ids_across_keywords_not_refetched`**
- Two keywords, `["python", "data"]`. The search for `python` returns ids `501, 502`. The search for `data` returns `502, 503`. Every detail call succeeds.
- Assert: the detail URLs called are exactly the URLs for `501`, `502` and `503`, with `502` once. The jobs returned have ids `["jobsdb_501", "jobsdb_502", "jobsdb_503"]` with no duplicates. Sleep calls: 3 detail + 1 keyword-switch page sleep = **4**.
- Old code fetches `502` twice (4 detail requests, 5 sleeps), so this test fails there.

Also add a variant of (c) in which `502`'s detail call fails, and assert it is still fetched only once. This covers the "or failed" clause. It can be a second assertion block inside (c) or a fourth test, `test_jobsdb_failed_detail_id_not_refetched_under_later_keyword`. The Builder chooses, and the build report states the final count.

**Existing tests that must still pass unchanged:** `test_jobsdb_detail_fetch_failure_falls_back_to_teaser` (1 failure, no trip), `test_jobsdb_skips_detail_fetch_for_known_ids`, `test_jobsdb_fetch_details_disabled`, `test_jobsdb_malformed_record_handling` (`"id": ""` rejected by `_normalize_id`), `test_jobsdb_scrape_covers_all_keywords`, and the contract-parity and zero-network tests.

### 3. `docs/contexts/task-ledger.md`
Under `#### Phase 7: Build & Dependency Hygiene (P7)` (added by 7.1), append:
```
- [x] **Task 7.2: JobsDB Detail Fetch Circuit Breaker & Per-Run Dedupe** (Breaker trips after 3 consecutive detail failures per `scrape()` run and skips remaining detail requests and sleeps with teaser fallback; job IDs deduped before detail fetch across keywords; fixes CI run 38710734201 budget exhaustion).
```

---

## Out of scope
- **Why the endpoint returns 404.** `DETAIL_URL` (`jobsdb.py:30`) is probably the wrong path or is blocked for CI IPs. This task caps the damage, which is now about 3 requests and 3 s per run, but every JobsDB job still gets only the teaser. Finding the real SEEK detail endpoint is a follow-up task, and it needs a live probe that you approve.
- **Turning off `fetch_details` by default.** Not needed once the breaker exists.
- **Retry policy in `base.py`.** Shared by all scrapers. Do not touch.
- **Breakers for Blognone and JobThai.** They have no reported incident.

---

## Hermetic Test Plan
| Test | Depends on diff line | Old code | New code |
|---|---|---|---|
| (a) breaker trips | 1d: `not self._detail_breaker_open` and the trip logic | FAIL (5 requests and 5 sleeps) | PASS (3 and 3) |
| (b) reset on success | 1d: `self._detail_failures = 0` on success | FAIL (8 requests) | PASS (6) |
| (c) dedupe across keywords | 1e: `job_id in seen_ids` before `_parse_job` | FAIL (`502` fetched twice) | PASS (once) |

Mocks: `requests.Session.get` (search and detail), `time.sleep`. No network, no env, no storage.

**Order:** write the tests first, run `uv run python -m unittest tests.test_scrapers -v`, and record that (a), (b) and (c) fail on the unmodified scraper. Then implement.

---

## Verification Plan (PowerShell, repo root)
1. Tests fail first: `uv run python -m unittest tests.test_scrapers -v`. The new tests FAIL and all existing tests pass.
2. After the change: `uv run python -m unittest tests.test_scrapers -v`. Everything passes.
3. Full suite: `uv run python -m unittest discover tests`. Expect **207 passed** (baseline 204 + 3), or 208 if the Builder adds the optional fourth test.
4. Scope: `git diff --stat` lists only `src/scrapers/jobsdb.py`, `tests/test_scrapers.py` and `docs/contexts/task-ledger.md` (plus the Builder's own stage report).
5. R-02: `Select-String -Path src\scrapers\jobsdb.py,tests\test_scrapers.py,docs\contexts\task-ledger.md -Pattern ([char]0x2014)` must not match any line this task added.
6. Web is not touched, so lint and build are not required.

## Not verified by this plan
- Live JobsDB behavior. No real detail request is made. The first real confirmation is the next CI run: its log should show at most 3 `Detail request failed` lines followed by one breaker warning, and the step should finish far under the 10-minute budget.
- Whether the detail endpoint can ever succeed (see Out of scope).
