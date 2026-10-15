# Plan: Task 7.3.1: Review Format Merge and Ignored-Target Check (docs only)

**Date:** 2026-10-15
**Task ID:** 7.3.1 (follow-up to 7.3, commit `417362d`)
**Target paths (exhaustive, the allowed list):** `workflow/stages/02_build/CONTEXT.md`, `workflow/stages/03_review/CONTEXT.md`, `docs/prompts/review.md`, `docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/build-report.md`
**Reference:** orchestrator order 7.3.1; Task 7.3 spec "Out of scope: Two review output formats"
**Skills:** `antislop-copywriting` (R-02: zero em dashes)

---

## Goal
Remove one duplicate ledger line from the Builder context, add an ignored-target check as the reviewer's first step, and make the `03_review/CONTEXT.md` schema the only review report format without losing any check from `docs/prompts/review.md`.

---

## Engineering & antislop Protocol Compliance
- **Docs only:** no change under `src/`, `web/`, `tests/`, `.github/`, or any root script. No new tests.
- **No production touch points:** no Turso, Telegram, Gemini or CI.
- **Not touched:** `CLAUDE.md`, `AGENTS.md`, `docs/prompts/task.md`, `workflow/stages/01_spec/CONTEXT.md`.
- **R-02:** every allowed file has zero U+2014 characters after the change. Baseline today: 0 in all five files.
- **Verdict words:** only `APPROVED` and `CHANGES REQUESTED`.
- **No file deleted or moved.**

---

## Current Behavior (Evidence)

Baseline: `uv run python -m unittest discover tests` gives `Ran 208 tests ... OK` (run by the spec author at `417362d`). `git check-ignore -v` on all five allowed files prints nothing and exits 1, so none of them is ignored.

**(1) Duplicate ledger line**
- `workflow/stages/02_build/CONTEXT.md:11`: `- Task ledger updates: \`docs/contexts/task-ledger.md\`.`
- `workflow/stages/02_build/CONTEXT.md:12`: the Bookkeeping files line already allows `docs/contexts/task-ledger.md`. Line 11 is redundant.

**(2) No ignored-target check**
- `workflow/stages/03_review/CONTEXT.md:13-17` (Required Reading) sends the reviewer straight to `git diff`. `git diff` and `git diff --stat` never show a file that is untracked and ignored (by `.gitignore`, `.git/info/exclude` or a global excludes file), so a change to such a target is invisible to the review.

**(3) Two report formats**
- `docs/prompts/review.md:34-56` (`## Output`) defines a fenced text format: `Task`, `Verdict`, `Tests`, `Blocking`, `Non-blocking`, `Rule candidates`, plus a paste-ready fix block on CHANGES REQUESTED.
- `workflow/stages/03_review/CONTEXT.md:45-58` (`## Review Deliverable`) defines a sectioned schema: Metadata, 1 to 5.
- `CLAUDE.md:6` sends any review to `docs/prompts/review.md`; the herdr reviewer reads `03_review/CONTEXT.md`. Both formats are live.
- `docs/prompts/review.md:14`: "Do not edit any file." `03_review/CONTEXT.md:8,46` tells the reviewer to write a report file. Once `review.md` points at that schema, this conflict must be resolved in the pointer.

**What exists only in `review.md` (gap analysis against `03_review/CONTEXT.md`)**

| `review.md` item | Already in 03_review CONTEXT? | Action |
|---|---|---|
| Check 1 run tests yourself (`:18`) | Gates 1, 2 and `:11` | none |
| Check 2 scope (`:19`) | Gate 3 | none |
| Check 3 cause, not symptom (`:20`) | Gate 4 bullet 2 | none |
| Check 4 "name the line of the diff each new test depends on; a test that also passes on old code is blocking" (`:21`) | Gate 4 bullet 1 covers "fails on previous code" but not "name the line" or "blocking" | move |
| Check 5 "for each AGENTS.md invariant the diff touches, state whether it still holds" (`:22`) | Gate 5 lists six fixed items only | move |
| Miss: empty env var as set (`:24`) | Gate 5 `:36` | none |
| Miss: SQL with f-strings (`:25`, first half) | Gate 5 `:35` | none |
| Miss: write not idempotent (`:25`, second half) | no | move |
| Miss: test can reach real Turso, Gemini or Telegram, `.env` loads at import (`:26`, first half) | Gate 1 `:23` says "zero real network requests" only | move |
| Miss: test calls `time.sleep` (`:26`, second half) | Gate 5 `:40` | none |
| Miss: `open()` without UTF-8 (`:27`) | Gate 5 `:37` | none |
| Miss: secret in a log (`:28`) | Gate 5 `:38` | none |
| Miss: Gemini error by `str(e)` (`:29`) | Gate 5 `:39` | none |
| Miss: request per job, not per batch (`:30`) | no | move |
| Miss: Turso write the plan said a human runs (`:31`) | no | move |
| Check 7 production SQL vs live schema and unique-key conflicts (`:32`) | no | move |
| Output: `Tests: <N> passed (run by reviewer)` (`:39`) | Section 3 "exact count passed" | add "run by reviewer" |
| Output: Non-blocking list (`:44-45`) | no | move |
| Output: Rule candidates (`:47-48`) | no | move |
| Output: paste-ready fix block (`:51-56`) | no | move |

