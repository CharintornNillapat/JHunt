# Stage 2: Implementation & Build Context (`02_build`)

## Role & Mandate
You are the **Builder Agent** (Session B).
Your responsibility is to implement the exact specification designed in Stage 1, adhering strictly to repository invariants, quality standards, and test-driven validation.

## Allowed Writes & Boundary Constraints
- **Allowed writes**:
  - Source code files explicitly listed in the task specification (`src/`, `web/`, `tests/`, etc.).
  - Output report: `workflow/stages/02_build/output/build-report.md`.
  - **Bookkeeping files**: `docs/contexts/task-ledger.md` and `workflow/stages/02_build/output/*` are always allowed and never count as a scope violation, even when the spec does not list them.
- **PROHIBITED**:
  - Do NOT touch files outside the specification scope (no opportunistic refactoring).
  - Do NOT create `GEMINI.md` or modify `CLAUDE.md`, `.gitignore`, `.mcp.json`, or `web/package.json`.
  - Do NOT modify `AGENTS.md` unless the task spec explicitly authorizes it.
  - Do NOT execute any command listed in `AGENTS.md` "Stop and ask first" (no live Turso writes, no live Telegram messages, no real Gemini pipeline runs).

## Required Reading & Handoff Protocol
1. Read `AGENTS.md` (and `CLAUDE.md`).
2. Read the spec: `workflow/stages/01_spec/output/task-<id>-spec.md`.
3. If a review report exists (`workflow/stages/03_review/output/task-<id>-review.md`) with blocking items, fix ONLY the listed items.
   - Only `workflow/stages/03_review/output/task-<id>-review.md` counts as the review for a task. Ignore the legacy `workflow/stages/03_review/output/review.md` (Task 3.4). Do not delete or move it.

## Execution Strategy
1. **Full-Context Read**: Before editing, read the whole spec, every target file, and the test file for each target file, in full. Do not work from snippets or search hits.
2. **Sub-Agent Discipline**: Sub-agents may only read and explore. They never edit files or run commands that write. The main agent makes every edit, then runs verification once, sequentially, after all edits are done.
3. **Deep Verification on Fix**: On a fix order, fix only the blocking items in `workflow/stages/03_review/output/task-<id>-review.md`. Then rerun the full test suite and recheck every blocking item from all earlier review rounds of the same task, not only the newest round.

## Implementation Guidelines
1. **Test-First Discipline**:
   - Add new unit tests first in `tests/test_*.py`.
   - Run tests to confirm they fail as expected on the unpatched codebase.
2. **Minimal & Precise Code Edits**:
   - Write the smallest, cleanest implementation that satisfies the tests and spec.
   - Adhere to repository invariants:
     - Job IDs maintain prefix (`jobsdb_`, `blognone_`, `jobthai_`).
     - Treat empty string env vars as unset (`_csv_env` / `_bool_env`).
     - All SQL queries parameterized and idempotent (`ON CONFLICT`).
     - LLM extraction fails open without interrupting batch processing.
     - Files opened with explicit UTF-8 encoding: `open(..., encoding="utf-8")`.
     - Fast hermetic tests: mock network calls, blank credentials, patch `time.sleep`.
3. **Frontend & Design Standards** (for `web/`):
   - Comply with `antislop-ui`, `emil-design-eng`, `impeccable`, and `taste-skill`.
   - Maintain typography scale, accessible contrast, and clean layout without generic AI slop.
4. **Copywriting Hygiene (R-02)**:
   - Ensure zero em dashes (`\u2014`) in all touched files.

## Verification Checklist
Before declaring the build complete, execute:
1. Python unit tests: `uv run python -m unittest discover tests` (all tests must pass hermetically).
2. If `web/` was modified: `cd web; npm run lint ; npm run build` (zero errors or warnings).
3. Git hygiene: `git diff --stat` must show only planned files plus the bookkeeping files above.
4. Em dash scan: verify zero em dashes across all touched files.

## Output Deliverable
Write `workflow/stages/02_build/output/build-report.md` detailing:
- Task ID and BUILT status.
- File-by-file summary of deliverables and changes.
- Exact test verification results and pass counts.
- Explicit list of what was NOT verified (e.g. live network or production Turso writes).
