# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Environment (environment.yml is the source of truth; requirements.txt is a UTF-16 pip freeze dump, unused by CI)
conda env create -f environment.yml
conda activate jhunt

# Full pipeline
python main.py

# Scraper only — MUST be run as a module; scrapers/jobsdb_scraper.py uses a relative
# import (`from .base_scraper import ...`) and fails when run as a plain script path.
python -m scrapers.jobsdb_scraper

# Telegram smoke test (sends a real message to TELEGRAM_CHAT_ID)
python notifier.py

# Reset dedupe state
echo '{"seen_ids": []}' > data/seen_jobs.json
```

Watch the browser locally: set `HEADLESS=false` (PowerShell: `$env:HEADLESS="false"`).

There is no test suite and no linter configured. The `if __name__ == "__main__"` blocks in
`notifier.py` and `scrapers/jobsdb_scraper.py` are the only ad-hoc verification entry points.

## Configuration

`.env` (gitignored) / GitHub Actions secrets:

| Variable | Notes |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Required — `TelegramNotifier.__init__` raises if either is missing |
| `SEARCH_KEYWORDS` | Comma-separated; each becomes one JobsDB URL slug |
| `TITLE_FILTER` | Comma-separated relevance keywords (English + Thai). Not in the README table and **not passed in `scraper_cron.yml`**, so CI always uses the hardcoded default in `get_config()` |
| `HEADLESS` | `"true"`/`"false"` string compare |

## Architecture

Linear pipeline in `main.py:main()`, seven ordered steps:

`run_scrapers()` → `filter_new_jobs` → `filter_relevant_jobs` → `filter_by_seniority` → `filter_by_location` → `notify_jobs` → `state.save()`

Job dicts flow through unchanged. The contract is `BaseScraper.JOB_SCHEMA = {id, title, company, url}`
(validated by `_validate_job`, which also rejects falsy values), plus optional `location`, `salary`,
`work_type` added from the detail page. `main.py` never knows which scraper produced a job.

### State is mutated during filtering, not after

`StateManager.filter_new_jobs()` ([state_manager.py:50](state_manager.py#L50)) marks jobs seen **in memory**
as it dedupes — before any relevance/seniority/location filter runs. Consequences to keep in mind when
changing the pipeline:

- A job dropped by a later filter is still marked seen, so loosening a filter later will **not** resurface it.
- `state.save()` is only reached at the end of `main()`. The early `return` when `local_jobs` is empty
  ([main.py:100-102](main.py#L100-L102)) means a run where everything gets filtered out persists nothing.
- Filter order matters: relevance and seniority read `job["title"]`, location reads `job.get("location", "")`
  and **keeps** jobs with an empty location (detail-page fetch failures get the benefit of the doubt).
- `_clean_url` strips query params and fragments, and runs inside `filter_new_jobs` — not in the scraper.

Seniority/location term lists are module-level constants (`EXCLUDE_SENIORITY`, `INCLUDE_LOCATIONS`) with
Thai and English entries; relevance keywords come from env instead. All matching is lowercase substring.

### Scraper layer

`BaseScraper.__init__` launches Chrome immediately — instantiating a scraper opens a browser. Selenium 4
resolves ChromeDriver itself (`Service()` with no path).

`JobsDBScraper.scrape()` does a two-phase pass per keyword, and the ordering is load-bearing: visiting a
detail page navigates the shared driver away from the results page, so **all** card data must be harvested
into `new_cards_data` before any `_get_job_details()` call. An in-run `seen_ids` set dedupes across keywords
so overlapping searches don't refetch detail pages.

`scrape()` calls `self.close()` before returning — the driver is dead afterwards and the instance is single-use.

`_parse_cards()` ([scrapers/jobsdb_scraper.py:90](scrapers/jobsdb_scraper.py#L90)) is dead code, superseded by
the inline logic in `scrape()`. Don't extend it; if you touch it, delete it.

**`SELECTORS` is the main breakage point.** Every JobsDB CSS selector lives in one dict at the top of
`JobsDBScraper`. Cards use `data-testid`, detail-page fields use `data-automation`. When the pipeline
returns zero jobs, check these first — the failure mode is a silent `TimeoutException` in `_wait_for_cards()`
that logs and moves on, not a crash.

### Adding a scraper

Subclass `BaseScraper`, implement `scrape() -> list[dict]`, then instantiate and `all_jobs.extend(...)`
inside `run_scrapers()` ([main.py:31](main.py#L31)). Nothing downstream changes.

## CI

`.github/workflows/scraper_cron.yml` — daily at 02:00 UTC (09:00 Bangkok), plus `workflow_dispatch`.
Miniconda from `environment.yml`, then Chrome installed via apt.

The scraper step needs `shell: bash -el {0}` for conda activation. State persistence uses `actions/cache`
with the **fixed key `seen-jobs-state`** — GitHub Actions cache entries are immutable, so once that key
exists the save step will not overwrite it. Treat CI dedupe state as effectively frozen at the first
successful run unless the key is versioned or the cache is manually evicted.