The `## Read` and `## Check` sections of `review.md` stay as they are (the order replaces only `## Output`), so no check is removed from `review.md` either.

---

## Proposed Changes

Wording below is normative. The Builder may adjust formatting (bold, list style) to match the surrounding file, but not the meaning.

### Part 1. `workflow/stages/02_build/CONTEXT.md`
Delete line 11 (`  - Task ledger updates: \`docs/contexts/task-ledger.md\`.`). Keep line 12 unchanged. No other edit to this file.

### Part 2. `workflow/stages/03_review/CONTEXT.md`: ignored-target check
Insert a new section between `## Allowed Writes & Boundary Constraints` (ends at line 11) and `## Required Reading & Review Inputs` (line 13):

```markdown
## Step 0: Ignored-Target Check (run first)
Before reading any diff, run `git check-ignore -v <path>` on every target file in the spec and every file the Builder listed.
- No output (exit code 1): no target is ignored. Continue.
- A printed line names a target and the rule that ignores or excludes it (`.gitignore`, `.git/info/exclude`, or a global excludes file). `git diff` cannot show that file. Say so in the review under **2. Deliverables & Invariants Verification**, and read that file in full instead of relying on `git diff`.
- Exit code 128 is an error: report BLOCKED with the error text.
```

### Part 3. `workflow/stages/03_review/CONTEXT.md`: merge checks from `review.md`

**3.1 Gate 1** (`Run Hermetic Test Suite`): add a bullet after line 23:
```markdown
   - No test can reach real Turso, Gemini or Telegram. `main.py` loads `.env` at import, so any test that builds a storage or API client must blank `TURSO_*`, `GEMINI_*` and `TELEGRAM_*` or mock the client.
```

**3.2 Gate 4** (`Root Cause & Test Validity`): add a bullet after line 33:
```markdown
   - For each new test, name the line of the diff it depends on. A test that would also pass on the old code is blocking.
```

**3.3 Gate 5** (`Invariants & Common Failure Modes`): insert as the first bullet (before line 35):
```markdown
   - For each AGENTS.md invariant the diff touches, state whether it still holds. The items below are the typical misses in this repo, not the full list.
```
Change line 35 to:
```markdown
   - Parameterized SQL only (no f-strings or string concatenation), and every write idempotent (`ON CONFLICT`).
```
Append after line 40:
```markdown
   - Gemini extraction stays batched: no new request per job.
   - No Turso write that the spec says a human runs.
```

**3.4 New Gate 7**: append after Gate 6 (after line 43):
```markdown
7. **Production SQL in the spec** (if any):
   - Check it against the live Turso schema differences listed in AGENTS.md (Storage).
   - Check what happens to rows that conflict on a unique key.
```

**3.5 `## Review Deliverable`**
- Line 46: append one sentence: `This schema is the only review report format. \`docs/prompts/review.md\` points here.`
- Line 52: change to `  - Python Hermetic Test Suite (exact count passed, run by the reviewer).`
- Replace lines 56-58 (section 5) and append sections 6 and the fix block:
```markdown
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
```
(The outer fence above is only for this spec. In CONTEXT.md, the fix block is a single fenced block.)

The reference in the fix block changes from "steps 5 and 6 of docs/prompts/task.md" (`review.md:54`) to cover both flows, because under herdr the Builder follows `02_build/CONTEXT.md`, not `task.md`.

