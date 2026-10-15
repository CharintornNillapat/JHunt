# Review: Task 7.3.2: Scope Check Catches New Files

- **Task ID:** 7.3.2
- **Date:** 2026-10-15
- **Reviewer:** Claude Code (REVIEWER)
- **Target files:** `workflow/stages/03_review/CONTEXT.md`, `workflow/stages/02_build/CONTEXT.md`, `docs/prompts/task.md`, `docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/build-report.md`
- **Status:** APPROVED

## 1. Executive Summary
Docs-only change, uncommitted on `main` at `fd6dd2b`. All three scope checks now run `git status --porcelain --untracked-files=all` next to `git diff --stat`, and an unlisted new untracked file now blocks. The task's own stage outputs and the bookkeeping files are exempt. Gate 5's human-run Turso write line is reworded. The diff matches the spec's normative wording word for word.

## 2. Deliverables & Invariants Verification

**Step 0 (ignored targets):** `git check-ignore -v` on all five target files printed nothing and exited 1. No target is ignored or excluded.

| Spec part | Evidence | Result |
|---|---|---|
| 1.1 Gate 3: new command, `??` rule, stage-output exemption; Bookkeeping line kept | `03_review/CONTEXT.md:35-38` | Done |
| 1.2 Builder git hygiene | `02_build/CONTEXT.md:52` | Done |
| 1.3 task.md Step 5 | `docs/prompts/task.md:42` | Done |
| 2. Gate 5 reworded | `03_review/CONTEXT.md:52` reads `The Builder ran no Turso write that the spec leaves to a human.`; the old text is gone | Done |
| 3. Ledger entry after 7.3.1; build report rewritten | `task-ledger.md` +1 line in Phase 7; `build-report.md` is a full rewrite for 7.3.2 | Done |

**Consistency:** the new command appears exactly once in each of the three files. Every `git diff --stat` mention in those files sits on a line together with the new command (`grep -F 'git diff --stat' | grep -vF porcelain` returns nothing). The exemption is consistent across files:
- 03_review and 02_build exempt the task's own spec and review files.
- task.md exempts "the plan or spec file itself". A review file cannot exist yet at the writer's Step 5, so this difference is correct.

**Invariants:** this is a docs-only change. No code, SQL, environment, LLM, network or CI path is touched. `CLAUDE.md`, `AGENTS.md`, `docs/prompts/review.md` and `workflow/stages/01_spec/CONTEXT.md` are unchanged (`git diff --quiet` exits 0).

## 3. Verification & Quality Gates
- **Python hermetic test suite (run by the reviewer):** `Ran 208 tests`, `OK`. 208 passed, matching the baseline, with no new tests (as the spec requires).
- **Next.js lint and build:** not applicable, because `web/` was not touched.
- **Scope (the new Gate 3 applied to this task):**
  - `git diff --stat` lists exactly the 5 allowed files.
  - `git status --porcelain --untracked-files=all` lists those 5 as ` M`, plus `?? workflow/stages/01_spec/output/task-7.3.2-spec.md`. That file is the task's own spec and is exempt as a stage output.
  - There are no unannounced files.
- **Em dashes (R-02), whole files:** 0 in each of the 5 touched files.

## 4. What Was NOT Verified
- Whether the Builder and Reviewer agents run the new command at runtime. That shows only on the next orchestrated task.
- `AGENTS.md:53` (Definition of done item 4) still uses only `git diff --stat`. It was left alone because AGENTS.md is off limits for this order, as the spec's Out of scope section records.

## 5. Conclusion
APPROVED. Every gate passed: 208 tests passed, scope matches the spec, there are no em dashes, and all three scope checks catch new files.

**Non-blocking:**
- `AGENTS.md:53` - Definition of done item 4 has the same new-file gap. Candidate for a later task that is allowed to edit AGENTS.md: add `git status --porcelain --untracked-files=all` there too.

## 6. Rule Candidates
None.
