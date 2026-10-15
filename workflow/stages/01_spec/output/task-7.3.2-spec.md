# Plan: Task 7.3.2: Scope Check Catches New Files (docs only)

**Date:** 2026-10-15
**Task ID:** 7.3.2 (follow-up to 7.3.1, commit `fd6dd2b`)
**Target paths (exhaustive, the allowed list):** `workflow/stages/03_review/CONTEXT.md`, `workflow/stages/02_build/CONTEXT.md`, `docs/prompts/task.md`, `docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/build-report.md`
**Reference:** orchestrator order 7.3.2; `workflow/stages/03_review/output/task-7.3.1-review.md` (both non-blocking items)
**Skills:** `antislop-copywriting` (R-02: zero em dashes)

---

## Goal
Make every scope check also run `git status --porcelain`, so a new untracked file outside the spec is caught and blocks, and reword review Gate 5's human-run Turso write line.

---

## Engineering & antislop Protocol Compliance
- **Docs only:** no change under `src/`, `web/`, `tests/`, `.github/`, or any root script. No new tests.
- **No production touch points:** no Turso, Telegram, Gemini or CI.
- **Not touched:** `CLAUDE.md`, `AGENTS.md`, `docs/prompts/review.md`, `workflow/stages/01_spec/CONTEXT.md`.
- **R-02:** zero U+2014 in every allowed file after the change. Baseline: 0 in all five.
- **No file deleted or moved.**

---

## Current Behavior (Evidence)

Baseline at `fd6dd2b` (clean tree): `uv run python -m unittest discover tests` gives `Ran 208 tests`, `OK`. `git check-ignore -v` on all five allowed files prints nothing and exits 1.

**Scope checks that use only `git diff --stat`** (`grep -rn "diff --stat"`):
- `workflow/stages/03_review/CONTEXT.md:35-36`: "Check `git diff --stat`. Verify every modified file was authorized in the specification." / "Any unannounced modifications are blocking."
- `workflow/stages/02_build/CONTEXT.md:52`: "3. Git hygiene: `git diff --stat` must show only planned files plus the bookkeeping files above."
- `docs/prompts/task.md:42`: "- `git diff --stat`: every file appears in the plan."
- `AGENTS.md:53` (Definition of done item 4). This file is off limits; see Out of scope.

`git diff --stat` compares tracked files only. A new untracked file never appears in it, so an unannounced new file passes all three checks today.

**Stage outputs are untracked during build and review.** Commit `fd6dd2b` adds `task-7.3.1-spec.md` and `task-7.3.1-review.md` in the same commit as the task, so both files are untracked (`??`) while the Builder and Reviewer run. The same holds for `docs/plans/<date>-task-<id>.md` outside herdr: `docs/plans/` is tracked, and each plan file arrives as a new file. Under the order's rule as written, the task's own spec would block every review, including this task's own Done-when (see Part 1.4).

**Gate 5 wording:** `workflow/stages/03_review/CONTEXT.md:51`: "No Turso write that the spec says a human runs." This reads as a rule about the spec, not a check on the Builder (7.3.1 review, Non-blocking 1).

---

## Proposed Changes

Wording below is normative. The Builder may adjust formatting (bold, list style) to match the surrounding file, but not the meaning.

**Command choice:** use `git status --porcelain --untracked-files=all`. With the default untracked mode, a new directory shows as a single `?? dir/` line. `--untracked-files=all` lists each file in it, so every new file can be checked against the spec by name. It is still `git status --porcelain`, as ordered. New untracked files are the lines that start with `??`.

### Part 1. Scope checks

**1.1 `workflow/stages/03_review/CONTEXT.md`, Gate 3** (`Scope & Plan Compliance`). Replace lines 35-36 with:
```markdown
   - Check `git diff --stat` and `git status --porcelain --untracked-files=all`. Verify every modified or new file was authorized in the specification.
   - Any unannounced modification is blocking. Any new untracked file (a `??` line) that the spec does not list is blocking.
```
Keep line 37 (Bookkeeping files) unchanged. After it, add:
```markdown
   - **Stage outputs**: the task's own spec (`workflow/stages/01_spec/output/task-<id>-spec.md`) and review files (`workflow/stages/03_review/output/task-<id>-review.md`) are workflow records, not changes. They never count as a scope violation.
```

