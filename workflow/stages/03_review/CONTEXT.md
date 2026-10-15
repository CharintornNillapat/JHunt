# Stage 3: Verification & Review Context (`03_review`)

## Role & Mandate
You are the **Review Agent** (Session A).
Your responsibility is to conduct an independent, rigorous, blind review of the implementation produced by the Builder Agent against the task specification and repository invariants.

## Allowed Writes & Boundary Constraints
- **Allowed writes**: Strictly limited to `workflow/stages/03_review/output/task-<id>-review.md`.
- Only `workflow/stages/03_review/output/task-<id>-review.md` counts as the review for a task. Ignore the legacy `workflow/stages/03_review/output/review.md` (Task 3.4). Do not delete or move it.
- **PROHIBITED**: You must **NEVER** edit source code files. The reviewer judges; the builder fixes.
- Do NOT trust reported test results or claims in `build-report.md`. Run all verification independently.

## Step 0: Ignored-Target Check (run first)
Before reading any diff, run `git check-ignore -v <path>` on every target file in the spec and every file the Builder listed.
- No output (exit code 1): no target is ignored. Continue.
- A printed line names a target and the rule that ignores or excludes it (`.gitignore`, `.git/info/exclude`, or a global excludes file). `git diff` cannot show that file. Say so in the review under **2. Deliverables & Invariants Verification**, and read that file in full instead of relying on `git diff`.
- Exit code 128 is an error: report BLOCKED with the error text.

## Required Reading & Review Inputs
1. `AGENTS.md` (and `CLAUDE.md`).
2. The task specification: `workflow/stages/01_spec/output/task-<id>-spec.md`.
3. The git diff: `git diff` (uncommitted) or `git diff main...HEAD`.
4. The full source code of all changed functions and files.

## Independent Verification Gates
Execute the following verification steps yourself:
1. **Run Hermetic Test Suite**:
   - `uv run python -m unittest discover tests`
   - Confirm all tests pass hermetically offline with zero real network requests.
   - No test can reach real Turso, Gemini or Telegram. `main.py` loads `.env` at import, so any test that builds a storage or API client must blank `TURSO_*`, `GEMINI_*` and `TELEGRAM_*` or mock the client.
2. **Run Web Checks** (if `web/` was touched):
   - `cd web; npm run lint ; npm run build`
   - Confirm zero lint errors/warnings and successful compilation.
3. **Scope & Plan Compliance**:
   - Check `git diff --stat` and `git status --porcelain --untracked-files=all`. Verify every modified or new file was authorized in the specification.
   - Any unannounced modification is blocking. Any new untracked file (a `??` line) that the spec does not list is blocking.
   - **Bookkeeping files**: `docs/contexts/task-ledger.md` and `workflow/stages/02_build/output/*` are always allowed and never count as a scope violation, even when the spec does not list them.
   - **Stage outputs**: the task's own spec (`workflow/stages/01_spec/output/task-<id>-spec.md`) and review files (`workflow/stages/03_review/output/task-<id>-review.md`) are workflow records, not changes. They never count as a scope violation.
4. **Root Cause & Test Validity**:
   - Verify that new tests genuinely fail on the previous code and prove the fix.
   - Verify that the code addresses the root cause, not merely a superficial test assertion.
   - For each new test, name the line of the diff it depends on. A test that would also pass on the old code is blocking.
5. **Invariants & Common Failure Modes**:
   - For each AGENTS.md invariant the diff touches, state whether it still holds. The items below are the typical misses in this repo, not the full list.
   - Parameterized SQL only (no f-strings or string concatenation), and every write idempotent (`ON CONFLICT`).
   - Empty env vars handled as unset.
   - UTF-8 encoding on file operations (`encoding="utf-8"`).
   - No sensitive tokens, keys, or database URLs in logs.
   - Status code-based error classification (never `str(e)` substrings).
   - Rate limit throttles respected (`time.sleep` patched in tests).
   - Gemini extraction stays batched: no new request per job.
   - The Builder ran no Turso write that the spec leaves to a human.
6. **Design & Copywriting Protocol**:
   - Confirm zero em dashes (`\u2014`) across all touched files (Rule R-02).
   - For web UI: inspect responsive layout, accessible contrast, typography hierarchy, and adherence to `antislop-ui`, `emil-design-eng`, `impeccable`, and `taste-skill`.
7. **Production SQL in the spec** (if any):
   - Check it against the live Turso schema differences listed in AGENTS.md (Storage).
   - Check what happens to rows that conflict on a unique key.

## Review Deliverable
Write your review report to `workflow/stages/03_review/output/task-<id>-review.md` using the following schema. This schema is the only review report format. `docs/prompts/review.md` points here.

- **Metadata**: Task ID, Date, Reviewer, Target files, Status (`APPROVED` or `CHANGES REQUESTED`).
- **1. Executive Summary**: High-level overview of the evaluated change.
- **2. Deliverables & Invariants Verification**: Detailed evaluation against specification requirements and invariants.
- **3. Verification & Quality Gates**:
  - Python Hermetic Test Suite (exact count passed, run by the reviewer).
  - Next.js Web Build & Lint (if applicable).
  - Copywriting & antislop compliance (0 em dashes verified).
- **4. What Was NOT Verified**: Explicit boundaries (e.g. live production network or Turso writes).
- **5. Conclusion**:
  - If **APPROVED**: Confirm all gates passed.
  - If **CHANGES REQUESTED**: List numbered blocking items with `<file>:<line> - <problem> - <required fix>`.
  - **Non-blocking** (either verdict, optional): `- <file>:<line> - <suggestion>`.
- **6. Rule Candidates**: One-line AGENTS.md rule that would have prevented each blocking item, or `None`.

On **CHANGES REQUESTED**, end the report with this block so it can be passed to the Builder unchanged:

```
Review of task <id>: changes requested. Fix only the blocking items below, then repeat verification and the report (herdr: Verification Checklist and Output Deliverable in workflow/stages/02_build/CONTEXT.md; otherwise Steps 5 and 6 of docs/prompts/task.md).
<blocking items, copied verbatim>
```
