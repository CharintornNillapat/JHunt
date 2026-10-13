# Build Report: Task 1.5 — Blueprint Specification & Exporter Polish

**Task:** 1.5  
**Spec Reference:** `workflow/stages/01_spec/output/task-1.5-spec.md`  
**Test Suite:** 191 passed (`uv run python -m unittest discover tests`), `npm run lint` & `npm run build` passed.

---

## Changes Implemented

1. **`src/generator/ideation_engine.py` (Prompt Guardrails & Defensive Normalization)**:
   - Expanded `IDEATION_SYSTEM_INSTRUCTION` with explicit architecture constraints:
     - **Contracts**: Webhook retry responses must use HTTP 5xx (e.g. 503) or 409 Conflict, and NEVER 422 Unprocessable Entity.
     - **Transactional State**: Failure status updates (e.g., dead-letter row or failed state) must commit in an autonomous or independent transaction before or outside the main rollback.
     - **Concurrency & Invariants**: Verification assertions must hold true under any request interleaving. In-test concurrency must use `asyncio.gather` with `httpx.AsyncClient` or thread pools, forbidding `pytest-xdist`.
     - **Tech Stack**: Required `target_tech_stack` to list bare technology names without version numbers.
   - Programmatically sanitized `spec.target_tech_stack` in `IdeationEngine.generate_project_spec()` to strip trailing version numbers (`re.sub(r"\s+v?\d+(?:\.\d+)*$", "", t).strip()`).

2. **`src/generator/markdown_exporter.py` (Deduplication & Period Stripping)**:
   - Added `_clean_step(step: str)` helper to strip duplicated leading step markers (such as `"Step 1:"`, `"1."`, or `"1. Step 1:"`) from `walking_skeleton` entries.
   - Applied `.rstrip(".")` on `fm.failure` in `render_spec_markdown()` before appending a single terminal period, preventing double periods (`..**`).

3. **`web/src/lib/turso.ts` (Versioned Skill Canonicalization)**:
   - Exported `canonicalizeSkill`.
   - Added regex and prefix matching for versioned PostgreSQL strings (`"PostgreSQL 16"`, `"Postgres 16"`, etc.).
   - Added regex and prefix matching for versioned Python strings (`"Python 3.12"`, `"Python 3"`, etc.).
   - Added fallback trailing version stripping on generic skill strings (`replace(/\s+v?\d+(?:\.\d+)*$/i, "")`) before casing normalization.

---

## Tests Added & Verified

- **`tests/test_generator.py`**:
  - `test_render_spec_strips_double_periods_in_failure_modes`: Verifies trailing periods in failure mode strings are stripped to avoid double periods (`..**`).
  - `test_render_spec_deduplicates_step_prefixes_in_walking_skeleton`: Verifies leading step markers (e.g. `"Step 1:"`, `"2."`, `"3. Step 3:"`) are deduplicated.
  - `test_ideation_system_instruction_contains_architecture_guardrails`: Verifies `IDEATION_SYSTEM_INSTRUCTION` mandates HTTP status codes (5xx/409, never 422), autonomous transactions for failure state, `asyncio.gather` concurrency rules, and interleaving-safe verification.
  - `test_generate_project_spec_strips_stack_versions`: Verifies `generate_project_spec()` strips version suffixes from `target_tech_stack` (e.g. `["Python 3.12", "PostgreSQL 16", "FastAPI v0.110.0", "Docker"]` -> `["Python", "PostgreSQL", "FastAPI", "Docker"]`).

---

## Verification Status

- **Hermetic Unit Tests**: 191 passed, 0 failures, 0 errors (`uv run python -m unittest discover tests`).
- **Web Verification**:
  - `npm run lint` passed (clean exit 0).
  - `npm run build` passed (Turbopack production build compiled successfully in 9.5s, all SSG/dynamic routes generated cleanly).
- **Production Touch Points**: None (zero writes to Turso, zero Telegram calls, zero Gemini network calls).
