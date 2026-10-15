# Build Report: Task 7.3.1 - Review Format Merge and Ignored-Target Check (docs only)

## Summary
- **Task ID**: 7.3.1
- **Status**: BUILT
- **Target**: Remove duplicate ledger line from 02_build CONTEXT, add ignored-target check (Step 0) to 03_review CONTEXT, and make 03_review CONTEXT the single canonical review format with all checks, typical misses, non-blocking items, rule candidates, and paste-ready fix block merged in from docs/prompts/review.md; update task-ledger.md. Zero em dashes across touched files.

---

## 1. Deliverables & Modified Files

### 1.1 `workflow/stages/02_build/CONTEXT.md`
- Removed redundant line 11 (`- Task ledger updates: \`docs/contexts/task-ledger.md\`.`) under Allowed Writes, as line 12 (`Bookkeeping files`) already authorizes `docs/contexts/task-ledger.md`.

### 1.2 `workflow/stages/03_review/CONTEXT.md`
- **Step 0: Ignored-Target Check**: Added section before Required Reading running `git check-ignore -v <path>` on all targets and builder-listed files to catch ignored/excluded files invisible to `git diff`.
- **Gate 1 (Hermetic Test Suite)**: Added bullet on environment isolation and client mocking (`TURSO_*`, `GEMINI_*`, `TELEGRAM_*` blanked or mocked) due to `main.py` loading `.env` at import.
- **Gate 4 (Root Cause & Test Validity)**: Added requirement for each new test to name the line of the diff it depends on, noting that tests passing on old code are blocking.
- **Gate 5 (Invariants & Common Failure Modes)**:
  - Added requirement stating whether each touched AGENTS.md invariant still holds.
  - Updated SQL bullet to require idempotent writes (`ON CONFLICT`).
  - Added checks for batched Gemini extraction (no per-job requests) and verification that no human-run Turso write was executed.
- **Gate 7 (Production SQL in the spec)**: Added gate checking production SQL against live Turso schema differences and unique-key conflict handling.
- **Review Deliverable Schema**:
  - Pinned schema as the only review report format, noted by `docs/prompts/review.md`.
  - Added "(run by the reviewer)" to the Python Hermetic Test Suite item.
  - Added non-blocking suggestions list (`- <file>:<line> - <suggestion>`) to section 5.
  - Added section 6 (`Rule Candidates`).
  - Added standardized paste-ready fix block on `CHANGES REQUESTED` covering both herdr and standalone task flows.

### 1.3 `docs/prompts/review.md`
- Replaced `## Output` section with a direct pointer to `workflow/stages/03_review/CONTEXT.md` (`## Review Deliverable`) as the single review format, supporting both herdr report file output and interactive review replies.

### 1.4 `docs/contexts/task-ledger.md`
- Appended entry for Task 7.3.1 under Phase 7.

### 1.5 `workflow/stages/02_build/output/build-report.md`
- Generated this build report for Task 7.3.1.

---

## 2. Verification & Quality Gates

### 2.1 Python Hermetic Test Suite
- Command: `uv run python -m unittest discover tests`
- Result: 208 passed (all tests pass hermetically offline with zero network requests).

### 2.2 Scope & Git Status Check
- Modified files strictly match the allowed target paths:
  - `workflow/stages/02_build/CONTEXT.md`
  - `workflow/stages/03_review/CONTEXT.md`
  - `docs/prompts/review.md`
  - `docs/contexts/task-ledger.md`
  - `workflow/stages/02_build/output/build-report.md`
- Excluded files (`CLAUDE.md`, `AGENTS.md`, `docs/prompts/task.md`, `workflow/stages/01_spec/CONTEXT.md`) are untouched.

### 2.3 Whole-File Em Dash Scan (Rule R-02)
- Zero em dashes (U+2014) verified across all touched files.

### 2.4 Format and Content Checks
- `docs/prompts/review.md`: legacy format blocks removed; points to `workflow/stages/03_review/CONTEXT.md`.
- `workflow/stages/02_build/CONTEXT.md`: exactly one `task-ledger.md` reference in Allowed Writes.
- `workflow/stages/03_review/CONTEXT.md`: contains Step 0 `git check-ignore -v`, all merged checks, `Rule Candidates`, `Non-blocking`, and the paste-ready fix block.
- Verdict words: only `APPROVED` and `CHANGES REQUESTED` present; no verdict lines with `PASS`, `FAIL`, or `REJECTED`.

---

## 3. What Was NOT Verified
- Runtime compliance by external review agents (Claude Code / herdr) during upcoming review cycles.
