# Review: Task 7.3.1: Review Format Merge and Ignored-Target Check

- **Task ID:** 7.3.1
- **Date:** 2026-10-15
- **Reviewer:** Claude Code (REVIEWER)
- **Target files:** `workflow/stages/02_build/CONTEXT.md`, `workflow/stages/03_review/CONTEXT.md`, `docs/prompts/review.md`, `docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/build-report.md`
- **Status:** APPROVED

## 1. Executive Summary
Docs-only change, uncommitted on `main` at `417362d`. The Builder removed the duplicate ledger line from the Builder context and added a Step 0 `git check-ignore -v` check to the review context. It replaced the Output section of `docs/prompts/review.md` with a pointer, so the `03_review/CONTEXT.md` schema is now the only review format. Every check that existed only in `review.md` was carried into the review context. The diff matches the spec's normative wording.

## 2. Deliverables & Invariants Verification

**Step 0 (ignored targets):** `git check-ignore -v` on all five target files printed nothing and exited 1. No target is ignored or excluded, so `git diff` shows every change.

| Spec part | Evidence | Result |
|---|---|---|
| 1. Delete `02_build/CONTEXT.md:11` and keep line 12 | Diff removes exactly `- Task ledger updates: ...`. `task-ledger.md` now appears once, at `:11` (the Bookkeeping line). | Done |
| 2. Step 0 before Required Reading | `03_review/CONTEXT.md:13-17`. It comes before `## Required Reading` (`:19`) and covers exit 1, a printed match, and exit 128. | Done |
| 3.1 Gate 1 `.env` bullet | `03_review/CONTEXT.md:30` | Done |
| 3.2 Gate 4 "name the line of the diff" | `:41` | Done |
| 3.3 Gate 5: invariant-by-invariant, `ON CONFLICT`, per job, human-run write | `:43`, `:44`, `:50`, `:51` | Done |
| 3.4 Gate 7 production SQL | `:55-57` | Done |
| 3.5 Schema: only-format sentence, "run by the reviewer", Non-blocking, Rule Candidates, fix block | `:60`, `:66`, `:73`, `:74`, `:76-81` | Done |
| 4. `review.md` Output becomes a pointer; lines 1-33 unchanged | Diff touches only lines 36 onward. The new `:36-37` resolves the conflict with "Do not edit any file" (`:14`). | Done |
| 5. Ledger entry after 7.3; build report rewritten | `task-ledger.md` +1 line in Phase 7. `build-report.md` is a full rewrite for 7.3.1. | Done |

**Every item from the old `review.md` Output and Check sections is kept:** `Tests ... (run by reviewer)` maps to `:66`, Blocking to `:72`, Non-blocking to `:73`, Rule candidates to `:74`, and the paste block to `:76-81`. All 8 typical misses are now covered by Gates 1 and 5. Check 7 is now Gate 7. The `## Check` section of `review.md` (`:16-32`) is unchanged, so nothing was removed there either.

**One format:** `docs/prompts/review.md` no longer contains `Verdict:`, `Blocking:`, `Non-blocking:` or `Rule candidates:`. The only format left is the schema.

**Invariants:** this is a docs-only change. No code, SQL, environment, LLM, network or CI paths are touched. `CLAUDE.md`, `AGENTS.md`, `docs/prompts/task.md` and `workflow/stages/01_spec/CONTEXT.md` are unchanged (`git diff --quiet` exits 0).

## 3. Verification & Quality Gates
- **Python hermetic test suite (run by the reviewer):** `Ran 208 tests`, `OK`. 208 passed, matching the baseline. No tests were added, as the spec requires.
- **Next.js lint and build:** not applicable, because `web/` was not touched.
- **Scope:** `git diff --stat` lists exactly the 5 allowed files. `git status --short --untracked-files=all` adds only `workflow/stages/01_spec/output/task-7.3.1-spec.md`, which is the spec's own stage output. There are no unannounced files.
- **Em dashes (R-02), whole files:** 0 in each of the 5 touched files.
- **Verdict words:** the only uppercase `PASS`, `FAIL` or `REJECTED` hit is `build-report.md:64`, which says these words are absent. It is not a verdict.

## 4. What Was NOT Verified
- Whether agents follow Step 0 and the merged schema at runtime. That shows only on the next orchestrated review.
- Line endings: git warns that LF will become CRLF in the 5 touched files. This affects only how the files are stored, not their content, and it matches earlier tasks.

## 5. Conclusion
APPROVED. Every gate passed: 208 tests passed, scope matches the spec, there are no em dashes, and there is one review format.

**Non-blocking:**
- `workflow/stages/03_review/CONTEXT.md:51` - "No Turso write that the spec says a human runs" can read as a rule for the spec rather than a check on the Builder. Suggested wording: "The Builder ran no Turso write that the spec leaves to a human."
- `workflow/stages/03_review/CONTEXT.md:35` - Gate 3 still relies on `git diff --stat`, which does not list untracked new files. Adding `git status --short --untracked-files=all` would close this gap. It was already listed as out of scope in the spec and is a candidate for a follow-up.

## 6. Rule Candidates
None.
