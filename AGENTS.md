# AGENTS.md — JHunt

Shared instructions for every coding agent on this repo: Antigravity CLI (`agy`) and Claude Code.
`CLAUDE.md` imports this file, so edit rules **here only**.
Do not create `GEMINI.md`. Antigravity gives it priority over this file, so the two would split.

## What this project is

JHunt is a daily batch pipeline for the Thailand tech job market. It scrapes JobsDB, Blognone and JobThai,
extracts tech skills with Gemini, stores results in Turso, sends Telegram alerts, and generates
portfolio project blueprints. A Next.js dashboard in `web/` reads the data.
It has one developer, runs on Windows with PowerShell, and must stay 100% free tier.

## Stop and ask first

These touch production or spend quota. Never run them unless I approve in the current conversation:

- `python main.py run ...`, `python main.py alert`, `python main.py analyze`. These write to production Turso,
  send real Telegram messages, and spend the Gemini daily quota (about 20 requests/day).
- `python notifier.py`, which sends two real Telegram messages.
- Any SQL that writes to Turso (`INSERT`, `UPDATE`, `DELETE`, `ALTER`, `DROP`). Put the SQL in the plan file and let me run it.
- `gh workflow run|disable|enable`, or pushing changes to `.github/workflows/`.
- Resetting or deleting `data/seen_jobs.json`.
- Adding a dependency, a paid API, or a new top-level directory.
- `git commit`, `git push`, or any history rewrite.

## Commands (PowerShell)

```powershell
# Setup (deterministic install from lockfile)
uv venv; .venv\Scripts\activate; uv pip install -r requirements.lock

# Updating dependencies (recompile lockfile from requirements.txt; 3.11 = CI Python, keep in sync with scraper_cron.yml)
uv pip compile requirements.txt --universal --python-version 3.11 -o requirements.lock

# Python tests: hermetic, no network. Must pass before any task counts as done.
uv run python -m unittest discover tests
uv run python -m unittest tests.test_salary_parser -v   # one module

# Web
cd web; npm run lint; npm run build
```

PowerShell traps:
- `echo '...' > file` writes UTF-16 in Windows PowerShell 5.1, which breaks JSON readers. Write files with Python or `Set-Content -Encoding utf8`.
- Chain commands with `;`, not `&&`, unless the shell is PowerShell 7+.

## Definition of done

1. `uv run python -m unittest discover tests` passes. Report the count ("131 passed").
2. If `web/` changed, `npm run lint` and `npm run build` pass.
3. Every behavior change has a test that fails without the change.
4. `git diff --stat` shows only files the task needed.
5. The report lists what was **not** verified (for example, "Turso migration not run").
6. `docs/contexts/task-ledger.md` is updated when a planned task finishes.

## How to work

- Read the file and its tests before editing. Never guess a path, signature or column name: grep for it.
- Tasks that touch more than one file, or any storage, LLM, scraper or CI code, need a plan first: follow `docs/prompts/task.md`.
- One task per session. No "while I'm here" refactors; list them under "Out of scope" in the plan instead.
- If the same fix fails twice, stop and report what you tried. Do not loop.
- If this file, the README or an audit disagrees with the code, the code is the truth. Tell me about the mismatch.

## Map (as of 2026-10-12; if a path is wrong, grep for the real one and fix this section)

```
main.py                         CLI + pipeline orchestration, env helpers _csv_env/_bool_env
state_manager.py                dedupe state in data/seen_jobs.json
src/scrapers/                   base.py (BaseScraper, retries), jobsdb.py, blognone.py, jobthai.py
src/storage/                    __init__.py (get_storage), schema.py, turso_client.py, db.py (local SQLite)
src/extractor/                  gemini_client.py (retries, fallback), salary_parser.py, text_sanitizer.py, schemas.py
src/analyzer/                   skill frequency + co-occurrence
src/generator/                  ideation_engine.py (blueprint prompt), markdown_exporter.py
src/notifier/                   telegram_notifier.py
web/src/lib/turso.ts            all dashboard queries, canonicalizeSkill, skill-gap math
web/src/app/api/skill-gap/      public API route
.github/workflows/scraper_cron.yml   daily 01:00 UTC
docs/contexts/task-ledger.md    task status
docs/audits/                    audits (evidence with file:line)
2026-10-12-remediation-plan.md  current task list (Phase 0 → 1 → 2)
```

