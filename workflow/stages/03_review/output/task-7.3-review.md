# Review: Task 7.3: Workflow Rule Hygiene (docs only)

- **Task ID:** 7.3
- **Date:** 2026-10-15
- **Reviewer:** Claude Code (REVIEWER session)
- **Target files:** `AGENTS.md`, `docs/prompts/task.md`, `docs/prompts/review.md`, `workflow/stages/01_spec/CONTEXT.md`, `workflow/stages/02_build/CONTEXT.md`, `workflow/stages/03_review/CONTEXT.md`, `docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/build-report.md`
- **Status:** APPROVED

```
Task: 7.3
Verdict: APPROVED
Tests: 208 passed (run by reviewer)
Blocking: none
```

---

## 1. Executive Summary
This is a docs-only change. Every item in the spec is present with the normative wording:
- verdicts unified
- herdr spec location and the `SPEC DONE` stop point
- bookkeeping and legacy review-file rules in both stage contexts
- conditional AGENTS.md ban
- Builder Execution Strategy
- AGENTS.md map line and ledger date fixed
- all em dashes removed

No source, test, web or workflow file changed.

---

## 2. Deliverables & Invariants Verification

**Important context:** the three `workflow/stages/*/CONTEXT.md` files are excluded by `.git/info/exclude:8`. `git diff` does not show them, so I read them in full and compared them with their pre-task contents, which I had read earlier in this session.

| Spec item | Evidence | Result |
|---|---|---|
| 1. Execution Strategy | `02_build/CONTEXT.md:25-28`: all three rules, placed after Required Reading | PASS |
| 2.1 Verdicts | `review.md:38,51,54`; `03_review/CONTEXT.md:48,58` | PASS |
| 2.2 herdr note | `task.md:3`; `review.md:10` | PASS |
| 2.2 Stop point | `01_spec/CONTEXT.md:44`: "Stop and report `SPEC DONE`..." | PASS |
| 2.3 Bookkeeping | `02_build/CONTEXT.md:12,53`; `03_review/CONTEXT.md:30` | PASS |
| 2.4 Legacy review file | `02_build/CONTEXT.md:23`; `03_review/CONTEXT.md:9`. `03_review/output/review.md` still exists. | PASS |
| 2.5 AGENTS.md ban | `02_build/CONTEXT.md:15-16` | PASS |
| 3. AGENTS.md map | `AGENTS.md:81`: real path, Phases 0 to 2, points to the ledger | PASS |
| 3. Path fix (reviewer addition) | `task.md:10`; `01_spec/CONTEXT.md:15` | PASS |
| 3. Ledger | `task-ledger.md:4` (`2026-10-15`), `:146` (7.3 entry). The old Phase 7 section is untouched. | PASS |
| 4. Em dashes | `AGENTS.md:1` is now `# AGENTS.md: JHunt`; `review.md:42,45` use hyphens | PASS |

**AGENTS.md permission:** exactly two lines changed (1 and 81). There is no agy-specific text. Holds.

**CLAUDE.md:** `git diff --quiet -- CLAUDE.md` reports no change. Holds.

**Scope:** `git diff --stat` lists `AGENTS.md`, `docs/contexts/task-ledger.md`, `docs/prompts/review.md`, `docs/prompts/task.md` and `build-report.md`, all on the allowed list. Nothing changed under `src/`, `web/`, `tests/` or `.github/`.

**Invariants:** no code is touched, so no code invariant applies.

---

## 3. Verification & Quality Gates (run by reviewer)
- **Python suite:** `uv run python -m unittest discover tests`: **Ran 208 tests, OK**. The count is unchanged, as required.
- **Web:** not touched, so lint and build are not required.
- **R-02, whole files:** 0 em dashes in all 8 allowed files.
- **Verdict words:** case-sensitive `\bPASS\b|\bFAIL\b|REJECTED` over the 8 files finds 2 hits, both in `build-report.md`, lines 20 and 70. Both describe the change itself (line 20: "from APPROVED / REJECTED to ..."; line 70: the scan pattern). Neither states a verdict, so this is acceptable under spec Verification step 4.

---

## 4. What Was NOT Verified
- Whether agy, herdr and Claude Code follow the new rules at runtime. That is only observable on the next orchestrated task.
- A git-level diff of the three CONTEXT.md files. They are git-excluded, so I verified them by full read only.

---

## 5. Conclusion
**APPROVED.** All gates passed.

Non-blocking:
- **`.git/info/exclude:8` (worth acting on).** `workflow/stages/*/CONTEXT.md` is excluded locally. The three edited stage rule files, the core of this task, will not be in the commit and have no version history or backup. If they are meant to be shared or protected, remove the exclude line and commit them. That is a separate decision; this spec missed it.
- `workflow/stages/02_build/CONTEXT.md:11-12`: the ledger is now listed twice under Allowed writes (line 11 "Task ledger updates" and line 12 "Bookkeeping files"). Line 11 could be dropped.

Rule candidates:
- AGENTS.md or the 03_review context: "Before reviewing, run `git check-ignore` on every target file; a git-excluded target must be verified by a full read, and the review must say so."
