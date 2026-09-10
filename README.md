# JHunt 🎯

> An automated job scraper and Telegram alert system — built with Python, direct JSON APIs, and GitHub Actions.

JHunt monitors job boards on a daily schedule, filters duplicates across runs, and fires real-time Telegram alerts for every new listing found. No machine needs to be on.

---

## Features

- **Modular scraper architecture** — add new job sites by dropping a single file into `scrapers/`
- **Duplicate filtering** — persistent state via GitHub Actions Cache ensures you never see the same job twice
- **Telegram alerts** — clean, formatted notifications delivered instantly to your phone
- **Fully automated** — GitHub Actions cron job runs daily at 09:00 Bangkok time (02:00 UTC)
- **No browser required** — talks to the JobsDB JSON API directly, so a full run takes seconds
- **Optional AI filtering** — Gemini Flash can screen out non-engineering roles that keyword filters miss

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

```
GitHub Actions (cron: 09:00 BKK)
        │
        ├── Restore state cache (seen_jobs.json)
        ├── Setup Conda
        ├── JobsDBAPIScraper.scrape()          # one HTTP call per keyword
        │       └── BaseScraper (extensible base class)
        ├── StateManager.filter_new_jobs()     # dedupe against seen state
        ├── StateManager.filter_relevant_jobs()   # title keywords
        ├── StateManager.filter_by_seniority()    # drop senior/lead/manager
        ├── StateManager.filter_by_location()     # Bangkok area + remote
        ├── filter_semantically()              # optional Gemini pass
        ├── TelegramNotifier.send_job_alert()
        └── Save updated state cache
```

The `BaseScraper` abstract class enforces a consistent interface across all scrapers. Every scraper must implement `scrape()` and return a list of job dicts with the schema `{id, title, company, url}`. This means `main.py` never needs to know which scraper it's running.

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

```bash
conda env create -f environment.yml
conda activate jhunt
```

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

### 4. Initialize state file

```bash
mkdir -p data
echo '{"version": 2, "seen": {}}' > data/seen_jobs.json
```

### 5. Run locally

```bash
python main.py
```

You can also run the pieces on their own:

```bash
python -m scrapers.jobsdb_api   # scraper only — prints jobs, sends nothing
python notifier.py              # Telegram smoke test — sends two real messages
```

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

### 2. Push to main

```bash
git push origin main
```

The workflow runs automatically every day at 09:00 Bangkok time. To trigger manually: **Actions → JHunt Scraper → Run workflow**.

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

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | Required. Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | — | Required. Your personal chat ID |
| `SEARCH_KEYWORDS` | `python developer,data engineer` | Comma-separated search terms |
| `TITLE_FILTER` | 18 EN/TH keywords | Title relevance keywords, matched as substrings |
| `GEMINI_ENABLED` | `false` | Set to `true` to enable the Gemini semantic filter |
| `GEMINI_API_KEY` | — | Required only when `GEMINI_ENABLED=true` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model used for filtering |

See `.env.example` for a documented template.

### About the Gemini filter

The keyword filters can only match text, so a sales ad that mentions "Python" gets through. Enabling
`GEMINI_ENABLED` adds a pass that screens the surviving jobs for genuine junior engineering roles.

It runs on the Gemini free tier: jobs are batched 40 per request, so a typical daily run costs one or
two requests. The filter is **fail-open** — a missing key, a quota error, or an unparseable response
all keep every job, so turning it on can never cost you an alert.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.11 | Core language |
| requests | JobsDB JSON API, Telegram, and Gemini calls |
| python-dotenv | Environment variable management |
| Gemini Flash | Optional semantic job filtering |
| GitHub Actions | Cron scheduling & CI/CD |
| Anaconda | Environment management |

---

## License

MIT