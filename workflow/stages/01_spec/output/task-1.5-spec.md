# Plan: Task 1.5 — Blueprint Specification & Exporter Polish

**Date:** 2026-10-13  
**Task ID:** 1.5  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 1.5), `docs/audits/2026-10-12-architecture-reflection.md` (Section 1.2, Section 2.4, Section 3.1 P1 row), `AGENTS.md` (Definitions & Invariants)

---

## Goal
Harden portfolio project blueprint generation by injecting anti-contradiction prompt constraints into `ideation_engine.py`, stripping double periods and duplicate step numbering in `markdown_exporter.py`, and canonicalizing versioned technology stacks in `web/src/lib/turso.ts`.

---

## Disagreements / Alignment Notes
1. **Prompt Constraints vs. Second LLM Pass**:  
   Section 1.2 of the architecture reflection suggests an optional second Gemini "contradiction check" call. However, Task 1.5 in `remediation-plan.md` specifies hardening the single-pass prompt constraints. Because Gemini free-tier daily requests (RPD ~20 req/day) are the binding constraint on CI, we strictly adhere to the remediation plan's approach: strengthen `IDEATION_SYSTEM_INSTRUCTION` and add defensive programmatic sanitization rather than spending a second daily LLM call.
2. **Version Stripping at Ingestion & Web Boundary**:  
   Stack entries like `"Python 3.12"` or `"PostgreSQL 16"` cause blueprint matches to fail in `web/src/lib/turso.ts`. We address this in two layers:
   - Instruct Gemini to output bare technology names without version numbers, plus programmatically strip version suffixes in `IdeationEngine.generate_project_spec()`.
   - Update `canonicalizeSkill()` in `web/src/lib/turso.ts` to recognize versioned prefixes (`PostgreSQL 16`, `Python 3.12`) and strip trailing version numbers (`Redis 7` -> `Redis`).

---

## Current Behavior (Evidence)
1. **Double Periods in Rendered Markdown**:  
   In `src/generator/markdown_exporter.py:46`:
   ```python
   failures_md = "\n".join(f"- **{fm.failure}.** {fm.recovery}" for fm in spec.failure_modes)
   ```
   If `fm.failure` ends with a period (common in LLM output, e.g. `"The provider delivers the same event twice."`), the exporter appends a second period, generating `- **...event twice...** recovery`.
2. **Duplicated Step Numbering in Walking Skeleton**:  
   In `src/generator/markdown_exporter.py:45`:
   ```python
   skeleton_md = "\n".join(f"{i}. {step}" for i, step in enumerate(spec.walking_skeleton, 1))
   ```
   When the LLM prefixes steps with `"Step 1:"` or `"1."`, this formats as `"1. Step 1: POST /webhooks..."` or `"1. 1. POST..."`.
3. **Missing Prompt Constraints on Concurrency, Webhook Status Codes, and Transactions**:  
   In `src/generator/ideation_engine.py:19-41`, `IDEATION_SYSTEM_INSTRUCTION` does not specify:
   - Webhook retry status codes must be 5xx / 409, never 422.
   - Status updates must commit in an autonomous transaction before main rollback.
   - In-test concurrency must use `asyncio.gather` with `httpx.AsyncClient` or thread pools, never `pytest-xdist`.
   - Verification checks must hold under any request interleaving.
   - Tech stack entries must omit version numbers.
4. **Versioned Tech Strings Ignored by `canonicalizeSkill`**:  
   In `web/src/lib/turso.ts:324-351`:
   - `"PostgreSQL 16"` or `"Postgres 16"` does not match `"postgres"` or `"postgresql"`, failing to map to `"PostgreSQL"`.
   - Trailing version patterns (e.g. `Redis 7.2`) are not normalized, breaking skill-gap matching against user skills.

---

## Changes

### 1. `src/generator/ideation_engine.py`
- Expand `IDEATION_SYSTEM_INSTRUCTION`:
  - **Contracts**: Explicitly specify that webhook retry responses must be HTTP 5xx (e.g., 503) or 409 Conflict, and NEVER 422 Unprocessable Entity (senders treat 4xx as terminal client errors and drop the event).
  - **Transactional State**: Specify that on failures, status updates (e.g. recording a `FAILED` state or dead-letter row) must be committed in an autonomous/independent transaction before or outside the main rollback.
  - **Concurrency & Invariants**: Mandate that verification checks must hold true under any request interleaving (no flaky assumptions about scheduling order). For in-test concurrency, specify `asyncio.gather` with `httpx.AsyncClient` or a thread pool; forbid `pytest-xdist` for in-test concurrency assertions.
  - **Tech Stack**: Require `target_tech_stack` to list technology names without version numbers (e.g. `'Python'`, `'PostgreSQL'`, not `'Python 3.12'`).
