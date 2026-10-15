# Build Report: Task 7.3.2 - Scope Check Catches New Files (docs only)

## Summary
- **Task ID**: 7.3.2
- **Status**: BUILT
- **Target**: Update scope checks across 03_review CONTEXT, 02_build CONTEXT, and task.md Step 5 to execute `git status --porcelain --untracked-files=all` alongside `git diff --stat`, ensuring unlisted new untracked files are blocking while exempting bookkeeping files and the task's own stage output spec and review files; reword Gate 5 human-run Turso write check; update task-ledger.md. Zero em dashes across touched files.

---

## 1. Deliverables & Modified Files

### 1.1 `workflow/stages/03_review/CONTEXT.md`
- **Gate 3 (Scope & Plan Compliance)**:
  - Added `git status --porcelain --untracked-files=all` alongside `git diff --stat` to inspect modified and new files.
  - Specified that any new untracked file (`??` line) not listed in the spec is blocking.
  - Added explicit exemption for stage outputs (`workflow/stages/01_spec/output/task-<id>-spec.md` and `workflow/stages/03_review/output/task-<id>-review.md`) as workflow records that never count as scope violations.
- **Gate 5 (Invariants & Common Failure Modes)**:
  - Reworded bullet to: `The Builder ran no Turso write that the spec leaves to a human.`

### 1.2 `workflow/stages/02_build/CONTEXT.md`
- **Verification Checklist (Item 3 Git Hygiene)**:
  - Added requirement that `git status --porcelain --untracked-files=all` must show no new untracked file (`??` line) other than planned files, bookkeeping files, and the task's own spec and review files, with any other new file being blocking.

### 1.3 `docs/prompts/task.md`
- **Step 5 (Verify)**:
  - Updated scope item to run `git status --porcelain --untracked-files=all` alongside `git diff --stat`.
  - Added rule that unlisted new untracked files (`??` lines) are blocking, with plan/spec files and bookkeeping files exempted.

### 1.4 `docs/contexts/task-ledger.md`
- Appended entry for Task 7.3.2 under Phase 7.

### 1.5 `workflow/stages/02_build/output/build-report.md`
- Generated this build report for Task 7.3.2.

---

## 2. Verification & Quality Gates

### 2.1 Python Hermetic Test Suite
- Command: `uv run python -m unittest discover tests`
- Result: 208 passed (all tests pass hermetically offline with zero network requests).

### 2.2 Scope & Git Status Check
- Modified files strictly match the allowed target paths:
  - `workflow/stages/03_review/CONTEXT.md`
  - `workflow/stages/02_build/CONTEXT.md`
  - `docs/prompts/task.md`
  - `docs/contexts/task-ledger.md`
  - `workflow/stages/02_build/output/build-report.md`
- `git status --porcelain --untracked-files=all` shows only modified allowed files plus the untracked spec file (`?? workflow/stages/01_spec/output/task-7.3.2-spec.md`).
- Excluded files (`CLAUDE.md`, `AGENTS.md`, `docs/prompts/review.md`, `workflow/stages/01_spec/CONTEXT.md`) are untouched.

### 2.3 Whole-File Em Dash Scan (Rule R-02)
- Zero em dashes (U+2014) verified across all touched files.

### 2.4 Command and Check Presence
- `git status --porcelain --untracked-files=all` confirmed present in `03_review/CONTEXT.md`, `02_build/CONTEXT.md`, and `docs/prompts/task.md`.
- Every `git diff --stat` mention in those files appears on a line together with the new command.
- Gate 5 contains `The Builder ran no Turso write that the spec leaves to a human.` and no longer contains `that the spec says a human runs`.

---

## 3. What Was NOT Verified
- Runtime compliance by external review agents (Claude Code / herdr) during upcoming review cycles.
