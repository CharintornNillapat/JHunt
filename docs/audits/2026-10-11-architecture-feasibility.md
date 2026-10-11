# JHunt: Architecture & Feasibility Audit (2026-10-11)

Framework: Depth-over-Breadth & Solo-Agent Feasibility. Audited at `16221bb` ("resolve P0 and P1 audit findings"), plus the generated blueprint in `Ideas/Real-world-tech-industrial-insight-for-building-project/`.

## How the evidence was gathered

Every claim below comes from one of these four sources. Nothing is inferred from file names or docstrings alone.

| Source | What it showed |
|---|---|
| Test run: `python -m unittest discover -s tests`, scratch venv with exactly the deps in `environment.yml`, no credentials | **57 tests, 56 pass, 1 fail, 3.0 s, zero network** |
| Read-only `SELECT`s against the production Turso DB | `jobs` **482**; `skills_extracted` **7** (6 `Unknown` level, 1 `Senior`); **1.43** tech tags per extracted job on average; `generated_projects` **14 rows, 1 distinct title** |
| `gh run view 38063170672 --log` (last successful run) | First Gemini call returns `429 RESOURCE_EXHAUSTED` (daily quota). Extraction: **0 jobs**. Ideation: fallback. Turso connect to extraction start: **71 s** |
| `gh run list` | Earlier runs took **42 m**, **42 m** and **1 h 7 m** (cancelled) before the 10-minute timeout existed. Those runs most likely drained the daily quota |

---

## 1. Executive scorecard

| Dimension | Score (1-10) | Status | Key evidence / file reference |
| :--- | :--- | :--- | :--- |
| **1. Architectural depth vs. shallow breadth** (30%) | **6** | Degraded | Real failure handling: `BaseGeminiService._generate` (`src/extractor/gemini_client.py:146`) with jittered backoff, 503 model fallback and a cross-call circuit breaker (`:29, :152`); atomic `fsync` + `os.replace` state writes (`state_manager.py:102-134`); retry on failed send (`main.py:110`). But the design does not survive its actual production condition, an exhausted free-tier quota: one request per job, and 7 of 482 jobs ever extracted |
| **2. Solo-developer & agent feasibility** (25%) | **6** | Degraded | Offline, credential-free, deterministic suite (57 tests in 3 s, `time.sleep` patched). Against that: 1 red test is a regression from the latest commit, CI never runs the suite, schema is defined 3 times with drift (`db.py:97` vs `turso_client.py:133` vs `web/src/lib/turso.ts:8`), and pipeline jobs are untyped `dict`s |
| **3. Market alignment & industrial relevance** (25%) | **5** | Degraded | Domain is authentic: a live JobsDB scraper with 482 real rows and real Telegram alerts. But the product's output, "market intelligence" and blueprints, is effectively empty: 1.4 tags per extracted job, and the only blueprint is a hand-written string (`src/generator/ideation_engine.py:95-165`) inserted 14 times |
| **4. Methodological rigor** (20%) | **6** | Degraded | A true walking skeleton runs daily in CI: scrape, SQLite/Turso, Telegram, Next.js. Against that: no CI test gate, so a regression shipped, plus no `concurrency` group, no migrations, and the `os._exit` band-aid (`main.py:432`) |
| *Generated blueprint (engine output, unweighted)* | *3* | *Fail* | One fallback spec ×14. Template padding identical across items (`markdown_exporter.py:46, 56`), invented performance targets, and cardholder-data scope a solo project should never take on |
| **Weighted total** | **5.8 / 10** | **Degraded** | The engineering inside the pipeline is solid. The data it produces is not yet real |

What keeps this from a Fail: the hard parts that are present (state dedupe, retries, fail-open, idempotent writes) are implemented correctly and tested. What keeps it from a Pass: the system's purpose, turning postings into stack intelligence and blueprints, has not worked in production, and nothing alerts on that.

---

## 2. Concrete strengths (evidence-backed)

