# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Environment (environment.yml is the source of truth; there is no requirements.txt)
conda env create -f environment.yml
conda activate jhunt

# Full pipeline
python main.py

# Scraper only — MUST be run as a module; scrapers/jobsdb_api.py uses a relative
# import (`from .base_scraper import ...`) and fails when run as a plain script path.
python -m scrapers.jobsdb_api

# Telegram smoke test (sends two real messages to TELEGRAM_CHAT_ID — a normal
# alert and one full of HTML metacharacters, which is the escaping regression test)
python notifier.py

# Reset dedupe state
echo '{"version": 2, "seen": {}}' > data/seen_jobs.json
```

There is no test suite and no linter configured. The `if __name__ == "__main__"` blocks in
`notifier.py` and `scrapers/jobsdb_api.py` are the only ad-hoc verification entry points.

There is no browser anywhere in this project. Selenium, ChromeDriver and the `HEADLESS` flag were
removed — if you are reading older docs or commits that mention them, they are stale.

## Configuration

`.env` (gitignored, see `.env.example`) / GitHub Actions secrets:

| Variable | Notes |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Required — `TelegramNotifier.__init__` raises if either is missing |
| `SEARCH_KEYWORDS` | Comma-separated; each becomes one JobsDB API query |
| `TITLE_FILTER` | Comma-separated relevance keywords (English + Thai) |
| `GEMINI_ENABLED` | `1/true/yes/on` enables the semantic filter; anything else disables it |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Only read when enabled; model defaults to `gemini-2.5-flash` |

**Read env vars through the helpers in `main.py`, not `os.getenv` directly.** CI passes *unset*
secrets as an empty string, so `os.getenv("TITLE_FILTER", default)` returns `""` rather than the
default. For `TITLE_FILTER` that yields `[""]`, and since every string contains `""`, the relevance
filter would silently pass everything. `_csv_env()` and `_bool_env()` ([main.py:24-42](main.py#L24-L42))
treat empty as unset.

## Architecture

Linear pipeline in `main.py:main()`, eight ordered steps:

`run_scrapers()` → `filter_new_jobs` → `filter_relevant_jobs` → `filter_by_seniority`
→ `filter_by_location` → `filter_semantically` → `notify_jobs` → `state.save()`

Job dicts flow through unchanged. The contract is `BaseScraper.JOB_SCHEMA = {id, title, company, url}`
(validated by `_validate_job`), plus optional `location`, `salary`, `work_type`, `teaser`,
`bullet_points`, `listing_date` — all supplied by the same API response. `main.py` never knows which
scraper produced a job.

`_validate_job` checks **only the four schema keys**, deliberately. An earlier version used
`all(job.values())`, which inspected every value and so discarded any job with an empty `salary` —
about 75% of JobsDB ads. Do not reintroduce that.

### State is mutated during filtering, and always persisted

`StateManager.filter_new_jobs()` ([state_manager.py](state_manager.py)) marks jobs seen **in memory**
as it dedupes, before any relevance/seniority/location/semantic filter runs. Consequences:

- A job dropped by a later filter is still marked seen, so loosening a filter later will **not**
  resurface it. This is intended — it stops the same rejects being re-evaluated daily.
- `state.save()` runs in a `finally` block, so state persists on every exit path including the
  no-matches early `return` and an unhandled exception.
- A job whose Telegram send **fails** is passed to `state.unmark()` by `notify_jobs`, so the next
  run retries it rather than losing the alert permanently.
- Filter order matters: relevance and seniority read `job["title"]`, location reads
  `job.get("location", "")` and **keeps** jobs with an empty location.
- `_clean_url` runs inside `filter_new_jobs`. The API already returns canonical URLs, so it is now a
  guard rather than a necessity.

**State file is v2:** `{"version": 2, "seen": {"<job_id>": "YYYY-MM-DD"}}`. The date is when the ID
was first seen and drives 90-day TTL pruning (`STATE_TTL_DAYS`) so the file stays bounded. `_load()`
still accepts the v1 `{"seen_ids": [...]}` shape and stamps those IDs with today's date. `save()` is
atomic — temp file in the same directory, `fsync`, then `os.replace` — because a truncated state file
would otherwise be cached by CI and restored forever.

Seniority/location term lists are module-level constants (`EXCLUDE_SENIORITY`, `INCLUDE_LOCATIONS`)
with Thai and English entries; relevance keywords come from env instead. All matching is lowercase
substring.

### Scraper layer

`BaseScraper` is a pure ABC — constructing a scraper opens no browser and acquires nothing needing
cleanup. Subclasses are plain HTTP clients.

`JobsDBAPIScraper` ([scrapers/jobsdb_api.py](scrapers/jobsdb_api.py)) calls SEEK's public JSON search
endpoint (JobsDB runs on SEEK's platform):

```
GET https://th.jobsdb.com/api/jobsearch/v5/search
    ?siteKey=TH-Main&sourcesystem=houston&locale=en-TH&sortmode=ListedDate
    &keywords=<kw>&page=<n>&pageSize=100&dateRange=3
