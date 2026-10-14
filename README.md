# JHunt

Technical specification and operational guide for **JHunt**: a serverless market intelligence, compensation benchmarking, and portfolio blueprint synthesis platform for software engineering roles in Thailand.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Package Manager](https://img.shields.io/badge/uv-0.6%2B-purple?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![Database](https://img.shields.io/badge/Turso-LibSQL%20over%20HTTPS-teal?logo=sqlite&logoColor=white)](https://turso.tech/)
[![Inference](https://img.shields.io/badge/Gemini-3.8%20%2F%202.5%20Flash-orange?logo=google&logoColor=white)](https://ai.google.dev/)
[![Frontend](https://img.shields.io/badge/Next.js-16%20(Turbopack)-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![Tests](https://img.shields.io/badge/Tests-128%20Passed-emerald?logo=pytest&logoColor=white)](tests/)

---

## 1. System Overview

JHunt ingests software engineering postings across Thai hiring portals, normalizes unstructured salary disclosure into monthly baseline figures, extracts technology requirements via structured LLM batch inference, and computes market affinity matrices. Data is persisted to Turso (LibSQL over HTTPS) as the single source of truth and rendered via a Next.js server-rendered dashboard with real-time skill-gap telemetry.

### Core Capabilities
- **Multi-Source Scraping**: Concurrent ingestion from JobsDB (SEEK REST API), Blognone Jobs (SSR HTML / JSON-LD), and JobThai (GraphQL endpoints).
- **Deterministic Compensation Parsing**: Rule-based extraction supporting structured payloads, Unicode normalization, pay frequency multipliers (hourly, daily, annual to monthly), and false-positive rejection (postal codes, phone numbers, year spans).
- **Fault-Tolerant LLM Extraction**: Batched Gemini inference (15 postings per chunk) with exponential jittered backoff and automatic model fallback (`gemini-3.8-flash` to `gemini-2.5-flash`) on HTTP 429, 502, 503, 504, and `DEADLINE_EXCEEDED`.
- **Self-Healing Schema Synchronization**: Zero-downtime column reconciliation via `PRAGMA table_info` and isolated index execution to prevent local SQLite degradation.
- **Skill Gap & ROI Telemetry**: Live evaluation of engineer competency vectors against active market demand, outputting market coverage rates and companion skill unlock percentages.

---

## 2. System Architecture

```mermaid
flowchart TD
    subgraph INGESTION["1. Multi-Source Ingestion Layer"]
        A1["JobsDB (SEEK REST API)"] --> B["BaseScraper Adapter Interface"]
        A2["Blognone (SSR HTML / JSON-LD)"] --> B
        A3["JobThai (GraphQL Endpoint)"] --> B
        B --> C["RawJob Normalizer"]
    end

    subgraph PREPROCESSING["2. Normalization & Deduplication"]
        C --> D["Deterministic Salary Parser (Regex & Unit Multipliers)"]
        D --> E{"State Deduplication (seen_jobs.json)"}
        E -->|New ID| F["Ingestion Batch Queue"]
        E -->|Existing ID| DROP["Drop Record (Idempotent)"]
    end

    subgraph EXTRACTION["3. Fault-Tolerant LLM Extraction"]
        F --> G["BatchExtractor (15 jobs per chunk)"]
        G --> H{"Gemini API Request (gemini-3.8-flash)"}
        H -->|HTTP 200 OK| I["Pydantic v2 Schema Validation"]
        H -->|HTTP 429, 502, 503, 504, Timeout| J["Dynamic Fallback (gemini-2.5-flash with Jitter)"]
        J --> I
    end

    subgraph STORAGE["4. Single Source of Truth (SSoT)"]
        I --> K[("Turso Cloud (LibSQL over HTTPS) - Self-Healing DDL")]
        K -.->|Fallback if Offline| L[("Local SQLite (market.db) - WAL Mode")]
    end

    subgraph WEB["5. Web Telemetry & Career Engine"]
        K --> M["Next.js 16 App Router (Dynamic SSR)"]
        M --> N["Market Intelligence & Compensation Index (/analytics)"]
        M --> O["Interactive Skill Gap Matcher (/api/skill-gap)"]
        M --> P["Architecture Blueprint Reader (/blueprints/[id])"]
    end
```

---

## 3. Engineering Highlights & Failure Modes

### Multi-Source Adapter Pattern
The ingestion layer implements an abstract `BaseScraper` contract (`src/scrapers/base.py`) to isolate upstream payload variations:
- **JobsDB**: Queries SEEK public search endpoints (`/api/jobsearch/v5/search`) with unauthenticated JSON payloads.
- **Blognone**: Ingests server-side rendered listings and parses embedded JSON-LD schemas alongside Cheerio-equivalent HTML selectors.
- **JobThai**: Interacts directly with internal GraphQL search endpoints, bypassing client-side JavaScript rendering overhead.

All scrapers emit normalized `RawJob` objects with deterministic identifiers (`jobsdb_{id}`, `blognone_{id}`, `jobthai_{id}`).

### Deterministic Salary Intelligence (`src/extractor/salary_parser.py`)
Unstructured compensation data is parsed deterministically without LLM calls:
1. **Platform Payload Priority**: Extracts structured dictionary bounds (`min`, `max`, `from`, `to`, `currency`) when present.
2. **Text Normalization**: Standardizes Unicode hyphen variants (`\u2013`, `\u2014`, `\u2212`) to ASCII hyphens, strips Thai currency markers (`฿`, `.-`), and extracts ISO currency codes (`THB`, `USD`, `EUR`, `SGD`).
3. **Pay Period Conversion**: Converts all compensation figures to monthly baseline equivalents:
   - Hourly: multiplied by 160 (40 hours/week * 4 weeks)
   - Daily: multiplied by 22 (22 working days/month)
   - Annual: divided by 12
4. **False-Positive Noise Rejection**: Discards matched integers corresponding to Thai phone numbers (`081-xxx-xxxx`, `02-xxx-xxxx`), postal codes (`10110`), and year ranges (`2020-2024`).
5. **Sanity Thresholds**: Rejects THB monthly figures outside 15,000 to 1,000,000 THB and USD monthly figures outside $500 to $30,000.

### Fault-Tolerant LLM Batching (`src/extractor/gemini_client.py`)
To prevent quota exhaustion on free-tier limits (15 RPM), extraction runs through a resilient execution pipeline:
- **Batching**: Aggregates up to 15 job descriptions per request into a single prompt, returning a structured JSON array.
- **Transient Error Classification**: Classifies HTTP `429`, `502`, `503`, `504`, and Google API `DEADLINE_EXCEEDED` as transient faults.
- **Model Fallback**: Attempts primary execution via `gemini-3.8-flash`. Upon transient failure, backs off with exponential delay and randomized jitter, falling back to `gemini-2.5-flash` on subsequent retries.

### Self-Healing Schema Migrations (`src/storage/turso_client.py`)
Remote Turso cloud databases handle schema evolution without migrations scripts:
- In `init_schema()`, the client inspects live column layout using `PRAGMA table_info(jobs)` and `PRAGMA table_info(skills_extracted)`.
- If legacy columns exist (`skill`), it executes `ALTER TABLE skills_extracted RENAME COLUMN skill TO skill_name`.
- Missing columns (`min_salary`, `max_salary`, `currency`, `category`) are appended dynamically with `ALTER TABLE ... ADD COLUMN`.
- Index statements are executed in isolation with defensive try-catch wrappers, preventing index creation conflicts from aborting initialization or triggering local SQLite fallback.

### Skill Gap Matcher & ROI Engine (`web/src/lib/turso.ts`)
The analytical engine evaluates an engineer's competency vector $U = \{s_1, s_2, \dots, s_n\}$ against $N_{tech}$ active postings:
1. **Market Coverage Rate**:
   $$\text{Coverage Rate} = \frac{|\{j \in \text{Jobs} \mid \text{Skills}(j) \cap U \neq \emptyset\}|}{N_{tech}} \times 100$$
2. **Companion Skill Synergy**: Identifies co-occurring skills $c \notin U$ within matched postings, calculating co-occurrence frequency and additional market unlock percentage:
   $$\text{Unlock Potential} = \frac{|\{j \in \text{Jobs} \mid c \in \text{Skills}(j) \land \text{Skills}(j) \cap U = \emptyset\}|}{N_{tech}} \times 100$$
3. **Blueprint Alignment**: Matches generated architecture project specifications based on tech-stack intersection, displaying matched and missing technical requirements.

---

## 4. Empirical Performance & Benchmarks

Telemetry gathered across local environments and CI runners:

| Pipeline Stage | Measurement | Context / Guarantees |
| :--- | :--- | :--- |
| **Dependency Resolution** | 1.5s cold / 0.2s cache | Managed via `uv` across 53 Python dependencies |
| **Hermetic Test Suite** | 6.96s total | **128 / 128 tests passed** with 0 external network calls |
| **Next.js Production Build** | 1.2s compilation | Turbopack compilation; TypeScript validation in 2.7s |
| **Dashboard Layout Shift** | CLS = 0.00 | Dedicated SVG meters and zero-shift skeleton loaders |
| **Turso Batch Latency** | ~220ms per batch | LibSQL transactions executed over HTTPS pipeline |

---

## 5. Database Schema Contract

The relational schema is defined in `src/storage/schema.py` and enforced symmetrically across local SQLite and remote Turso (LibSQL):

### Table: `jobs`
Stores raw metadata and normalized compensation figures.
```sql
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    url TEXT NOT NULL,
    location TEXT,
    salary TEXT,
    work_type TEXT,
    raw_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    posted_at TIMESTAMP,
    source TEXT,
    min_salary INTEGER,
    max_salary INTEGER,
    currency TEXT DEFAULT 'THB'
);
```

### Table: `skills_extracted`
Stores structured technology tokens extracted from job descriptions.
```sql
CREATE TABLE IF NOT EXISTS skills_extracted (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE,
    skill_name TEXT,
    category TEXT,
    experience_level TEXT,
    must_have_skills TEXT,
    nice_to_have_skills TEXT,
    frameworks TEXT,
    databases TEXT,
    cloud_infra TEXT,
    tools TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
);
```

### Table: `generated_projects`
Stores synthesized production architecture blueprints.
```sql
CREATE TABLE IF NOT EXISTS generated_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    role TEXT NOT NULL,
    difficulty TEXT,
    domain TEXT,
    tech_stack TEXT,
    spec_markdown TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target_role TEXT GENERATED ALWAYS AS (role) VIRTUAL
);
```

### Indexes
```sql
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs (source);
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills_extracted (skill_name);
CREATE INDEX IF NOT EXISTS idx_skills_experience ON skills_extracted (experience_level);
CREATE INDEX IF NOT EXISTS idx_skills_job_id ON skills_extracted (job_id);
CREATE INDEX IF NOT EXISTS idx_projects_title ON generated_projects (title);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON generated_projects (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects (target_role);
```

---

## 6. Local Development & Verification

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or standard `venv`
- Node.js 20+ and npm

### 1. Backend Ingestion Pipeline
```bash
# Set up virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.lock

# Execute hermetic test suite (199 tests)
uv run python -m unittest discover tests

# Run ingestion pipeline across all scrapers (limit 30 records)
uv run python main.py run --all --limit 30

# Run offline analysis on existing database records
uv run python main.py analyze --role "Backend Engineer"
```

### 2. Next.js Web Dashboard
```bash
# Navigate to web application directory
cd web

# Install Node dependencies
npm install

# Run static type checking and ESLint
npm run lint

# Compile production build with Turbopack
npm run build

# Start local development server
npm run dev
```

### 3. Environment Variables (`.env`)
```ini
# Turso Database Configuration (Cloud SSoT)
TURSO_DATABASE_URL=https://jhunt-db-<org>.aws-ap-northeast-1.turso.io
TURSO_AUTH_TOKEN=eyJ...

# Google Gemini API Configuration
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3.8-flash

# Telegram Dispatcher (Optional)
TELEGRAM_BOT_TOKEN=123456789:AA...
TELEGRAM_CHAT_ID=123456789

# Scraper Search Keywords
SEARCH_KEYWORDS=python developer,backend engineer,data engineer
```

---

## 7. License

MIT License. Engineered for transparency across the software engineering talent market in Thailand.