1. **Resilience is consolidated and tested.** `_generate` (`gemini_client.py:146-190`) is the one path for structured LLM calls. It throttles, separates daily-quota failures (fail fast, `:38`) from transient 429/503/timeouts (exponential backoff + jitter, `:79`), switches to `FALLBACK_MODEL` after two 503s, and opens a circuit after 3 consecutive exhausted calls. The SDK client has a 30 s timeout (`:28`). Tests pin the behavior: `test_extract_job_503_fallback_to_gemini_2_5_flash` asserts exactly 2 sleeps, and `test_extract_job_fails_fast_on_daily_quota` and `test_batch_process_stops_gracefully_on_daily_quota` cover the quota path. The production log above shows the fast-fail path working: one 429, no retry storm, and the pipeline completes in 2 m 6 s.
2. **State dedupe is crash-safe, which is uncommon in portfolio code.** `StateManager.save` writes to a same-directory temp file, `fsync`s, then `os.replace`s (`state_manager.py:102-134`), so a killed runner cannot leave a truncated file for the cache to restore forever. TTL pruning (`:77`, 90 days) bounds growth. A v1 to v2 schema migration exists. `unmark` (`:154`) plus `notify_jobs` (`main.py:110`) means a failed Telegram send is retried next run instead of being lost. `state.save()` now runs right after alerts (`main.py:296`), so dedupe no longer depends on the slow Gemini stages.
3. **Writes are idempotent at the database, not in app code.** `ON CONFLICT(id) DO NOTHING` for jobs (`db.py:137`) and `ON CONFLICT(job_id) DO UPDATE` for skills (`db.py:200`, mirrored in Turso at `turso_client.py:226`). Re-running a day is safe.
4. **Fail-open is a deliberate contract, not an accident.** The semantic filter keeps every job when Gemini fails (`gemini_filter.py:94, 131`), because a missed alert costs more than a noisy one. It batches 40 jobs per request (`:23`) with a typed `list[JobVerdict]` schema (`:79`). That batching is exactly the pattern extraction is missing (Gap 1).
5. **Transport-level retries sit at the right layer.** The scraper mounts a `urllib3.Retry` (`scrapers/jobsdb_api.py:59-62`, 429/5xx, backoff). The Telegram client honors `retry_after` with a cap (`telegram_notifier.py:28, 91-96`).
6. **Component discipline.** One batch pipeline (CLI), one store (SQLite, mirrored to Turso), one read-only presentation layer (Next.js ISR). No queue, no services, no Redis. For ~500 rows a day that is the correct shape (see "Do not add" below).
7. **LLM boundaries are typed.** `ExtractedJob` and `ProjectIdeaSpec` (`src/extractor/schemas.py`) are passed as `response_schema` and re-validated with `model_validate_json`, so malformed model output fails at the boundary instead of three modules later.

---

## 3. Gaps and "toy-code" red flags

### Gap 1. The extraction design cannot meet its own workload under the free tier (Depth, Market)
One `generate_content` per job (`llm_extractor.py:170-197`), 10 jobs per day at most, against roughly 160 new postings per day. In production the daily quota was gone before the first call, and the circuit breaker cannot fix that. Result: **7 / 482 jobs extracted (1.5%)**. "Market intelligence" computed from 7 rows is not market intelligence. The same file already contains the fix pattern (`gemini_filter.py` batches 40 per call).

### Gap 2. Extraction input is too thin to extract from (Market)
The model sees title, company, a 1-2 sentence `teaser` and up to 3 `bulletPoints` (`scrapers/jobsdb_api.py:121-122`). Measured outcome: **1.43 tags per job, 6 of 7 with experience `Unknown`**. Every chart on `/analytics` inherits this ceiling.

### Gap 3. The blueprint catalog is one hardcoded string (Market, Rigor)
`generated_projects`: 14 rows, 1 title, `Idempotent Payment Orchestrator & PromptPay Webhook Engine`. That is `_build_fallback_spec`'s backend branch (`ideation_engine.py:95-165`), not model output. The exporter inserts it again on every fallback day, and the web dedupes by title, so the site shows one card. Nothing marks it as a fallback in the DB, the markdown or the UI.

**Correction (same day, after timestamp analysis):** only rows #3 and #6 line up with pipeline runs. The other 12 arrive in same-second pairs (#1-2, #4-5, #7-8, #9-10, #11-12, #13-14), one per pipeline test in `tests/test_cli.py`. That test built a real `TursoClient()` from the developer's `.env`, which `main.py` loads at import, so **every local test run wrote a fallback blueprint, and the `cli_job_001` fixture job, into production Turso**. Rows #13-14 came from the test run made for this audit. Fixed in the follow-up commit (credentials blanked for that test class), but the existing rows still need manual cleanup.