### Part 4. `docs/prompts/review.md`: replace `## Output`
Replace lines 34-56 (from `## Output` to the end of the file) with:
```markdown
## Output

Use the report schema in `workflow/stages/03_review/CONTEXT.md` (`## Review Deliverable`). It is the only review format. The verdict is `APPROVED` or `CHANGES REQUESTED`.
Under herdr orchestration, write the report to `workflow/stages/03_review/output/task-<id>-review.md`. Otherwise, give it in your reply; "Do not edit any file" above still holds.
```
Do not change lines 1-33. The em dash fixes from 7.3 at old lines 42 and 45 disappear with the old block.

### Part 5. Bookkeeping
- **`docs/contexts/task-ledger.md`**: line 4 is already `2026-10-15`; leave it. Under `#### Phase 7: Build & Dependency Hygiene (P7)`, directly after the Task 7.3 line, append:
  ```
  - [x] **Task 7.3.1: Review Format Merge & Ignored-Target Check** (Duplicate ledger line removed from 02_build CONTEXT; 03_review CONTEXT gains Step 0 `git check-ignore -v` check; review.md Output replaced by a pointer so the 03_review schema is the only report format, with typical misses, production SQL check, non-blocking list, rule candidates and paste-ready fix block moved in).
  ```
- **`workflow/stages/02_build/output/build-report.md`**: rewrite for 7.3.1 as usual, zero em dashes.

---

## Out of scope
- **`git diff --stat` misses untracked files.** A new, untracked, non-ignored file does not show in `git diff --stat`, so Gate 3 can miss an unannounced new file. `git status --short --untracked-files=all` would catch it. This is a reviewer note for a later task; the order does not ask for it.
- **`02_build/CONTEXT.md:10`** (`build-report.md` line) is also covered by the bookkeeping line 12. The order removes only line 11.
- **Historical review outputs** in `workflow/stages/03_review/output/` keep their old format. They are records.
- **`CLAUDE.md:6`** still points to `docs/prompts/review.md`, which now points to the schema. No change needed.
- **`docs/prompts/review.md` Read item 4** (remediation plan and audit finding): a reading input, not a check, and it stays in `review.md`. The herdr reviewer gets the finding from the spec.

---

## Test Plan
No behavior change, so no new tests. The suite must stay at **208**.

---

## Verification Plan (repo root, PowerShell)
1. **Suite:** `uv run python -m unittest discover tests`. Expect `Ran 208 tests` and `OK`.
2. **Scope:** `git diff --stat` and `git status --short` list only files from the allowed list.
3. **Em dashes, whole files:** expect 0 for every file:
   ```powershell
   $files = 'workflow\stages\02_build\CONTEXT.md','workflow\stages\03_review\CONTEXT.md','docs\prompts\review.md','docs\contexts\task-ledger.md','workflow\stages\02_build\output\build-report.md'
   $files | % { "{0}: {1}" -f $_, (Select-String -Path $_ -Pattern ([char]0x2014) | Measure-Object).Count }
   ```
4. **One format:** `Select-String -Path docs\prompts\review.md -Pattern 'Verdict:','Blocking:','Rule candidates:','Non-blocking:'` returns nothing. `03_review/CONTEXT.md` contains `Rule Candidates`, `Non-blocking`, and `Review of task <id>: changes requested.`
5. **Part 1:** `Select-String -Path workflow\stages\02_build\CONTEXT.md -Pattern 'task-ledger.md'` returns exactly one line (the Bookkeeping line).
6. **Part 2:** `03_review/CONTEXT.md` contains `git check-ignore -v`, in a section that comes before `## Required Reading & Review Inputs`.
7. **Moved checks:** `03_review/CONTEXT.md` contains `.env`, `ON CONFLICT`, `per job`, `a human runs`, `unique key`, and `name the line of the diff`.
8. **Verdict words:** `Select-String -CaseSensitive -Pattern '\bPASS\b','\bFAIL\b','REJECTED'` over the allowed files returns no verdict line.
9. **Untouched:** `git diff --quiet -- CLAUDE.md AGENTS.md docs/prompts/task.md workflow/stages/01_spec/CONTEXT.md` exits 0.

## Not verified by this plan
- Whether agents follow the merged schema and Step 0 at runtime. That shows only on the next orchestrated review.
