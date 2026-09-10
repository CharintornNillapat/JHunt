# JHunt 🎯

> An automated job scraper and Telegram alert system — built with Python, direct JSON APIs, and GitHub Actions.

JHunt monitors job boards on a daily schedule, filters duplicates across runs, and fires real-time Telegram alerts for every new listing found. No machine needs to be on.

---

## Features

- **Modular scraper architecture** — add new job sites by dropping a single file into `scrapers/`
- **Duplicate filtering** — persistent state via GitHub Actions Cache ensures you never see the same job twice
- **Telegram alerts** — clean, formatted notifications delivered instantly to your phone
- **Fully automated** — GitHub Actions cron job runs daily at 09:00 Bangkok time (02:00 UTC)
- **No browser required** — Selenium, ChromeDriver and all headless-browser dependencies have been
  removed. The scraper calls the JobsDB JSON API directly with `requests`, so a full run takes seconds
  instead of minutes and CI needs no Chrome install
- **Optional AI filtering** — Gemini 2.5 Flash can screen out non-engineering roles that keyword
  filters miss

---

## Project Structure

```
JHunt/
├── .github/
│   └── workflows/
│       └── scraper_cron.yml      # GitHub Actions automation
├── data/
│   └── seen_jobs.json            # Runtime state — gitignored
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py           # Abstract base class (pure ABC, no browser)
│   └── jobsdb_api.py             # JobsDB JSON API client
├── .env                          # Local secrets — never committed
├── .env.example                  # Documented template for .env
├── .gitignore
├── environment.yml               # Conda environment definition
├── gemini_filter.py              # Optional AI relevance pass
├── main.py                       # Orchestrator
├── notifier.py                   # Telegram notification module
└── state_manager.py              # Duplicate filter & state persistence
```

---

## Architecture

`main.py:main()` is a linear pipeline of eight ordered steps. Job dicts flow through unchanged;
each stage only narrows the list.

```
GitHub Actions (cron: 09:00 BKK)  ─→  Restore state cache  ─→  Setup Conda  ─→  python main.py
                                                                                     │
  1. Fetch          JobsDBAPIScraper.scrape()          JobsDB v5 JSON API via requests
  2. Deduplicate    StateManager.filter_new_jobs()     atomic v2 state store
  3. Relevance      StateManager.filter_relevant_jobs()   TITLE_FILTER substring match
  4. Seniority      StateManager.filter_by_seniority()    drop senior/lead/principal/manager
  5. Location       StateManager.filter_by_location()     Bangkok region + remote
  6. Semantic       filter_semantically()                 Gemini 2.5 Flash via REST (optional)
  7. Dispatch       TelegramNotifier.send_job_alert()     HTML mode, rate-limited
  8. Persist        StateManager.save()                   atomic write in a finally block
                                                                                     │
                                                          Save updated state cache  ←┘
```

| Step | What it does |
|------|--------------|
| **1. Fetch** | One `GET` per keyword against `th.jobsdb.com/api/jobsearch/v5/search`. Unauthenticated; needs only a browser `User-Agent`. Location, salary and work type all come back in the search response, so there is no per-job detail fetch. |
| **2. Deduplicate** | Drops job IDs already in `data/seen_jobs.json`, and marks the survivors seen **in memory**. Anything a later filter rejects therefore stays marked, so the same rejects are not re-evaluated tomorrow. |
| **3. Relevance** | Keeps a job when its title contains any `TITLE_FILTER` term. Lowercase **substring** matching, not regex — `data` matches `Data Engineer` and also `Database Admin`. |
| **4. Seniority** | Drops titles containing `senior`, `lead`, `principal`, `manager`, `head of`, `director` (`EXCLUDE_SENIORITY`). |
| **5. Location** | Keeps Bangkok-region and remote roles (`INCLUDE_LOCATIONS`, Thai + English). Jobs with an empty location are kept — benefit of the doubt. |
| **6. Semantic** | Optional Gemini pass over the survivors only. Skipped entirely unless `GEMINI_ENABLED` is set. Fail-open: any error keeps every job. |
| **7. Dispatch** | One Telegram message per job, `parse_mode: HTML` with every field escaped, self-throttled to 1s apart with a single 429 retry. |
| **8. Persist** | `state.save()` runs in a `finally` block, so state reaches disk on every exit path — including the no-matches early return and an unhandled exception. Writes to a temp file, `fsync`s, then `os.replace`s, so a killed run can never leave a truncated file for CI to cache. |

