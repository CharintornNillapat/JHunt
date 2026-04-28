# JHunt 🎯

> An automated job scraper and Telegram alert system — built with Selenium, Python, and GitHub Actions.

JHunt monitors job boards on a daily schedule, filters duplicates across runs, and fires real-time Telegram alerts for every new listing found. No machine needs to be on.

---

## Features

- **Modular scraper architecture** — add new job sites by dropping a single file into `scrapers/`
- **Duplicate filtering** — persistent state via GitHub Actions Cache ensures you never see the same job twice
- **Telegram alerts** — clean, formatted notifications delivered instantly to your phone
- **Fully automated** — GitHub Actions cron job runs daily at 09:00 Bangkok time (02:00 UTC)
- **Headless Selenium** — runs without a display, compatible with CI/CD environments

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
│   ├── base_scraper.py           # Abstract base class
│   └── jobsdb_scraper.py         # JobsDB implementation
├── .env                          # Local secrets — never committed
├── .gitignore
├── environment.yml               # Conda environment definition
├── main.py                       # Orchestrator
├── notifier.py                   # Telegram notification module
├── state_manager.py              # Duplicate filter & state persistence
└── requirements.txt
```

---

## Architecture

```
GitHub Actions (cron: 09:00 BKK)
        │
        ├── Restore state cache (seen_jobs.json)
        ├── Setup Conda + Chrome
        ├── JobsDBScraper.scrape()
        │       └── BaseScraper (extensible base class)
        ├── StateManager.filter_new_jobs()
        ├── TelegramNotifier.send_job_alert()
        └── Save updated state cache
```

The `BaseScraper` abstract class enforces a consistent interface across all scrapers. Every scraper must implement `scrape()` and return a list of job dicts with the schema `{id, title, company, url}`. This means `main.py` never needs to know which scraper it's running.

---

## Getting Started

### Prerequisites

- [Anaconda](https://www.anaconda.com/) or Miniconda
- Google Chrome installed
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

Create a `.env` file at the project root:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
SEARCH_KEYWORDS=python developer,data engineer
HEADLESS=false
```

### 4. Initialize state file

```bash
mkdir -p data
echo '{"seen_ids": []}' > data/seen_jobs.json
```

### 5. Run locally

```bash
python main.py
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
# scrapers/indeed_scraper.py
from .base_scraper import BaseScraper

class IndeedScraper(BaseScraper):
    def scrape(self) -> list[dict]:
        # your implementation
        ...
```

```python
# main.py — run_scrapers()
from scrapers.indeed_scraper import IndeedScraper

indeed = IndeedScraper(keywords=config["keywords"], headless=config["headless"])
all_jobs.extend(indeed.scrape())
```

Nothing else in the pipeline changes.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_KEYWORDS` | `python developer,data engineer` | Comma-separated search terms |
| `HEADLESS` | `true` | Set to `false` to watch the browser locally |
| `TELEGRAM_BOT_TOKEN` | — | Required. Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | — | Required. Your personal chat ID |

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.11 | Core language |
| Selenium 4 | Browser automation & scraping |
| python-dotenv | Environment variable management |
| requests | Telegram API calls |
| GitHub Actions | Cron scheduling & CI/CD |
| Anaconda | Environment management |

---

## License

MIT