### Gap 4. Blueprint feasibility fails the framework the engine claims to serve
The exported spec (`Ideas/.../2026-10-10_backend-engineer_idempotent-payment-orchestrator-promptpay-webhook-engine.md`):
- **Breadth over depth:** distributed locks across replicas, async settlement workers, bank-file reconciliation, token-bucket limiting, circuit breakers and PDPA residency, all in one project. Each is a project on its own. A solo developer ends up with seven half-built subsystems.
- **No walking skeleton or scope cut:** no first vertical slice, no "done" definition.
- **Unfalsifiable acceptance:** every feature reads "Complete implementation of {feature}" / "Validated with end-to-end integration tests and load benchmarks" (`markdown_exporter.py:46`), and every challenge gets the same mitigation sentence (`:56`).
- **Invented numbers:** "Sub-50ms p99" (`ideation_engine.py:161`), "10k events/sec" (`:113`), with no hardware, load or baseline.
- **Wrong risk:** "encryption of cardholder credentials" (`:162`) puts a portfolio project into PCI-DSS scope. Use PromptPay or tokenized references and never store card data.
- **The prompt asks for this breadth:** the system instruction asks for "senior-level interview talking points: ... Redis/Redlock, outbox pattern with Kafka/RabbitMQ, ... partitioning ..." (`ideation_engine.py:42`). The engine optimizes for buzzword coverage, which is the opposite of this audit's first criterion.

### Gap 5. The latest commit shipped a regression that the suite catches and CI doesn't run
`test_model_default_and_custom_override` (`tests/test_extractor.py:277`) fails because `DEFAULT_MODEL` is now resolved once at import (`gemini_client.py:23`) and the constructor no longer reads `GEMINI_MODEL` (`:117`). The workflow has no test step (`.github/workflows/scraper_cron.yml`).

### Gap 6. Three hand-maintained schemas, already drifted (Feasibility)
`generated_projects` is `(domain_industry, tech_stack, file_path, generated_at)` locally (`db.py:97`), `(difficulty, domain, tech_stack, spec_markdown, created_at)` in Turso (`turso_client.py:133`), and hand-mapped with `String(row.x ?? "")` in TS (`web/src/lib/turso.ts:46-55`). There are no migrations, only `CREATE TABLE IF NOT EXISTS`, so a column change silently does nothing on existing databases. An agent editing one copy will not know about the other two.

### Gap 7. Untyped core contract and layering leaks (Feasibility)
- The scraper-to-pipeline job is a plain `dict` validated only for 4 keys. `teaser`, `bullet_points`, `listing_date` and `location` are accessed by string key across `main.py`, `state_manager.py`, `db.py`, `turso_client.py` and `text_sanitizer.py`.
- `storage` depends on `extractor` (`db.py:18` imports `ExtractedJob`), and `db.py:286` lazily imports `analyzer.cluster_analyzer` inside a function to dodge an import cycle. That function, `get_top_skill_cooccurrences`, is called only by tests.

### Gap 8. Untested critical paths (Rigor)
No direct tests for `StateManager._prune`, the v1 migration, atomic replace or `unmark`. None for `JobsDBAPIScraper._parse_job` against a recorded API payload. None for `filter_semantically`. None for Telegram HTML escaping (only the market brief layout is tested). Nothing in `web/`. The scraper is therefore verified only against the live endpoint.

### Gap 9. Audit-001 P1 items still open at `16221bb`
- `TursoClient.__init__` `AttributeError` on a malformed URL (`turso_client.py:53-71`): not fixed.
- Per-row Turso sync: not fixed; **71 s measured** in the last run.
- No `concurrency:` group, no `permissions:` block in the workflow: not fixed.
- `os._exit` without flushing stdout (`main.py:432`): not fixed.
- `getAllProjects` still selects `spec_markdown` (`web/src/lib/turso.ts:44`). The `ProjectSummary` type was added (`:19`) but is unused.
- `BlueprintReader.tsx:1` is still `"use client"`. The memo stops the re-parse, but the 46 KB gz markdown parser still ships to the client.