The `BaseScraper` abstract class enforces a consistent interface across all scrapers. It is a pure
ABC — constructing a scraper opens no browser and acquires nothing needing cleanup. Every scraper
must implement `scrape()` and return a list of job dicts with the schema `{id, title, company, url}`,
plus optional `location`, `salary`, `work_type`, `teaser`, `bullet_points`. This means `main.py` never
needs to know which scraper it's running.

---

## Getting Started

### Prerequisites

- [Anaconda](https://www.anaconda.com/) or Miniconda
- A Telegram Bot token (see setup below)

### 1. Clone the repository

```bash
git clone https://github.com/CharintornNillapat/JHunt.git
cd JHunt
```

### 2. Create and activate the Conda environment

`environment.yml` is the single source of truth for dependencies — Python 3.11 plus `requests` and
`python-dotenv`. There is no `requirements.txt`.

```bash
conda env create -f environment.yml
conda activate jhunt
```

To pick up dependency changes later, `conda env update -f environment.yml --prune`.

### 3. Configure environment variables

Copy the template and fill it in:

```bash
cp .env.example .env
```

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
SEARCH_KEYWORDS=python developer,data engineer
```

Values are read literally — no quotes, and no repeated variable name. `SEARCH_KEYWORDS=python
developer,data engineer` is a plain comma-separated string, **not**
`SEARCH_KEYWORDS=SEARCH_KEYWORDS=...` and not `"python developer","data engineer"`. Spaces inside a
term are fine; whitespace around the commas is stripped.

### 4. Initialize state file

```bash
mkdir -p data
echo '{"version": 2, "seen": {}}' > data/seen_jobs.json
```

### 5. Run locally

```bash
python main.py
```

### 6. Verify the pieces individually

**Scraper only** — prints the parsed job dicts and sends nothing. Must be run as a module: it uses a
relative import and fails when invoked as a plain file path.

```bash
python -m scrapers.jobsdb_api
```

**Telegram smoke test** — sends two *real* messages to `TELEGRAM_CHAT_ID`, so credentials must be set
first. The second message is deliberately loaded with HTML metacharacters
(`Developer (C++ & Python) <Urgent>`); under the old Markdown mode it returned HTTP 400 and vanished
silently, so it doubles as the escaping regression test.

```bash
python notifier.py
```

Both messages arriving intact means the notifier is configured correctly.

---

## Telegram Bot Setup

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token into your `.env`
4. Start a conversation with your bot, then visit:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
5. Copy the `chat.id` value into your `.env`

---

## GitHub Actions Deployment

### 1. Add repository secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `SEARCH_KEYWORDS` | Comma-separated keywords e.g. `python developer,data engineer` |
| `TITLE_FILTER` | Optional. Comma-separated title relevance keywords |
| `GEMINI_ENABLED`, `GEMINI_API_KEY` | Optional. Only needed to enable the AI filter |

An unset secret arrives as an empty string rather than being absent, so every optional variable falls
back to its documented default when the secret does not exist. `GEMINI_MODEL` is not forwarded by the
workflow — CI always uses the default model.

### 2. Push to main

```bash
git push origin main
```

The workflow runs automatically every day at 09:00 Bangkok time. To trigger manually: **Actions → JHunt Scraper → Run workflow**.

### State caching between runs

GitHub Actions cache entries are **immutable** — once a key exists it can never be overwritten. A
fixed cache key therefore freezes dedupe state after the first successful run, and every later run
re-notifies the same jobs. The workflow avoids this with a rotating key and a prefix restore:

```yaml
- uses: actions/cache/restore@v4        # step 2, before the run
  with:
    path: data/seen_jobs.json
    key: seen-jobs-state-v2-${{ github.run_id }}
    restore-keys: |
      seen-jobs-state-v2-

- uses: actions/cache/save@v4           # step 6, after the run
  if: always()
  with:
    path: data/seen_jobs.json
    key: seen-jobs-state-v2-${{ github.run_id }}
```

Each run saves under a key unique to that run, and `restore-keys` prefix-matches the most recent
entry on the next run. `restore` and `save` must stay **split**: the combined `actions/cache@v4`
action skips its post-run save when the key already exists, which reintroduces the original bug.
`if: always()` persists whatever state was reached even if the scraper failed part-way.

Bump the `v2` segment to deliberately discard all cached state and start fresh.

---

## Adding a New Job Site

1. Create `scrapers/yoursite_scraper.py` extending `BaseScraper`
2. Implement the `scrape()` method returning `list[dict]` matching the job schema
3. Import and call it inside `run_scrapers()` in `main.py`

```python
# scrapers/indeed_api.py
from .base_scraper import BaseScraper

class IndeedAPIScraper(BaseScraper):
    def __init__(self, keywords: list[str]):
        self.keywords = keywords

    def scrape(self) -> list[dict]:
        # your implementation
        ...
```

```python
# main.py — run_scrapers()
from scrapers.indeed_api import IndeedAPIScraper

indeed = IndeedAPIScraper(keywords=config["keywords"])
all_jobs.extend(indeed.scrape())
```

Nothing else in the pipeline changes.

---

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather. `TelegramNotifier` raises at startup if missing |
| `TELEGRAM_CHAT_ID` | Yes | — | Destination chat ID. Also raises at startup if missing |
| `SEARCH_KEYWORDS` | No | `python developer,data engineer` | Comma-separated search terms. Each becomes one JobsDB API query |
| `TITLE_FILTER` | No | 18 EN/TH keywords | Comma-separated title keywords. A job is kept if its title contains any of them |
| `GEMINI_ENABLED` | No | `false` | `1`/`true`/`yes`/`on` enables the semantic filter; anything else disables it |
| `GEMINI_API_KEY` | Only if enabled | — | Key from [Google AI Studio](https://aistudio.google.com/apikey). Without it the filter logs a warning and keeps every job |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Model used for filtering |

### Value formats

`SEARCH_KEYWORDS` and `TITLE_FILTER` are both plain comma-separated strings — no quoting, no
brackets, and no repetition of the variable name:

```bash
SEARCH_KEYWORDS=python developer,data engineer,machine learning
TITLE_FILTER=python,backend,data,วิศวกร
```

- Whitespace around commas is stripped; spaces **inside** a term are preserved and meaningful
  (`full stack` is one term).
- Empty terms are discarded. If a variable resolves to nothing usable — unset, blank, or just commas —
  the built-in default is used instead. This matters in CI, where an unset secret is passed as an
  empty string: without that fallback `TITLE_FILTER` would become `[""]`, and since every string
  contains `""`, the relevance filter would silently pass every job through.
- `TITLE_FILTER` matching is lowercase **substring**, not regex. Both English and Thai terms work.

See `.env.example` for a documented template.

### About the Gemini filter

The keyword filters can only match text, so a sales ad that mentions "Python" gets through. Enabling
`GEMINI_ENABLED` adds a pass that screens the surviving jobs for genuine junior engineering roles.

It calls the REST endpoint directly with `requests` — no SDK, no extra dependency:

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
     x-goog-api-key: $GEMINI_API_KEY
```

Jobs are batched 40 per request with a 7s gap, against a free tier of roughly 10 requests/minute, so
a typical daily run costs one or two requests. Structured output (`responseMimeType` plus a
`responseSchema`) returns `{index, keep, score, reason}` per job rather than prose.

The filter is **fail-open** by design: disabled, missing key, HTTP error, quota exhaustion,
unparseable body, or a verdict for a job it never mentioned — every one of these keeps the affected
jobs, and the function never raises. A wrong verdict costs one alert; a crash would cost all of them.
Rejections are logged with the model's reason, which is the fastest way to tune the prompt.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.11 | Core language |
| requests | JobsDB JSON API, Telegram, and Gemini calls |
| python-dotenv | Environment variable management |
| Gemini 2.5 Flash | Optional semantic job filtering (REST, no SDK) |
| GitHub Actions | Cron scheduling & CI/CD |
| Anaconda | Environment management |

---

## License

MIT