- Update `generate_project_spec()`:
  - Add defensive programmatic normalization on `spec.target_tech_stack` to strip trailing version numbers (e.g. `re.sub(r"\s+v?\d+(?:\.\d+)*$", "", t).strip()`).

### 2. `src/generator/markdown_exporter.py`
- In `render_spec_markdown()`:
  - Strip trailing periods from `fm.failure` using `.rstrip(".")` before appending `.`:
    ```python
    failures_md = "\n".join(f"- **{fm.failure.rstrip('.')}.** {fm.recovery}" for fm in spec.failure_modes)
    ```
  - Clean leading numbers and step markers from `step` in `walking_skeleton`:
    ```python
    def _clean_step(step: str) -> str:
        return re.sub(r"^(?:(?:step\s*\d+[:\.\s-]*)|(?:\d+[\.\)]\s*))+", "", step, flags=re.IGNORECASE).strip()

    skeleton_md = "\n".join(f"{i}. {_clean_step(step)}" for i, step in enumerate(spec.walking_skeleton, 1))
    ```

### 3. `web/src/lib/turso.ts`
- Update `canonicalizeSkill(raw: string)`:
  - Add support for versioned PostgreSQL strings:
    `if (lower === "postgres" || lower === "postgresql" || lower.startsWith("postgres ") || lower.startsWith("postgresql ") || /^postgresql?\s*\d+/i.test(lower)) return { canonical: "PostgreSQL", lower: "postgresql" };`
  - Add support for versioned Python strings:
    `if (lower === "py" || lower === "python" || lower === "python3" || lower.startsWith("python ") || /^python\s*\d+/i.test(lower)) return { canonical: "Python", lower: "python" };`
  - Strip trailing version patterns across any generic skill before capitalization:
    `const stripped = trimmed.replace(/\s+v?\d+(?:\.\d+)*$/i, "").trim();`
- Export `canonicalizeSkill` so it can be imported and tested if needed.

---

## Tests to Add / Update

### In `tests/test_generator.py`:
1. `test_render_spec_strips_double_periods_in_failure_modes`:
   - **Asserts**: Verifies that when `fm.failure` ends with a period (e.g. `"The provider delivers the same event twice."`), the rendered markdown contains `- **The provider delivers the same event twice.**` and NOT `..**`.
   - **Why it fails today**: `render_spec_markdown()` blindly adds `.` resulting in `..**`.
2. `test_render_spec_deduplicates_step_prefixes_in_walking_skeleton`:
   - **Asserts**: Verifies that steps starting with `"Step 1: Deploy..."`, `"1. Deploy..."`, or `"1. Step 1: Deploy..."` are cleanly rendered as `1. Deploy...` without repeated step numbering.
   - **Why it fails today**: `render_spec_markdown()` formats as `1. Step 1: Deploy...` or `1. 1. Deploy...`.
3. `test_ideation_system_instruction_contains_architecture_guardrails`:
   - **Asserts**: Verifies `IDEATION_SYSTEM_INSTRUCTION` explicitly mentions webhook retry codes (5xx / 409, never 422), autonomous transactions for status updates, `asyncio.gather` for concurrency (forbidding `pytest-xdist`), and interleaving-safe verification.
   - **Why it fails today**: `IDEATION_SYSTEM_INSTRUCTION` does not currently contain these specific constraints.
4. `test_generate_project_spec_strips_stack_versions`:
   - **Asserts**: Verifies that when Gemini returns `["Python 3.12", "PostgreSQL 16", "FastAPI"]`, `generate_project_spec()` normalizes the stack to `["Python", "PostgreSQL", "FastAPI"]`.
   - **Why it fails today**: Versions in `target_tech_stack` are passed through untouched.

---

## Out of Scope
- Adding a second daily Gemini LLM call for contradiction checks (preserves free-tier RPD quota).
- Phase 2: `skill_stats` pre-aggregated rollup table (`Task 2.1`).
- Phase 2: Next.js `/analytics` ISR revalidation endpoints (`Task 2.2`).

---

## Production Touch Points
- None. (Zero Turso DDL/DML, zero Telegram messages, zero Gemini quota spend during unit testing).
