# JHunt 🎯
### Thailand Job Market Intelligence & Autonomous Portfolio Ideation Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Storage-SQLite3%20(WAL%20Mode)-green?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Validation](https://img.shields.io/badge/Contracts-Pydantic%20v2-e92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![LLM](https://img.shields.io/badge/AI-Google%20GenAI%20(Gemini%202.0%20Flash)-8E75C2?logo=google&logoColor=white)](https://ai.google.dev/)
[![CI/CD](https://img.shields.io/badge/Automation-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)](.github/workflows/scraper_cron.yml)
[![Cost](https://img.shields.io/badge/Cost%20Tier-100%25%20Free%20Tier-success)](#operational-guardrails)

---

## 1. Executive Summary & Vision

**JHunt** is an end-to-end **Job Market Intelligence & Portfolio Ideation Platform** designed for the Thailand tech ecosystem. It bridges the gap between active job market demand and candidate portfolio design by:

1. **Ingesting live tech job listings** directly from platform APIs (JobsDB / SEEK JSON API) in seconds without headless browsers.
2. **Filtering and alerting** software engineering opportunities instantly to Telegram with HTML-escaped formatting.
3. **Persisting historical market records** in a local SQLite database (`data/market.db`) with relational integrity and conflict-free deduplication.
4. **Extracting structured technology stacks** (languages, frameworks, databases, cloud, tools, and seniority levels) via Google Gemini 2.0 Flash and strict Pydantic v2 schemas.
5. **Computing market co-occurrence matrices** to uncover high-affinity technology clusters (e.g. `Go + PostgreSQL + Docker + Redis` or `FastAPI + PostgreSQL + Kafka`).
6. **Autonomously ideating and exporting enterprise-grade portfolio project specs** with YAML frontmatter directly to your local ideas repository:
   `C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project`

---

## 2. System Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                JHUNT ARCHITECTURAL PIPELINE                             │
└────────────────────────────────────────────────────────────────────────────────────────┘

  [ 1. Data Ingestion ] 
       JobsDB / SEEK Search API (Unauthenticated JSON, dateRange=3d, sort=ListedDate)
             │
             ▼
  [ 2. Filtering & Idempotency ] ──> StateManager (seen_jobs.json, 90-day TTL)
             │                       Keyword / Seniority / Thai Location Regex Filters
             ▼
  [ 3. Relational Persistence ]  ──> SQLite Storage (data/market.db)
             │                       • jobs (raw payload, title, company, salary)
             │                       • skills_extracted (FK jobs.id, tech arrays)
             │                       • generated_projects (audit trail of blueprints)
             ▼
  [ 4. Structured LLM Extraction ] 
       Text Sanitizer (Prunes Thai/EN HR perks & boilerplate, keeps technical specs)
             │
             ▼
       Gemini 2.0 Flash (Free Tier: Exponential backoff, jitter, rate-limit throttling)
             │
             ▼
       Pydantic v2 Contract (ExtractedJob schema validation & canonical casing)
             │
             ├──────────────────────────┐
             ▼                          ▼
  [ 5. Telegram Dispatcher ]     [ 6. Market Clustering Engine ]
       • HTML-escaped alerts          • Skill frequency distributions
       • Market brief dispatch        • Technology co-occurrence matrix (pair counts)
                                      • Role classification (English & Thai NLP heuristics)
                                        │
                                        ▼
                                 [ 7. Autonomous Ideation Engine ]
                                      • Anti-toy constraints (Strictly no To-Dos/blogs)
                                      • Real-world Thailand contexts (PromptPay, PDPA)
                                      • Pydantic v2 ProjectIdeaSpec validation
                                        │
                                        ▼
                                 [ 8. Windows Markdown Exporter ]
                                      • Jinja2 YAML frontmatter rendering
                                      • Windows-safe slug paths (pathlib.Path)
                                      • Auto-records metadata in market.db
```

---

## 3. Key Engineering Highlights & Seniority Signals

- **100% Free-Tier Boundary**: Zero paid external APIs. Built exclusively with Python standard library (`sqlite3`, `pathlib`, `argparse`, `json`), open-source libraries (`pydantic`, `jinja2`), and Google Gemini Free Tier.
- **Idempotent Storage & Conflict-Free Ingestion**: SQLite configured with write-ahead logging (`PRAGMA journal_mode = WAL;`) and enforced foreign keys (`PRAGMA foreign_keys = ON;`). All inserts leverage `ON CONFLICT(id) DO NOTHING` to eliminate redundant LLM processing.
- **Resilient LLM Quota Throttling**: Exponential backoff with random jitter handles HTTP 429 (`RESOURCE_EXHAUSTED`) gracefully, maintaining an inter-call throttle (default `4.0s`) to safely honor the 15 RPM free-tier ceiling.
- **Compound Thai NLP Title Classification**: Solves character segmentation challenges where Thai compound titles (e.g., `นักวิเคราะห์ข้อมูลอาวุโส`, `วิศวกรปัญญาประดิษฐ์`) fail under standard ASCII word-boundary (`\b`) regex.
- **Anti-Toy Application Guardrails**: The ideation engine strictly forbids basic CRUD, To-Do lists, and toy apps. It synthesizes enterprise constraints including PromptPay QR idempotency keys, distributed Redis locks, and outbox event streaming patterns.
- **Windows Path Safety**: All filesystem operations strictly utilize `pathlib.Path(r"...")` to eliminate backslash escape vulnerabilities (`\U`, `\N`, `\t`).

---

## 4. Directory Structure

```
JHunt/
├── .github/
│   └── workflows/
│       └── scraper_cron.yml          # GitHub Actions daily automation (09:00 Bangkok)
├── data/
│   ├── market.db                     # Relational SQLite database (gitignored)
│   └── seen_jobs.json                # Deduplication cache (gitignored)
├── docs/
│   └── contexts/
│       └── task-ledger.md            # Phased project tracking ledger
├── src/
│   ├── scraper/                      # Data collection layer
│   │   ├── base_scraper.py           # Pure ABC HTTP client contract
│   │   └── jobsdb_api.py             # SEEK public JSON search API client
│   ├── storage/                      # Persistence layer
│   │   ├── __init__.py
│   │   └── db.py                     # SQLite DatabaseManager with WAL & Foreign Keys
│   ├── extractor/                    # Structured LLM extraction
│   │   ├── schemas.py                # Pydantic v2 ExtractedJob & ProjectIdeaSpec
│   │   ├── text_sanitizer.py         # HTML/boilerplate pruner (English & Thai)
│   │   └── llm_extractor.py          # Gemini API wrapper with exponential backoff
│   ├── analyzer/                     # Market intelligence & clustering
│   │   ├── schemas.py                # MarketReport, RoleCluster, CooccurrenceItem
│   │   ├── role_classifier.py        # English/Thai regex heuristics & stack fallback
│   │   └── cluster_analyzer.py       # Frequency & co-occurrence matrix engine
│   ├── generator/                    # Portfolio ideation & export
│   │   ├── ideation_engine.py        # Gemini blueprint generator with anti-toy rules
│   │   ├── markdown_exporter.py      # Windows-safe Jinja2 markdown exporter
│   │   └── templates/
│   │       └── project_spec.md.jinja # Blueprint Jinja2 template with YAML Frontmatter
│   └── notifier/                     # Alert dispatching
│       ├── __init__.py
│       └── telegram_notifier.py      # HTML-escaped Telegram client & Market Brief
├── tests/                            # Automated test suite (41 tests)
│   ├── test_storage.py               # SQLite schema & deduplication tests
│   ├── test_extractor.py             # Sanitizer & mock Gemini extraction tests
│   ├── test_analyzer.py              # Role classifier & clustering tests
│   ├── test_generator.py             # Template rendering & file export tests
│   └── test_cli.py                   # Subcommand routing & pipeline tests
├── .env                              # Local environment variables (gitignored)
├── .env.example                      # Documented environment template
├── .gitignore                        # Git exclusion rules
├── CLAUDE.md                         # Single developer constitution & project rules
├── environment.yml                   # Conda environment definition
├── main.py                           # Unified CLI pipeline runner
├── notifier.py                       # Backward-compatibility shim
└── state_manager.py                  # Deduplication & state persistence
```

---

## 5. CLI Usage Guide

`main.py` provides three CLI interfaces powered by `argparse`:

### 1. Full Pipeline (`run --all`)
Executes the complete workflow: Scrapes jobs $\rightarrow$ stores in SQLite $\rightarrow$ filters for Telegram $\rightarrow$ extracts skills via Gemini $\rightarrow$ clusters market data $\rightarrow$ generates and exports a project blueprint $\rightarrow$ dispatches a Telegram market brief.

```bash
# Full end-to-end run (default when no arguments are provided)
python main.py run --all

# Limit LLM extraction to 5 jobs during testing
python main.py run --all --limit 5

# Override target role for blueprint ideation
python main.py run --all --role "Data Engineer / Data Analyst"
```

> **Backward Compatibility**: Running `python main.py` with no arguments defaults to `run --all`, ensuring GitHub Actions runs without any command updates.

### 2. Fast Alert Mode (`alert`)
Executes scraping, deduplication, filtering, and Telegram alert dispatching only (skips LLM extraction and spec generation).

```bash
python main.py alert
```

### 3. Offline Market Intelligence & Ideation (`analyze`)
Analyzes existing records in `data/market.db` and exports an enterprise portfolio blueprint without making external scraper calls:

```bash
# Generate blueprint for default Backend Engineer role
python main.py analyze

# Target specific engineering disciplines
python main.py analyze --role "Frontend Engineer"
python main.py analyze --role "Data Engineer / Data Analyst"
python main.py analyze --role "AI / ML / Computer Vision Engineer"
```

---

## 6. Environment Setup & Configuration

### Prerequisites
- Python 3.11+
- Conda or standard Python virtual environment

### Installation

```bash
# Option A: Conda
conda env create -f environment.yml
conda activate jhunt

# Option B: Standard Python venv
python -m venv .venv
.venv\Scripts\activate
pip install requests python-dotenv pydantic jinja2 google-genai
```

### Configuration (`.env`)

Copy `.env.example` to `.env`:

```ini
# ── Telegram Alerts ────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=123456789:AAExampleTokenReplaceMe
TELEGRAM_CHAT_ID=123456789

# ── Search Keywords ────────────────────────────────────────────────────────
SEARCH_KEYWORDS=python developer,data engineer

# ── Title Relevance Filter ─────────────────────────────────────────────────
TITLE_FILTER=python,django,fastapi,data,software,backend,programmer,developer,engineer,analyst,devops,cloud,fullstack,full stack,นักพัฒนา,โปรแกรมเมอร์,วิศวกร,นักวิเคราะห์

# ── Gemini API (Free Tier) ─────────────────────────────────────────────────
GEMINI_ENABLED=true
GEMINI_API_KEY=AIzaSy...YourKeyFromGoogleAIStudio
GEMINI_MODEL=gemini-2.0-flash

# ── Blueprint Export Directory Override (Optional) ─────────────────────────
# Defaults to: C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project
EXPORT_DIR=C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project
```

---

## 7. Testing & Verification

Run the complete test suite:

```bash
python -m unittest discover tests
```

Expected output:
```text
Ran 41 tests in 1.15s
OK
```

---

## 8. License

MIT License. Designed for software engineers, hiring managers, and students navigating the Thailand tech market.