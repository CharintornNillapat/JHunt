# JHunt: Architectural Reflection & Technical Audit (2026-10-12)

Audited at `04e23dd` (12 commits after the 2026-10-11 audit: scraper adapters, salary parser, skill-gap matcher, Turso-as-SSoT, uv CI).

## Evidence base

Every finding below cites one of these. Nothing is inferred from file names or the README.

| Source | Result |
|---|---|
| Test suite, scratch venv from `requirements.txt`, no credentials | **128 / 128 pass, 8.2 s.** Re-run with a canary `TURSO_DATABASE_URL`: no test contacts it |
| Read-only `SELECT`s on production Turso | 259 jobs, **all bare numeric ids, `source` NULL**; **3 / 259** with parsed salary; 36 `skills_extracted` rows (6 Non-Tech), **1.23 tags per tech job**; 1 blueprint (#16); `idx_projects_role` **absent** |
| Latest CI run `38141825333` (commit `9649832`, 2026-10-11 13:05 UTC) | Batch extraction **30 jobs in 2 requests**; semantic filter **504 after 29 s**; index batch **fails on `target_role`**; **zero `print()` lines** in the pipeline step; DB hostname printed unmasked |
| Turso latency from this machine (Thailand to `aws-ap-northeast-1`), 5 runs per query | **~105 ms median per query** regardless of query; plans use indexes; cost is network round trips |
| Salary parser fuzzing, 15 realistic inputs | 6 misparses, all through the description fallback (table in Phase 2.2) |
| `gh repo view` | Repository is **public**, so Actions logs are public |

**Not measured:** TTFB of the deployed site (deployment URL unknown, Vercel connector not authorized), hydration warnings in a live browser, and Cloudflare/Akamai behavior of Blognone or JobThai. The scraper adapters (`859240d`) **have never run in CI**: the latest run predates them.

> **Time-sensitive.** The 01:00 UTC cron on 2026-10-12 is the first production run of the new adapters. It will (1) re-alert JobsDB jobs already alerted, because ids changed from `95178481` to `jobsdb_95178481` and `seen_jobs.json` holds the bare ids; (2) insert prefixed duplicates of postings already in Turso; (3) scrape only 50 JobsDB jobs from the first keyword. See P0-2. To defer it: `gh workflow disable "JHunt Scraper"`.

---

## Phase 1. Architectural reflection (สะท้อนแนวคิด)

### 1.1 Single source of truth & the serverless model

The move from ephemeral runner SQLite to Turso is the right call. CI runners are disposable, and Turso is now the only place data survives. Three implementation choices undercut it:

1. **The fallback defeats the SSoT.** `get_storage()` (`src/storage/__init__.py:28-40`) returns local SQLite whenever Turso fails to initialize. In CI, local SQLite is deleted with the runner, the run still reports success, and `print` output (which says "local SQLite") is lost (P0-3). An outage therefore costs a day of data silently. Fallback is right for a laptop and wrong for the system of record.
2. **Two sources of truth remain for "seen".** Dedupe still lives in `data/seen_jobs.json` in the Actions cache, while `jobs` in Turso already records every posting. The id change (P0-2) shows the hazard: two stores, one renamed key, no migration for either.
3. **The schema is declared, not migrated.** `CREATE TABLE IF NOT EXISTS` plus ad-hoc `ALTER`s means the DDL in `schema.py` and the live tables disagree. Turso's `generated_projects` has no `target_role`, so `idx_projects_role` fails every run (CI log). Turso's `skills_extracted` keeps `job_id PRIMARY KEY` while a fresh local DB gets `id AUTOINCREMENT, job_id UNIQUE`. Startup does ~13 sequential round trips (~3.5 s) every run to re-assert this.

**Connection overhead is not the risk you might expect.** Both clients speak libSQL over HTTPS (`@libsql/client` in Next.js, `libsql-client` in Python), so there are no TCP pools to exhaust from serverless functions or runners. The real costs are **per-query latency** (~105 ms measured, regardless of query size) and **per-view row reads**: `/analytics` is `force-dynamic` and runs 7 queries per view, including a full scan of `skills_extracted`, then the client repeats 3 of them on mount (Phase 2.4). Unused LibSQL capabilities: batch transactions are used for writes, but not migrations with a version table, and not embedded replicas (local reads for the Python analysis stage).

### 1.2 Anti-slop & real-world blueprint generation

Blueprint #16 ("Exactly-Once PromptPay Webhook Ingestion and Merchant Ledger Engine") is **substantially better** than the hard-coded archetype it replaced. One service, one Postgres, `UNIQUE (provider, transaction_id)`, `SELECT … FOR UPDATE`, satang integers, CHECK constraints, falsifiable count-based tests, an explicit out-of-scope list. The prompt rewrite works.

Speculation still leaks through as **logic errors, not buzzwords**. A model can now produce a plausible-looking spec that is wrong in ways a reviewer will catch:

| # | Defect in #16 | Why it matters |
|---|---|---|
| a | Out-of-order refund returns **HTTP 422** "allowing gateway retry" | Most webhook senders treat 4xx as final and only retry 5xx or timeouts, so the refund is dropped. Park it as PENDING with 200, or return 409/503 per the provider's documented retry contract |
| b | Insufficient funds: "transaction rolls back, **status is stored as FAILED…**" | After a rollback nothing is stored. The status write needs its own transaction. The spec contradicts itself |
| c | "pytest-xdist to issue 100 concurrent POST requests" | xdist parallelizes *tests* across processes. It does not issue concurrent requests inside one test (use `asyncio.gather` with `httpx.AsyncClient`, or a thread pool) |
| d | "50 CREDIT + 50 DEBIT simultaneously … assert balance == 25,000" | Starting from 0, debits that land before enough credits hit the `>= 0` CHECK and fail. The final balance is interleaving-dependent, so the test is flaky by construction |
| e | `merchant_balances.version INT` | Never read. Optimistic-lock residue next to a pessimistic `FOR UPDATE` |
| f | Stack entries "Python 3.12", "PostgreSQL 16" | `canonicalizeSkill` maps neither to its canonical name, so the skill-gap blueprint match understates coverage (cross-feature bug) |
| g | Rendered "`…threads..**`" and "`1. Step 1:`" | Exporter appends "." to text that already ends with one and numbers steps the model already numbered (`markdown_exporter.py`) |

Defects (a)-(d) are the kind a staff engineer finds in five minutes, and they sit exactly in the concurrency and idempotency claims the project exists to demonstrate. A second Gemini pass, "find contradictions between failure_modes, contracts and verification; every verification must hold under any interleaving", costs 1 request per day and targets this class directly.

### 1.3 Data authenticity vs. heuristic estimation

The statistics are presented with more confidence than the data supports:

- **Sample size.** Market percentages divide by **30 tech jobs averaging 1.23 tags each**. "Top compensated skills" rests on jobs that have *both* a parsed salary (3 in Turso) and a `skill_name` (3 rows), an intersection of 0 to 3 jobs, behind `HAVING sample_count >= 1`. Nothing on the page shows n.
- **Salary per skill is not per skill.** `skill_name` is one column per job row, populated for 3 rows. A job requiring `["Python", "Java"]` credits its salary only to whichever single skill landed in `skill_name`. Correct attribution explodes every skill list (`json_each`) per job.
- **Midpoint averaging.** `AVG((min+max)/2)` is defensible for advertised bands, but as written it mixes currencies (no `currency = 'THB'` filter), drops min-only and max-only offers ("From 40,000"), and inherits the parser's 15,000 THB floor, which silently removes internships and biases the benchmark upward. Report the median with the interquartile range, n, and the filter rules.
- **Skill gap "unlock".** Coverage counts a job as matched if **any one** of your skills appears in it. Under that definition "learning X unlocks N jobs" is arithmetically consistent, but it reduces to "the most frequent skill you lack". The score `unlock × 2.0 + coOccur × 1.5` has no stated basis, and `unlockPercentage` is floored at **1 %** even when the unlock count is 0 (`turso.ts`). A meaningful definition is the fraction of a job's *must-have* skills covered, and "unlock" means crossing a threshold (for example 70 %).
- **Source mixing.** Blognone and JobThai supply full descriptions; JobsDB supplies only a teaser. Skill frequencies will therefore over-represent the two smaller boards, because their jobs simply contain more extractable tags.

---

## Phase 2. Deep technical audit (Audit เชิงลึกรอบด้าน)

### 2.1 Scraper & ingestion

| Finding | Evidence |
|---|---|
| **JobsDB coverage collapsed.** `limit=50` caps the *whole* scrape; the first keyword's first page (100 rows) fills it, and the second keyword is never queried. The old adapter took up to 500 per keyword | `main.py run_scrapers(limit=50)`; `src/scrapers/jobsdb.py:145, 160, 179` |
| **Id scheme changed without migration.** `jobsdb_{id}` vs the bare ids in Turso (259 rows) and in `seen_jobs.json` | `jobsdb.py:72`; probe: 259/259 numeric; `state_manager.py` unchanged since `024de9b` |
| **Detail fetches are unthrottled.** Blognone and JobThai issue one detail request per job back to back; `REQUEST_DELAY` applies only between search pages | `blognone.py:188` vs `:229`; `jobthai.py:461` vs `:498` |
| **Unbounded worst-case time.** 15 s timeout × (1 + 3 retries) plus backoff per request, with no overall deadline. A slow upstream pushes the run past `timeout-minutes: 10` before anything is stored | `base.py:149-153` |
| **`Retry-After` is honored with no cap.** urllib3 sleeps for whatever a 429/503 says; a bot wall answering `Retry-After: 3600` hangs the job until it is killed | `base.py:149` (`Retry` defaults) |
| **Silent schema drift.** If Blognone's embedded-JSON regex or JobThai's persisted-query hash stops matching, each returns `[]` and logs only "Total unique jobs: 0" at INFO. Only JobsDB warns on zero | `blognone.py:46-69, 263`; `jobthai.py:296`; `jobsdb.py:182` |
| **`posted_at` is really `updated_at`** for Blognone and JobThai, so bumped listings look new | `blognone.py:174`, `jobthai.py:455` |
| Memory footprint: non-issue. Hundreds of `RawJob`s of a few KB each | `src/models/job.py` |

Bot walls were not tested. Both new adapters scrape unauthenticated endpoints with a static desktop UA, so treat them as best-effort sources and make them **fail loudly** rather than hardening them.

### 2.2 Extraction & LLM pipeline

- **Batching works in production:** 30 jobs, 2 requests, about 21 s and 9 s (CI log). Requests per run: filter 1 + extraction 2 + ideation 1 = **4**. Worst case with retries is about 13 of the ~20 daily free requests, so two manual dispatches plus the cron on one day can exhaust the quota.
- **TPM is not the constraint.** 15 descriptions × ≤1,500 chars is roughly 6-8k input tokens; Thai text tokenizes denser but stays well inside limits. **RPD is the binding constraint.**
- **Error misclassification.** `is_transient_error` treats any message containing the substring `"500"` or `"502"` as transient (`gemini_client.py`). Pydantic `ValidationError`s embed the offending input, and job text is full of numbers like `1500` and `25,000`, so a deterministic schema failure can be retried 4 times, burning 4 requests.
- **No infinite loop**, because retries are bounded by `MAX_RETRIES = 4` and the breaker opens at 3 failed calls. But there is **no wall-clock budget**: about 30 s timeout × 4 attempts + 35 s backoff per call, across filter, 2 extraction batches and ideation, totals about 8 min of Gemini alone against a 10 min job that also scrapes.
- **Poison batch.** The queue is `ORDER BY created_at ASC` and batches are deterministic. A batch that always fails (safety block, truncated output, a bad record) is re-sent first every day, permanently costing 1 of 2 extraction requests while newer jobs wait. Separately, with ~30 extractions a day against more new postings than that, oldest-first means fresh jobs may never be reached.
- **Salary parser.** The salary *field* parses correctly in every case tested. Every misparse comes from the **description fallback**, which also determines currency and pay period over the whole text:

| Input (description) | Parsed | Defect |
|---|---|---|
| `Salary 35,000 - 45,000 THB. OT paid 200 THB/hour.` | 32,000 – 32,000 | "/hour" anywhere sets the period to hourly for the whole text |
| `We serve 50,000+ merchants` | min 50,000 | count read as salary |
| `Project budget 100,000 - 500,000 THB` | 100k – 500k | budget read as salary |
| `US clients ($) … Salary 60,000 THB` | 60,000 **USD** | any `$` relabels the currency |
| salary `Negotiable` + `team of 20,000+ engineers` | min 20,000 | non-disclosure overridden |
| `Bonus up to 120,000 THB annually` | max 120,000/mo | bonus as salary; "annually" not detected |

The integer guardrails do hold: values are bounded to 15k–1M THB, so no corrupt magnitudes reach Turso. They are wrong-but-plausible values, which is worse for a benchmark. Also, only **3 / 259** Turso rows have a parsed salary, because existing rows were never backfilled. About 25 of the existing raw labels sampled (`฿30,000 – ฿45,000 per month`) parse correctly today.

### 2.3 Storage & database

- **Migration safety.** It runs only `ADD COLUMN` and `RENAME COLUMN`: no truncation, no table rewrite, no data loss path. Two concurrent runs racing the same `ALTER` produce a "duplicate column" error that is caught and logged. With `concurrency` in CI that race requires a local run alongside CI. Acceptable.
- **The real migration risk is silent divergence** (Phase 1.1 #3), plus 40 duplicated lines (`_get_jobs_columns` and `_get_skills_extracted_columns` are identical) and the table batch in `init_schema` sitting outside any `try`. A DDL failure there aborts init and triggers the silent SQLite fallback.
- **Index strategy.** At current volumes the indexes are irrelevant (~105 ms is all RTT). At 100k rows the bottleneck is not B-trees but **shipping and JSON-parsing every `skills_extracted` row in a serverless function on every page view**. Specifics:
  - `idx_jobs_posted_at` and `idx_jobs_source` are **used by no query** (grep): pure write cost.
  - `idx_skills_experience` is low-cardinality and backs a `!=` predicate, so it's unhelpful.
  - `idx_skills_job_id` duplicates the primary-key auto-index.
  - `idx_skills_name` serves the compensation join, but on the wrong column (Phase 1.3).
  - `idx_projects_role` never exists.
  
  What `/analytics` needs is a **pre-aggregated rollup written once per pipeline run** (Top-3 #3), not more indexes.

### 2.4 Frontend

- **`force-dynamic` on `/` and `/analytics`.** Every view runs live queries. `/analytics` runs 4 (analytics) + 3 (skill gap, including `getAllProjects()` with every blueprint's full `spec_markdown`). Then `SkillGapMatcher`'s `useEffect` fires on mount with the same skills the server already computed: 3 more queries and a duplicate request. The data changes once a day, so ISR with on-demand revalidation from CI is the correct model.
- **Code splitting.** `nextDynamic()` in a Server Component without `ssr: false` still server-renders, so the `loading` skeleton only appears during client chunk loading. Recharts is already route-split to `/analytics`. The chart containers have fixed heights (`h-64`), so CLS risk is low. Hydration warnings were not observed in a browser (not measured).
- **`/api/skill-gap`.** Unauthenticated, uncached, available as both GET and POST. Inputs are capped at 30 items (POST also ≤50 chars each; GET has no per-item length cap). Each call does 3 Turso queries, including a full table scan and all blueprint markdown, so a simple loop burns Turso free-tier row reads and function invocations. Errors inside `calculateSkillGap` return HTTP 200 with zeros, which is indistinguishable from "no matches". CPU per request is small; the DoS vector is **cost**, not compute.

### 2.5 Security & production readiness

| Finding | Severity | Evidence |
|---|---|---|
| **No hardcoded secrets.** MCP configs use `${VAR}` placeholders | OK | `.mcp.json`, `.claude/mcp.json` |
| **SQL injection parity holds.** Every Python and TS query is parameterized; no interpolated SQL found | OK | grep across `src/`, `web/src` |
| **Unpinned third-party MCP gets an org-admin token.** `npx -y mcp-turso-cloud` (v0.0.x) runs whatever is latest, with `TURSO_API_TOKEN`, which can create and **delete databases** and mint tokens. The root `package.json` also aliases it as `@tursodatabase/mcp`, a scope it is not published under | High (supply chain) | `.mcp.json:6-7`, `package.json:26` |
| **DB hostname in public Actions logs.** The secret is masked as `libsql://…`, but code rewrites it to `https://…` and logs that string, which the masker doesn't know | Low-Medium (token not exposed) | CI log line; `turso_client.py:66` |
| `/api/skill-gap` cost amplification | Medium | 2.4 |
| `.claude/mcp.json` duplicates `.mcp.json`; Claude Code reads the root file | Hygiene | both files |

---

## Phase 3. Prioritized actions (ข้อเสนอแนะเพื่อพัฒนาต่อ)

| Priority | Category | Finding / Opportunity | Proposed Solution | Expected Impact / ROI |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | Stability | Turso failure silently falls back to ephemeral SQLite in CI; the run reports success | `JHUNT_REQUIRE_TURSO=1` in CI makes `get_storage()` raise; `PYTHONUNBUFFERED=1` restores the log (Top-3 #1) | No silent data loss; failures become red runs |
| **P0** | Data integrity | Id prefix change without migration means a re-alert flood and duplicate rows; JobsDB scrape capped at 50 from keyword 1 | One-time id migration (Turso + state file); per-keyword limits (Top-3 #2) | Restores coverage roughly 10×; continuity of dedupe and history |
| **P0** | Observability | All `print()` output lost in CI (`os._exit` before flush) | `PYTHONUNBUFFERED: "1"` in workflow env (one line) | You can see scrape counts and storage type |
| **P1** | Security | Unpinned `mcp-turso-cloud` holds an org-admin token | Pin an exact version; give agents a **read-only DB token** (`turso db tokens create jhunt-db --read-only`) instead of the platform token; drop the misleading alias and the root `package.json` | Removes a supply-chain path to deleting the database |
| **P1** | Data & LLM | Salary misparses from descriptions; 3 / 259 salaries in Turso | Parse descriptions only inside a window after `salary|เงินเดือน|ค่าตอบแทน`, detect period/currency per match, never use `N+` counts; run a one-off backfill over existing `salary` text | Benchmarks drawn from tens of real rows instead of 3 |
| **P1** | Data & LLM | Salary-per-skill uses one arbitrary `skill_name`; mixed currencies; n ≥ 1 | Rollup via `json_each` over all skill arrays, `currency = 'THB'`, `HAVING n >= 5`, show n (Top-3 #3) | First statistically defensible numbers on the page |
| **P1** | Data & LLM | Poison batch and oldest-first starvation in extraction | `ORDER BY created_at DESC`; add `extract_attempts` and skip after 3; split a failed batch in half once | Fresh jobs extracted daily; a bad record can't block the queue |
| **P1** | Data & LLM | `"500"` substring marks validation errors as transient | Match status codes structurally (`getattr(e, "code", None) in {429, 500, 502, 503, 504}`) | Stops 4× quota burn on bad output |
| **P1** | Stability | No global time budget (scrapers + Gemini can exceed 10 min) | Pass a monotonic deadline into scrapers and `_generate`; skip remaining work when under 60 s; cap urllib3 `Retry-After` (`respect_retry_after_header=False` plus own backoff) | Runs end with partial results instead of being killed |
| **P1** | Data | Blueprint logic defects (Phase 1.2) | Second "contradiction check" Gemini pass; prompt rule "verification must hold under any interleaving"; strip versions from stack entries; fix exporter `..` and `Step N:` duplication | Specs survive a staff-level read |
| **P2** | UX & perf | `force-dynamic` + 7 queries per view + duplicate mount fetch | ISR (`revalidate = 3600`) + CI-triggered `revalidatePath`; skip the matcher's first effect when skills equal the server's | ~0 Turso reads per view; faster TTFB |
| **P2** | UX & security | `/api/skill-gap` uncached full scans per request | Read the rollup table; memoize the job→skills map with a TTL; return 503 on internal errors instead of 200 with zeros | Removes the cost-amplification vector |
| **P2** | UX | Statistics shown without sample size; 1 % unlock floor | Display n on every metric; hide below n = 30; remove `Math.max(1, …)` | Honest numbers (antislop R-17) |
| **P2** | Storage | Schema drift, DDL every run, dead indexes | `schema_version` table + numbered migrations; drop `idx_jobs_posted_at`, `idx_jobs_source`, `idx_skills_experience`, `idx_skills_job_id`, and the `target_role` column/index | ~3 s faster startup; DDL matches reality |
| **P3** | Expansion | Dedupe state split between Actions cache and Turso | `alerted_at` column on `jobs`; delete `seen_jobs.json` and both cache steps | One store; CI becomes stateless |
| **P3** | Expansion | Skill gap's any-match definition | Must-have coverage ratio per job; "unlock" = crossing a 70 % threshold | Recommendations that differ from a frequency list |
| **P3** | Expansion | JobsDB still teaser-only, skewing cross-source skill counts | Fetch JobsDB job detail for new ids only, or weight counts per source | Comparable extraction depth across boards |

---

## Implementation guidelines: top 3 by ROI

### 1. Fail loudly instead of losing a day (P0, ~10 lines)

```diff
--- a/src/storage/__init__.py
 def get_storage(
     database_url: Optional[str] = None,
     auth_token: Optional[str] = None,
     db_path: Optional[Union[str, Path]] = None,
     force_sqlite: bool = False,
+    require_cloud: Optional[bool] = None,
 ) -> Union[TursoClient, DatabaseManager]:
+    if require_cloud is None:
+        # Same empty-means-unset semantics as main._bool_env
+        require_cloud = (os.getenv("JHUNT_REQUIRE_TURSO") or "").strip().lower() in ("1", "true", "yes", "on")
     if not force_sqlite:
         ...
+    if require_cloud:
+        raise RuntimeError(
+            "JHUNT_REQUIRE_TURSO is set but Turso is unavailable; refusing to write to ephemeral local SQLite."
+        )
     return DatabaseManager(db_path=db_path)
```
```diff
--- a/.github/workflows/scraper_cron.yml  (Run JHunt pipeline step)
         env:
+          JHUNT_REQUIRE_TURSO: "1"
+          PYTHONUNBUFFERED: "1"   # print() output survives os._exit
           TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}
```
Wrap the table batch in `TursoClient.init_schema` in the same `try` as the migrations, so a DDL hiccup doesn't disable the client. Add one test: `get_storage(require_cloud=True)` with no URL raises.

### 2. Restore coverage and id continuity (P0)

**Per-keyword limits.** In `jobsdb.py`, `blognone.py` and `jobthai.py`, count per keyword, not per scrape:
```diff
-                if len(jobs) >= limit:
+                if keyword_count >= limit:
                     break
 ...
-            if len(jobs) >= limit:
-                break
```
Then set the limits per adapter in `run_scrapers`: JobsDB 300 per keyword (no detail fetch), Blognone/JobThai 30 per keyword. Add `time.sleep(self.REQUEST_DELAY)` before each detail fetch, and skip detail fetches for ids already in storage.

**One-time id migration.** Run it before the next scheduled run, in one batch so it is atomic:
```sql
UPDATE skills_extracted SET job_id = 'jobsdb_' || job_id WHERE job_id GLOB '[0-9]*';
UPDATE jobs SET id = 'jobsdb_' || id, source = 'jobsdb' WHERE id GLOB '[0-9]*';
```
Then make the state file follow, in `StateManager._load`:
```diff
             if isinstance(seen, dict):
-                return {str(k): v for k, v in seen.items()}
+                # Ids gained a source prefix in 859240d; bare numeric ids are JobsDB.
+                return {(f"jobsdb_{k}" if str(k).isdigit() else str(k)): v for k, v in seen.items()}
```
Finally, `ORDER BY j.created_at DESC` in both `get_unprocessed_jobs` implementations, so the newest postings are extracted first.

If the 01:00 run lands first, the same SQL still works. Delete the duplicates it created before running it: `DELETE FROM jobs WHERE id GLOB 'jobsdb_*' AND substr(id, 8) IN (SELECT id FROM jobs WHERE id GLOB '[0-9]*');`, followed by the matching `skills_extracted` rows.

### 3. Pre-aggregate analytics once per day; serve it cheaply (P1 + P2)

Write a rollup at the end of the pipeline, then read only the rollup from the web.

```sql
-- Python, after extraction: replace the table contents in one batch
DELETE FROM skill_stats;
INSERT INTO skill_stats (skill, jobs, salary_n, salary_mid_thb)
WITH tags AS (
  SELECT s.job_id, je.value AS raw
  FROM skills_extracted s, json_each(s.must_have_skills) je
  WHERE s.experience_level != 'Non-Tech' AND json_valid(s.must_have_skills)
  UNION ALL SELECT s.job_id, je.value FROM skills_extracted s, json_each(s.frameworks) je
  WHERE s.experience_level != 'Non-Tech' AND json_valid(s.frameworks)
  -- … same for databases, cloud_infra, tools, nice_to_have_skills
),
job_skill AS (SELECT DISTINCT job_id, lower(trim(raw)) AS skill FROM tags WHERE trim(raw) != '')
SELECT js.skill,
       COUNT(*) AS jobs,
       SUM(j.currency = 'THB' AND j.min_salary IS NOT NULL AND j.max_salary IS NOT NULL) AS salary_n,
       CAST(AVG(CASE WHEN j.currency = 'THB' AND j.min_salary IS NOT NULL AND j.max_salary IS NOT NULL
                     THEN (j.min_salary + j.max_salary) / 2.0 END) AS INTEGER) AS salary_mid_thb
FROM job_skill js JOIN jobs j ON j.id = js.job_id
GROUP BY js.skill;
```
Web side:
- `/analytics` and `/` drop `force-dynamic` for `export const revalidate = 3600`.
- Add `POST /api/revalidate`, which checks a secret header and calls `revalidatePath("/analytics")` and `revalidatePath("/")`. The workflow's last step calls it with `curl -fsS -X POST -H "x-revalidate-token: ${{ secrets.REVALIDATE_TOKEN }}" "$SITE_URL/api/revalidate"`.
- Salary UI shows only rows with `salary_n >= 5`, always with n.
- `calculateSkillGap` loads the job→skills map from one narrow query (`job_id` plus arrays, no `SELECT *`, no blueprint markdown), memoized in module scope with a 10-minute TTL. Per-request work is then set operations in memory and zero row reads on a warm instance.

Expected effect: Turso reads per page view go from 7-10 queries to about 0 (cached render). The API stops scaling cost with traffic. Every published number carries its sample size.