Pipeline order: `run_scrapers` → `filter_new_jobs` → `filter_relevant_jobs` → `filter_by_seniority` →
`filter_by_location` → `filter_semantically` → `notify_jobs` → `state.save()` → storage →
batch extraction → analyze → ideate → export.

## Invariants: do not break these

**Job data**
- Job IDs carry a source prefix: `jobsdb_{id}`, `blognone_{id}`, `jobthai_{id}`. Bare numeric IDs are legacy JobsDB rows.
- `_validate_job` checks only `id`, `title`, `company`, `url`. Never use `all(job.values())`: it drops about 75% of JobsDB ads, which have an empty salary.
- CI passes unset secrets as `""`, so an empty env var must count as unset (an empty `TITLE_FILTER` would match everything). In `main.py`, use `_csv_env` / `_bool_env`. Elsewhere, use `(os.getenv("X") or "").strip()` and treat `""` as unset. Never import `main` from `src/`.

**State**
- `filter_new_jobs` marks jobs seen before the later filters run. This is intended.
- `state.save()` runs in `finally`. A failed Telegram send calls `state.unmark()` so the alert retries next run.
- State writes go to a temp file, then `fsync`, then `os.replace`. Keep that order.

**Storage**
- Turso is the single source of truth. Local SQLite fallback is for a laptop only; with `JHUNT_REQUIRE_TURSO=1`, `get_storage()` must raise instead of falling back.
- Every SQL statement is parameterized. Never build SQL with f-strings or `+`.
- Writes are idempotent (`ON CONFLICT`). Re-running a day must be safe.
- `src/storage/schema.py` is the only schema definition. Live Turso can differ from it: confirm a column with `PRAGMA table_info` before relying on it. Known differences: in Turso, `skills_extracted.job_id` is the PRIMARY KEY, and `generated_projects` has no `target_role` column.
- Production SQL in a plan starts with read-only pre-checks, including one for unique-key collisions, and says what to do if any check fails (default: stop and report).

**LLM (Gemini)**
- Fail open: a Gemini failure never crashes the pipeline, and the semantic filter keeps every job when it fails.
- Extraction is batched (15 jobs per request). Never add a per-job request. The binding limit is requests per day, not tokens.
- Classify transient errors by HTTP status code (`429, 500, 502, 503, 504`) or `DEADLINE_EXCEEDED`, never by searching `str(e)` for digits. Pydantic errors contain job text like "1500".
- Validate model output with Pydantic at the boundary. Models: `gemini-3.8-flash`, falling back to `gemini-2.5-flash`.

**Salary parsing**
- The structured salary field comes first. Description text is parsed only inside a window after a salary keyword (`salary`, `เงินเดือน`, `ค่าตอบแทน`, …), and currency and pay period are detected inside that match, not across the whole description.

**Telegram**
- `parse_mode="HTML"`. Every dynamic field goes through `html.escape()` (URLs with `quote=True`). Keep the 1 s throttle.

**Tests**
- Hermetic: no network, no real Turso, Gemini or Telegram. `main.py` loads `.env` at import, so any test that builds a storage or API client must blank `TURSO_*`, `GEMINI_*` and `TELEGRAM_*` or mock the client. A past test wrote fake rows into production this way.
- Patch `time.sleep`. Test files use fixtures, not live endpoints.

**Windows and text**
- Filesystem paths use `pathlib.Path`; write Windows literals as `Path(r"C:\...")`.
- Always `open(..., encoding="utf-8")`. Job text is Thai and English.

**Security**
- The repo and its Actions logs are public. Never log secrets, tokens, or database URLs (masking misses the `https://` rewrite of a `libsql://` URL).
- Use a read-only Turso token for inspection. Never use the platform/org token for agent work.

**Cost**
- Free tier only: Python stdlib, SQLite, Turso free, Gemini free tier, GitHub Actions. No paid APIs.
