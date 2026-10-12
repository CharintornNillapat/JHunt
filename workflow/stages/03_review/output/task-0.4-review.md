# Review: Task 0.4 — Restore Scraper Keyword Coverage & Detail Fetch Optimization

Task: 0.4
Verdict: PASS
Tests: 154 passed (run by reviewer)

Blocking:
None

Non-blocking:
- `main.py:94` — `run_scrapers` accepts `storage: Optional[Any] = None` and `run_full_pipeline` passes `active_storage`, but `storage` is currently unused in the body of `run_scrapers`. If `storage` later exposes a method like `get_known_job_ids()`, it can be queried alongside `state._seen.keys()`.
- `src/scrapers/blognone.py:259` & `src/scrapers/jobthai.py:277` — `_parse_job` is called before the outer `job.id in seen_ids` check. Passing `(known_ids or set()) | seen_ids` into `_parse_job` would also skip detail fetching and sleep delays for jobs encountered across multiple keywords in the same scrape session.

Rule candidates:
None