**1.2 `workflow/stages/02_build/CONTEXT.md:52`**. Replace with:
```markdown
3. Git hygiene: `git diff --stat` must show only planned files plus the bookkeeping files above. `git status --porcelain --untracked-files=all` must show no new untracked file (a `??` line) other than planned files, the bookkeeping files, and the task's own spec and review files. Any other new file is blocking.
```

**1.3 `docs/prompts/task.md:42`**. Replace with:
```markdown
- `git diff --stat` and `git status --porcelain --untracked-files=all`: every changed or new file appears in the plan. A new untracked file (a `??` line) that is not in the plan is blocking. The plan or spec file itself and the bookkeeping files (`docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/*`) do not count.
```

**1.4 Reviewer addition: the stage-output exemption.** The order exempts only files listed in the spec and the bookkeeping files. The task's own spec and review files (and the plan file outside herdr) are neither, and they are always untracked while the task runs (see Evidence). Without the exemption in 1.1, 1.2 and 1.3, every review would block on its own spec, and this task's Done-when ("git status --porcelain shows only allowed files") would fail on `?? workflow/stages/01_spec/output/task-7.3.2-spec.md`. The exemption is limited to the current task's own `<id>`. If the orchestrator rejects it, strike those three sentences and accept that the spec file shows as untracked.

### Part 2. Gate 5 wording
`workflow/stages/03_review/CONTEXT.md:51`. Replace the line with:
```markdown
   - The Builder ran no Turso write that the spec leaves to a human.
```

### Part 3. Bookkeeping
- **`docs/contexts/task-ledger.md`**: line 4 is already `2026-10-15`; leave it. Under `#### Phase 7: Build & Dependency Hygiene (P7)`, directly after the Task 7.3.1 line, append:
  ```
  - [x] **Task 7.3.2: Scope Check Catches New Files** (Scope checks in 03_review CONTEXT, 02_build CONTEXT and task.md Step 5 also run `git status --porcelain --untracked-files=all`; unlisted new untracked files are blocking, except bookkeeping files and the task's own spec and review files; Gate 5 human-run Turso write line reworded).
  ```
- **`workflow/stages/02_build/output/build-report.md`**: rewrite for 7.3.2 as usual, zero em dashes.

---

## Out of scope
- **`AGENTS.md:53`** (Definition of done: "`git diff --stat` shows only files the task needed") has the same gap. AGENTS.md is off limits for this order. Candidate for a later task that is allowed to edit AGENTS.md.
- **Ignored new files.** `git status --porcelain` does not list ignored files. 03_review Step 0 (`git check-ignore -v`) already covers ignored targets. An ignored file that is not a target stays invisible; no change here.
- **`docs/prompts/review.md` Check 2** ("Every changed file appears in the plan") is not a `git diff --stat` command and is not in the allowed list. The review schema it points to (03_review Gate 3) gets the new check.

---

## Test Plan
No behavior change, so no new tests. The suite must stay at **208**.

---

## Verification Plan (repo root, PowerShell)
1. **Suite:** `uv run python -m unittest discover tests`. Expect `Ran 208 tests` and `OK`.
2. **Scope:** `git diff --stat` lists only allowed files. `git status --porcelain --untracked-files=all` lists only allowed files plus `?? workflow/stages/01_spec/output/task-7.3.2-spec.md` (the stage output, per 1.4).
3. **Em dashes, whole files:** expect 0 for every file:
   ```powershell
   $files = 'workflow\stages\03_review\CONTEXT.md','workflow\stages\02_build\CONTEXT.md','docs\prompts\task.md','docs\contexts\task-ledger.md','workflow\stages\02_build\output\build-report.md'
   $files | % { "{0}: {1}" -f $_, (Select-String -Path $_ -Pattern ([char]0x2014) | Measure-Object).Count }
   ```
4. **New check present:** `Select-String -SimpleMatch 'git status --porcelain --untracked-files=all'` finds one hit each in `03_review/CONTEXT.md`, `02_build/CONTEXT.md` and `docs/prompts/task.md`. Every remaining `git diff --stat` mention in those three files appears on a line together with the new command.
5. **Gate 5:** `03_review/CONTEXT.md` contains `The Builder ran no Turso write that the spec leaves to a human.` and no longer contains `that the spec says a human runs`.
6. **Untouched:** `git diff --quiet -- CLAUDE.md AGENTS.md docs/prompts/review.md workflow/stages/01_spec/CONTEXT.md` exits 0.

## Not verified by this plan
- Whether agents run the new command at runtime. That shows only on the next orchestrated build and review.
