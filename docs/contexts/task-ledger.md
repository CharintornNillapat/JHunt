# Task Ledger: JHunt Market Intelligence & Portfolio Ideation Platform

> **Tracking Document**: Maintained across all execution phases.
> **Last Updated**: 2026-10-10

---

## 1. Project Overview & Architectural Vision
Elevate `JHunt` from a keyword scraper and Telegram alerter into a production-grade, end-to-end **Job Market Intelligence & Portfolio Ideation Platform** focused on the Thailand tech market.

### Core Modules
- `src/scraper`: JobsDB / SEEK API extraction clients.
- `src/storage`: Local SQLite persistence (`data/market.db`) & state management.
- `src/extractor`: Gemini API client with Pydantic schema validation.
- `src/analyzer`: Skill frequency & co-occurrence matrix clustering.
- `src/generator`: Portfolio ideation engine & Jinja2 Markdown blueprint exporter.
- `src/notifier`: HTML-escaped Telegram notification dispatcher.

---

## 2. Phased Roadmap & Task Checklist

### Phase 0: Environment Audit & Project Governance Setup
- [x] Inspect existing `JHunt` codebase (scraper logic, Telegram dispatcher, configs, dependencies).
- [x] Review and update existing `CLAUDE.md` to reflect new architecture standards, coding guidelines, cost boundaries, and module boundaries.
- [x] Ensure directory `docs/contexts/` exists.
- [x] Create `docs/contexts/task-ledger.md` containing the structured roadmap and actionable checklist.
- [x] Verify `.gitignore` ignores `data/*.db`, local caches, `.env`, and virtual environment artifacts.

### Phase 1: Data Contracts & Local Persistence
- [x] Define Pydantic schemas (`src/extractor/schemas.py`):
  - [x] `ExtractedJob`: `job_title`, `company`, `experience_level`, `must_have_skills`, `nice_to_have_skills`, `frameworks`, `databases`, `cloud_infra`, `tools`.
  - [x] `ProjectIdeaSpec`: `title`, `domain_industry`, `target_tech_stack`, `architecture_overview`, `core_features`, `database_schema`, `engineering_challenges`, `difficulty`.
- [x] Implement SQLite database layer (`src/storage/db.py`):
  - [x] Table schemas: `jobs`, `skills_extracted`, `generated_projects`.
  - [x] Methods: `job_exists(job_id)`, `save_job()`, `get_unprocessed_jobs()`, `save_extracted_skills()`, `get_top_skill_cooccurrences()`, `record_generated_project()`.
- [x] Update `environment.yml` with `pydantic>=2.0`, `jinja2>=3.1`, and `google-genai`.
- [x] Verify unit tests in `tests/test_storage.py` (8 passing unit tests covering schema validation, SQLite CRUD, duplicate prevention, and co-occurrences).

### Phase 2: LLM Extraction Pipeline
- [x] Implement text sanitization (`src/extractor/text_sanitizer.py`): strip boilerplate, benefits, and legal copy to conserve token quota while preserving Thai and English technical keywords.
- [x] Implement Gemini API client wrapper (`src/extractor/llm_extractor.py`) using `google-genai` SDK with exponential backoff and rate-limit handling for free-tier quotas.
- [x] Integrate structured output validation with Pydantic `ExtractedJob`.
- [x] Implement batch extraction queue runner `process_unprocessed_jobs()`.
- [x] Add unit tests in `tests/test_extractor.py` (9 passing tests verifying sanitization, mock Gemini responses, retries, and batch processing).

### Phase 3: Market Analysis & Tech Clustering
- [x] Implement role classification engine (`src/analyzer/role_classifier.py`): English & Thai regex heuristics with fallback to extracted tech stacks.
- [x] Implement schemas for market reporting and clustering (`src/analyzer/schemas.py`).
- [x] Implement cluster analyzer (`src/analyzer/cluster_analyzer.py`):
  - [x] Calculate frequency distributions of must-have, nice-to-have, frameworks, databases, and cloud tools.
  - [x] Compute a co-occurrence matrix to identify common paired stacks in Thailand (e.g. Go + Docker, Python + PostgreSQL).
  - [x] Extract dominant tech clusters per role (Backend, Frontend, Fullstack, Data, DevOps, AI/ML).