### Gap 10. No reproducible environment pin (Feasibility)
`google-genai` is unpinned in `environment.yml`, there's no lock file, and no container. A fresh clone in six months resolves different versions than CI does today.

---

## 4. Actionable remediation checklist

Ordered by impact on the score. Each item names its acceptance check.

### Priority 0: make the product's output real
- [ ] **Batch extraction.** Send 10-20 sanitized jobs per request with `response_schema=list[ExtractedJobWithId]` (copy the `gemini_filter.py` pattern, keyed by job id) and lift the cap to cover each day's new rows. *Done when:* a day's run extracts every new tech job in ≤ 15 requests, and `skills_extracted / jobs` exceeds 90% after a week.
- [ ] **Fetch full descriptions for new jobs only** (one detail request per unseen id; dedupe already gives you that set). *Done when:* mean tags per extracted job ≥ 6 and `Unknown` experience share < 30%, measured with the same SQL used in this audit.
- [ ] **Stop presenting fallbacks as generated output.** Add `source TEXT CHECK (source IN ('llm','fallback'))` to `generated_projects`, skip the Turso insert when a fallback title already exists, and show "curated example" on the card. *Done when:* `SELECT source, COUNT(*)` reflects reality and there are no duplicate fallback rows.

### Priority 1: gate quality in CI
- [ ] Fix the regression: `chosen_model = (model_name or model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL).strip()` in `gemini_client.py:117`.
- [ ] Add a test job before the pipeline step: `python -m unittest discover -s tests` (stdlib, no new dependency). *Done when:* a red test blocks the scheduled run.
- [ ] Close the audit-001 leftovers in Gap 9 (all small diffs, already specified in `anti-slop/audit-001-2026-10-10.md` P1-6..P1-13).

### Priority 2: one contract, one schema
- [ ] Add `migrations/001_init.sql`, `002_...sql` applied by a ~20-line runner to both SQLite and Turso with a `schema_version` table. Delete the duplicated `CREATE TABLE` blocks in `db.py` and `turso_client.py`. *Done when:* one SQL file defines `generated_projects` and the two stores have identical columns.
- [ ] Add a `JobPosting` Pydantic model at the scraper boundary (`_parse_job` returns it) and pass models, not dicts, through `main.py`.
- [ ] Move shared schemas to `src/contracts.py` so `storage` stops importing `extractor`. Delete the test-only `get_top_skill_cooccurrences` and its lazy import.

### Priority 3: cover the paths that guard data
- [ ] `tests/test_state_manager.py`: prune boundary, v1 migration, `unmark`, and a crash between temp write and replace leaving the old file intact.
- [ ] `tests/fixtures/jobsdb_search.json` (one recorded API page) plus a `_parse_job` test. This also gives a fully offline end-to-end test by feeding the fixture to `run_full_pipeline` with mocked Gemini and Telegram.
- [ ] One escaping test: a job title containing `<b>&"` produces valid Telegram HTML.

### Priority 4: make the blueprints solo-feasible
- [ ] Rewrite `IDEATION_SYSTEM_INSTRUCTION` around depth: one core service, one store, one async path. Require a numbered walking-skeleton slice, 3-5 falsifiable acceptance tests ("replaying the same webhook 100× produces exactly 1 ledger entry"), and an explicit out-of-scope list. Drop the buzzword list at `ideation_engine.py:42`.
- [ ] Extend `ProjectIdeaSpec` with `walking_skeleton: list[str]`, `acceptance_tests: list[str]`, `out_of_scope: list[str]`, and render those instead of the template padding at `markdown_exporter.py:46, 56`.
- [ ] Remove invented performance targets and "cardholder credentials" from the three fallback specs.

### Priority 5: reproducibility
- [ ] Pin `google-genai` and commit a lock (`pip freeze > requirements.lock`, installed in CI). A Dockerfile is optional: it adds a demo story but no verification the lock doesn't already give.

### Do not add
The criteria mention FastAPI, AsyncIO, Redis and Docker as high-demand pairings. Adding them here would **lower** the Component Hygiene score. The workload is one daily batch of ~500 rows with no request path, no shared mutable cache and no concurrency. The depth signal for this project comes from batching under quota, measured extraction quality, migrations, and crash-safe state. A stack checklist would not add it.
