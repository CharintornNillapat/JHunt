# Build Report: Task 7.3 - Workflow Rule Hygiene (docs only)

## Summary
- **Task ID**: 7.3
- **Status**: BUILT
- **Target**: Align workflow rule files and context definitions with the herdr orchestrator on verdicts, spec location, stop points, bookkeeping files, review file selection, and Builder execution strategy; fix stale path references; remove all em dashes across touched files.

---

## 1. Deliverables & Modified Files

### 1.1 `workflow/stages/02_build/CONTEXT.md`
- **Execution Strategy**: Added `## Execution Strategy` covering full-context reading, sub-agent read-only discipline, and deep re-verification across review rounds on fix orders.
- **Bookkeeping Allowance**: Added explicit clause under Allowed Writes establishing `docs/contexts/task-ledger.md` and `workflow/stages/02_build/output/*` as always allowed without counting as scope violations.
- **Review File Pinning**: Added rule in Required Reading specifying that only `task-<id>-review.md` counts as a review and the legacy `review.md` must be ignored.
- **AGENTS.md Exception**: Updated prohibited rule to permit `AGENTS.md` modifications when explicitly authorized by the task specification.
- **Git Hygiene**: Updated verification checklist item 3 to allow bookkeeping files.

### 1.2 `workflow/stages/03_review/CONTEXT.md`
- **Verdicts**: Updated Status and conclusion options from `APPROVED` / `REJECTED` to `APPROVED` / `CHANGES REQUESTED`.
- **Review File Pinning**: Added rule under Allowed Writes stating only `task-<id>-review.md` is valid and legacy `review.md` is ignored.
- **Bookkeeping Allowance**: Added bookkeeping exception to Gate 3 (`Scope & Plan Compliance`).

### 1.3 `workflow/stages/01_spec/CONTEXT.md`
- **Stop & Handoff**: Replaced human confirmation text with `SPEC DONE` report to orchestrator.
- **Stale Path**: Fixed bare `2026-10-12-remediation-plan.md` reference to `docs/audits/2026-10-12-remediation-plan.md`.

### 1.4 `docs/prompts/task.md`
- **Orchestration Callout**: Added blockquote under title clarifying that under herdr orchestration, the spec at `workflow/stages/01_spec/output/task-<id>-spec.md` replaces `docs/plans/` and the human gate is orchestrator pause.
- **Stale Path**: Fixed bare `2026-10-12-remediation-plan.md` reference to `docs/audits/2026-10-12-remediation-plan.md`.

### 1.5 `docs/prompts/review.md`
- **Spec Location**: Added herdr orchestration spec path note to Read item 2.
- **Verdicts**: Updated verdict schema to `APPROVED | CHANGES REQUESTED`, and updated fail block to trigger on `CHANGES REQUESTED`.
- **Em Dash Removal**: Replaced em dashes in blocking and non-blocking format templates with hyphens.

### 1.6 `AGENTS.md`
- **Em Dash Removal**: Replaced title em dash on line 1 (`# AGENTS.md: JHunt`).
- **Stale Map Entry**: Updated line 81 to `docs/audits/2026-10-12-remediation-plan.md` noting live status in `docs/contexts/task-ledger.md`.

### 1.7 `docs/contexts/task-ledger.md`
- **Date**: Updated `Last Updated` header to `2026-10-15`.
- **Phase 7 Entry**: Appended Task 7.3 completion entry.

---

## 2. Verification & Quality Gates

### 2.1 Python Hermetic Test Suite
- Command: `uv run python -m unittest discover tests`
- Result: **208 passed in 11.961s** (OK, 0 failures, 0 errors, completely hermetic).

### 2.2 Scope & Git Diff Check
- `git diff --stat`: Modified only allowed files (`AGENTS.md`, `docs/contexts/task-ledger.md`, `docs/prompts/review.md`, `docs/prompts/task.md`).
- Excluded context files on disk (`01_spec/CONTEXT.md`, `02_build/CONTEXT.md`, `03_review/CONTEXT.md`) verified updated.
- `CLAUDE.md`: Verified untouched (`git diff --quiet -- CLAUDE.md`).

### 2.3 Whole-File Em Dash Scan (Rule R-02)
- Programmatic scan across all 8 target files:
  - `AGENTS.md`: 0
  - `docs/prompts/task.md`: 0
  - `docs/prompts/review.md`: 0
  - `workflow/stages/01_spec/CONTEXT.md`: 0
  - `workflow/stages/02_build/CONTEXT.md`: 0
  - `workflow/stages/03_review/CONTEXT.md`: 0
  - `docs/contexts/task-ledger.md`: 0
  - `workflow/stages/02_build/output/build-report.md`: 0

### 2.4 Verdict Keyword Scan
- Scanned for `\bPASS\b`, `\bFAIL\b`, and `REJECTED`: 0 matches in verdict contexts across all target files.

---

## 3. What Was NOT Verified
- Runtime compliance by external agents (agy / herdr / Claude Code) during upcoming orchestration cycles.