- [x] Expose package interface via `src/analyzer/__init__.py`.
- [x] Add unit tests in `tests/test_analyzer.py` (5 passing tests verifying role classifications, frequency metrics, co-occurrences, and dominant stack resolution).

### Phase 4: Autonomous Project Spec Generator & Exporter
- [x] Create Jinja2 / Markdown template (`src/generator/templates/project_spec.md.jinja`): YAML frontmatter, business context, architecture overview, DB schema, and engineering interview challenges.
- [x] Implement ideation engine (`src/generator/ideation_engine.py`): Gemini structured output prompt synthesis, anti-toy constraints, Thailand industry alignment, and deterministic fallback models.
- [x] Implement markdown exporter (`src/generator/markdown_exporter.py`):
  - [x] Target directory: `C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project` (using `pathlib.Path(r"...")`).
  - [x] Filesystem-safe slug naming: `YYYY-MM-DD_<role-slug>_<project-slug>.md`.
  - [x] Persists generated project records into SQLite `generated_projects` table.
- [x] Expose package interface and orchestrator via `src/generator/__init__.py`.
- [x] Add unit tests in `tests/test_generator.py` (8 passing tests verifying Jinja2 rendering, markdown writing, database logging, mock Gemini generation, and offline fallback).

### Phase 5: Pipeline Orchestration & Telegram Integration
- [x] Refactor `main.py` into a unified pipeline runner supporting CLI subcommands:
  - [x] `python main.py run --all` (Scrape -> Extract -> Save -> Notify Telegram -> Generate Ideation -> Export MD, with default fallback when no args provided for GitHub Actions compatibility).
  - [x] `python main.py alert` (Fast path: legacy scraping and Telegram alerting only).
  - [x] `python main.py analyze` (Offline path: analytics and blueprint generation from SQLite DB without re-scraping).
- [x] Implement Telegram Market Intelligence Brief formatter (`send_market_brief`) in `src/notifier/telegram_notifier.py`.
- [x] Maintain root `notifier.py` and `src/scraper/` backwards compatibility shims.
- [x] Add unit and integration tests in `tests/test_cli.py` (11 passing tests verifying CLI parsing, routing, and pipeline execution).
- [x] Verify legacy Telegram alert compatibility without breaking changes.

### Phase 6: Dry Run, Testing & Documentation
- [x] Run end-to-end integration test on a sample set of job postings (`python main.py run --all --limit 3`).
- [x] Verify SQLite persistence in `data/market.db` (161 jobs stored, 2 generated projects tracked).
- [x] Verify generated Markdown file writes successfully to the target Windows path:
  `C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project\2026-10-10_backend-engineer_idempotent-payment-orchestrator-promptpay-webhook-engine.md`.
- [x] Perform documentation overhaul on `README.md` (architecture flow, engineering highlights, CLI guide, setup instructions).
- [x] Run complete repository test suite (`python -m unittest discover tests` — 41 tests passing).
- [x] Update `docs/contexts/task-ledger.md` with final execution status (100% Complete).

