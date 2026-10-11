# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and AI assistants when working with code in this repository.

---

## Project Mission & Evolution

`JHunt` is a **Job Market Intelligence & Portfolio Ideation Platform** focused on the Thailand tech ecosystem. It has evolved from a keyword scraper into an end-to-end intelligence engine that:
1. Scrapes job listings from Thailand job portals (e.g. JobsDB / SEEK API).
2. Filters and deduplicates listings for junior and mid-level software engineering roles.
3. Dispatches immediate alerts via Telegram (HTML-escaped).
4. Persists normalized job and skill records into cloud Turso (LibSQL over HTTPS) as the single source of truth, with local SQLite fallback (`data/market.db`).
5. Extracts structured tech stack attributes (languages, frameworks, databases, cloud, tools) via Google Gemini API (Free Tier) and Pydantic schemas.
6. Computes skill frequency distributions and tech stack co-occurrence matrices.
7. Automatically ideates and exports enterprise-grade portfolio project blueprints with YAML frontmatter to:
   `C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project`

---

## Operational Guardrails & Coding Standards

1. **Cost Policy**: 100% Free Tier (Python stdlib, SQLite, Turso Starter/Free, Google GenAI Free Tier / Gemini 2.0 Flash / 1.5 Flash, Git). Never introduce paid external APIs or billable cloud dependencies.
2. **Pathing Policy**: Always use Python's `pathlib.Path(r"...")` for all Windows filesystem operations. Never use unescaped raw string literals with backslashes.
3. **Single Developer Constitution**: Maintain all project guidelines, architectural rules, and coding standards exclusively in `CLAUDE.md`. **Do NOT create `GEMINI.md`**.
4. **Task Tracking Ledger**: Track phased execution and task states in `docs/contexts/task-ledger.md`.
5. **Modularity**: Code is structured into dedicated modular packages under `src/`:
   - `src/scraper`: Data collection and site scraper implementations.
   - `src/storage`: Unified storage abstraction (`get_storage()`), Turso LibSQL client (`turso_client.py`), and local SQLite database (`data/market.db`).
   - `src/extractor`: Text sanitizer, Gemini LLM client, and Pydantic schemas.
   - `src/analyzer`: Tech stack clustering, frequency, and co-occurrence matrices.
   - `src/generator`: Portfolio ideation engine and Jinja2 Markdown blueprint exporter.
   - `src/notifier`: Telegram dispatcher with throttling and HTML escaping.

---

## Commands

```bash
# Environment (`requirements.txt` via `uv` or `pip`, or `environment.yml` via Conda)
uv venv
uv pip install -r requirements.txt
# or standard pip
pip install -r requirements.txt

# Full end-to-end pipeline (Scrape -> Extract -> Save -> Notify -> Analyze -> Ideate -> Export)
python main.py run --all

# Legacy Telegram alert mode only
python main.py alert

# Run analytics and project spec generation on existing DB records without scraping
python main.py analyze

# Scraper only — MUST be run as a module; scrapers/jobsdb_api.py uses a relative
# import (`from .base_scraper import ...`) and fails when run as a plain script path.
python -m scrapers.jobsdb_api

# Telegram smoke test (sends two real messages to TELEGRAM_CHAT_ID — a normal
# alert and one full of HTML metacharacters, which is the escaping regression test)
python notifier.py

# Reset dedupe state
echo '{"version": 2, "seen": {}}' > data/seen_jobs.json
```

---

## Configuration

`.env` (gitignored, see `.env.example`) / GitHub Actions secrets:

| Variable | Notes |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Required for alerts — `TelegramNotifier.__init__` raises if missing |
| `SEARCH_KEYWORDS` | Comma-separated; each becomes one JobsDB API query |
| `TITLE_FILTER` | Comma-separated relevance keywords (English + Thai) |
| `GEMINI_ENABLED` | `1/true/yes/on` enables the semantic filter; anything else disables it |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Read when enabled; defaults to `gemini-3.8-flash` |
| `EXPORT_DIR` | Optional override for blueprint export directory; defaults to `C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project` |