```

Unauthenticated; needs only a browser `User-Agent`. `sourcesystem` is required. `locale=en-TH` keeps
location and work-type labels in English so the English terms in `INCLUDE_LOCATIONS` and
`EXCLUDE_SENIORITY` match. `dateRange=3` looks back further than the daily cron so a skipped run
leaves no gap.

**One request per keyword page returns everything** — `locations`, `salaryLabel`, `workTypes`,
`workArrangements`, `teaser`, `bulletPoints`. There is no detail-page fetch; the old Selenium version
navigated to each job individually, which was the entire runtime cost. A full two-keyword run is
now ~4s.

Pagination stops at `MAX_PAGES = 5` or when `page * pageSize >= totalCount`. An in-run `seen_ids` set
dedupes across keywords.

**This is an internal endpoint with no compatibility guarantee.** If it changes, the failure mode is
zero jobs, so `scrape()` logs a loud warning naming the endpoint when it returns nothing. Recovery
means editing the params in one file. The old `chalice-search/v4` endpoint is dead (404) — don't
reach for it.

### Adding a scraper

Subclass `BaseScraper`, implement `scrape() -> list[dict]`, then instantiate and `all_jobs.extend(...)`
inside `run_scrapers()` ([main.py:57](main.py#L57)). Nothing downstream changes.

### Notifier

`parse_mode` is **`"HTML"`**, and every dynamic field goes through `html.escape()` (the URL with
`quote=True`). The rendered message — emoji, line order, blank line after the header, `View Job` link
— is identical to the previous Markdown version. The switch exists because legacy Markdown has no
defined escape mechanism: a title like `Developer (C++ & Python)` returned HTTP 400 and the alert
vanished silently. If you edit the template, keep the escaping.

`send()` self-throttles to `MIN_SEND_INTERVAL` (1s) between messages against Telegram's ~20/min
per-chat limit, retries once on HTTP 429 honouring `parameters.retry_after` (capped at
`MAX_RETRY_AFTER`), and logs Telegram's own `description` on failure. Throttling lives in the
notifier, not the caller's loop, so every caller gets it.

### Gemini semantic filter

`gemini_filter.filter_semantically(jobs, config)` is an optional pass that drops non-engineering
roles the substring filters keep (a sales ad mentioning Python) and roles too senior for the target.
It runs **after** the cheap filters so it only scores the survivors.

Plain REST via `requests` — no SDK, no new dependency. Batches 40 jobs per request with a 7s gap;
free tier is ~10 req/min, so a normal run costs one or two requests. Uses structured output
(`responseMimeType: application/json` plus a `responseSchema`) rather than parsing prose.

**Fail-open is the contract, not a nicety.** Disabled, missing key, HTTP error, quota exhaustion,
unparseable body, a verdict for an index that doesn't exist, a missing score — every one of these
keeps the affected jobs. The function never raises. A wrong verdict costs one alert; a crash costs
all of them. Keep it that way when editing.

Note that semantically-dropped jobs remain marked seen, consistent with the other filters.

## CI

`.github/workflows/scraper_cron.yml` — daily at 02:00 UTC (09:00 Bangkok), plus `workflow_dispatch`.
Miniconda from `environment.yml`. No Chrome install step — there is no browser.

The scraper step needs `shell: bash -el {0}` for conda activation.

State persistence uses **split** `actions/cache/restore@v4` + `actions/cache/save@v4` with a rotating
key `seen-jobs-state-v2-${{ github.run_id }}` and the restore prefix `seen-jobs-state-v2-`. GitHub
cache entries are immutable, so the previous fixed key `seen-jobs-state` froze dedupe state after the
first successful run. Each run now writes a fresh entry and restores the newest. The combined
`actions/cache@v4` action will not save under an existing key — keep them split.