### Phase 7: Scale, Performance & Cloud Architecture Upgrades
- [x] **Database Performance Indexing**: Added idempotent B-Tree indexes on `skills_extracted`, `jobs`, and `generated_projects` across SQLite and Turso.
- [x] **Prompt Optimization**: Deterministic pre-cleaning and truncation for job descriptions in `src/extractor/text_sanitizer.py`.
- [x] **CI Acceleration**: Migrated GitHub Actions workflow (`scraper_cron.yml`) to `uv` (`astral-sh/setup-uv@v5`), cutting CI runner startup time to sub-5s.
- [x] **Frontend Code-Splitting**: Dynamic import of Recharts in `web/` with dark Obsidian loading skeleton.
- [x] **Storage SSoT Migration**: Established Turso (LibSQL over HTTPS) as Single Source of Truth for production data ingestion, with SQLite fallback, eliminating CI runner SQLite cache.
- [x] **LLM Gateway Timeout Resilience**: Classified HTTP 504, 502, 500, and DEADLINE_EXCEEDED as transient errors in `gemini_client.py` and triggered immediate fallback to `gemini-2.5-flash` with exponential backoff.
- [x] **Self-Healing Turso Schema Migration**: Implemented dynamic column migration (`skill` -> `skill_name`, `category`) and non-blocking isolated index execution in `turso_client.py`.
- [x] **Dynamic SSR & Analytics Resilience**: Enabled dynamic SSR on `/analytics` (`dynamic = 'force-dynamic'`, `revalidate = 0`, `fetchCache = 'force-no-store'`), eliminating build-time SSG empty-state caching; added structured diagnostics, null-safe experience filter, and query fallback in `web/src/lib/turso.ts`.
- [x] Comprehensive test suite expanded to 102 tests with 100% pass rate.

### Remediation Plan (2026-10-12)

#### Phase 0: Immediate Emergency & Data Integrity Fixes (P0)
- [x] **Task 0.1: ID Continuity Migration & State Compatibility** (Turso migration applied on live database; state_manager updated).
- [x] **Task 0.2: Enforce Turso as Single Source of Truth in CI** (`JHUNT_REQUIRE_TURSO=1`).
- [x] **Task 0.2.1: Task 0.2 review fixes; keep the Turso URL out of logs**
- [x] **Task 0.3: Restore CI Log Observability** (`PYTHONUNBUFFERED=1`).
- [x] **Task 0.4: Restore Scraper Keyword Coverage** (Track `keyword_count >= limit`).
- [x] **Task 0.5: Prevent Ingestion Queue Starvation** (`ORDER BY created_at DESC`).

#### Phase 1: Reliability, Data Quality & LLM Pipeline (P1)
- [x] **Task 1.1: Salary Parser Precision & Noise Rejection** (Keyword window + local currency/period).
- [x] **Task 1.2: Historical Salary Backfill** (Query unparsed jobs, parse with parse_salary, batch-update Turso/SQLite).
- [x] **Task 1.3: Structural Error Classification** (Stop retrying Pydantic errors on 500/1500).
- [x] **Task 1.4: Schema & Index Reconciliation** (Align role index on generated_projects).
- [x] **Task 1.5: Blueprint Logic & Exporter Fixes** (Interleaving tests, strip '..').

#### Phase 2: Analytics Rollup & Web Optimization (P2 / P3)
- [x] **Task 2.1: Pre-Aggregated Rollup Table** (`skill_stats` populated on pipeline completion).
- [x] **Task 2.2: Statistically Honest Telemetry** (Enforce `currency = 'THB'`, sample size floor $n \ge 5$, sample badges, 0% floor removed).
- [x] **Task 2.3: ISR Caching & On-Demand Revalidation** (`export const revalidate = 3600;` on `/` & `/analytics`, `/api/revalidate`, CI step 8).
- [x] **Task 2.4: Eliminate Duplicate Client Mount Query & API Memoization** (Skip initial mount fetch, 10-min TTL in `turso.ts` and `route.ts`).

---

## 3. Operational Guardrails Log
- **Cost Policy**: 100% Free Tier (Python stdlib, SQLite, Turso Starter/Free, Google GenAI Free Tier).
- **Pathing Policy**: Always use `pathlib.Path(r"...")` for Windows filesystem operations.
- **Single Developer Constitution**: `CLAUDE.md` is strictly maintained; no `GEMINI.md` is created.