**Read env vars through the helpers in `main.py`, not `os.getenv` directly.** CI passes *unset*
secrets as an empty string, so `os.getenv("TITLE_FILTER", default)` returns `""` rather than the
default. For `TITLE_FILTER` that yields `[""]`, and since every string contains `""`, the relevance
filter would silently pass everything. `_csv_env()` and `_bool_env()` ([main.py:24-42](main.py#L24-L42))
treat empty as unset.

---

## Architecture & Data Flow

### 1. Ingestion & Filtering Pipeline
Linear pipeline in `main.py`:
`run_scrapers()` → `filter_new_jobs` → `filter_relevant_jobs` → `filter_by_seniority`
→ `filter_by_location` → `filter_semantically` → `notify_jobs` → `state.save()`

Job dicts flow through unchanged. The contract is `BaseScraper.JOB_SCHEMA = {id, title, company, url}`
(validated by `_validate_job`), plus optional `location`, `salary`, `work_type`, `teaser`,
`bullet_points`, `listing_date` — all supplied by the same API response. `main.py` never knows which
scraper produced a job.

`_validate_job` checks **only the four schema keys**, deliberately. An earlier version used
`all(job.values())`, which inspected every value and so discarded any job with an empty `salary` —
about 75% of JobsDB ads. Do not reintroduce that.

### 2. State Management & Storage Persistence
`StateManager.filter_new_jobs()` ([state_manager.py](state_manager.py)) marks jobs seen **in memory**
as it dedupes, before any relevance/seniority/location/semantic filter runs.
- A job dropped by a later filter is still marked seen, so loosening a filter later will **not**
  resurface it. This is intended — it stops the same rejects being re-evaluated daily.
- `state.save()` runs in a `finally` block, so state persists on every exit path including the
  no-matches early `return` and an unhandled exception.
- A job whose Telegram send **fails** is passed to `state.unmark()` by `notify_jobs`, so the next
  run retries it rather than losing the alert permanently.
- Unified storage layer (`get_storage()`):
  - In production / CI (when `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are set), writes and reads execute directly against **Turso (LibSQL over HTTPS)** as the single source of truth.
  - If Turso credentials are missing or `force_sqlite=True`, seamlessly falls back to local SQLite (`data/market.db`).
  - Tables:
    - `jobs`: Stores raw job records, titles, companies, URLs, timestamps.
    - `skills_extracted`: Normalized canonical skills, frameworks, databases, cloud, tools, and experience level.
    - `generated_projects`: Tracks generated portfolio blueprints and export file paths.

### 3. Scraper Layer
`BaseScraper` is a pure ABC — constructing a scraper opens no browser and acquires nothing needing
cleanup. Subclasses are plain HTTP clients.

`JobsDBAPIScraper` ([scrapers/jobsdb_api.py](scrapers/jobsdb_api.py)) calls SEEK's public JSON search endpoint:
```
GET https://th.jobsdb.com/api/jobsearch/v5/search
    ?siteKey=TH-Main&sourcesystem=houston&locale=en-TH&sortmode=ListedDate
    &keywords=<kw>&page=<n>&pageSize=100&dateRange=3
```
Unauthenticated; needs only a browser `User-Agent`. `sourcesystem` is required. `locale=en-TH` keeps
location and work-type labels in English so the English terms in `INCLUDE_LOCATIONS` and
`EXCLUDE_SENIORITY` match. `dateRange=3` looks back further than the daily cron so a skipped run
leaves no gap.

### 4. Notifier Layer
`parse_mode` is **`"HTML"`**, and every dynamic field goes through `html.escape()` (the URL with
`quote=True`). Throttled to 1s between sends to stay comfortably under Telegram rate limits.

### 5. Structured LLM Extraction Layer (`src/extractor`)
- Strips boilerplate from JDs to minimize prompt tokens.
- Queries Gemini API using Pydantic structured output models (`ExtractedJob`).
- Exponential backoff and rate limit handling for Free Tier quotas.
- Fail-open contract: failures never crash the pipeline.

### 6. Market Clustering & Ideation Layer (`src/analyzer`, `src/generator`)
- Analyzes skill co-occurrence (e.g. Go + PostgreSQL + Redis + Docker).
- Synthesizes portfolio specs reflecting real Thailand market demands (`ProjectIdeaSpec`).
- Renders Jinja2 templates into Markdown with YAML frontmatter.
- Exports to `C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project`.

---

## CI & Automated Deployment

`.github/workflows/scraper_cron.yml` — runs daily at 01:00 UTC (08:00 Bangkok), plus `workflow_dispatch`.
`uv` (`astral-sh/setup-uv@v5`) with Python 3.11 and `requirements.txt`. Deduplication state persistence uses split `actions/cache/restore@v4` + `actions/cache/save@v4`
with rotating key `seen-jobs-state-v2-${{ github.run_id }}`. Production data ingestion writes directly to cloud Turso, eliminating runner SQLite cache.
