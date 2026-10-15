# Plan: Task 7.3: Workflow Rule Hygiene (docs only)

**Date:** 2026-10-15
**Task ID:** 7.3
**Target paths (exhaustive, the allowed list):** `AGENTS.md`, `docs/prompts/task.md`, `docs/prompts/review.md`, `workflow/stages/01_spec/CONTEXT.md`, `workflow/stages/02_build/CONTEXT.md`, `workflow/stages/03_review/CONTEXT.md`, `docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/build-report.md`
**Reference:** orchestrator order 7.3; `HANDOFF.md:21` (stale AGENTS.md map line, already noted there)
**Skills:** `antislop-copywriting` (R-02: zero em dashes)

---

## Goal
Make every workflow rule file agree with the herdr orchestrator on verdicts, spec location, stop point, bookkeeping files, the review file and the Builder execution strategy. Also fix two stale doc facts and remove every em dash from the touched files.

---

## Engineering & antislop Protocol Compliance
- **Docs only:** no change under `src/`, `web/`, `tests/`, `.github/`, or any root script.
- **No production touch points:** no Turso, Telegram, Gemini or CI.
- **R-02:** after this task, every allowed file contains zero U+2014 characters (not just the added lines).
- **AGENTS.md:** the Builder may edit it for this task only, and only for part (3) plus the R-02 fix in part (4) (see 4.1). No agy-specific text goes in AGENTS.md.
- **CLAUDE.md:** not touched.
- **No file deleted or moved.** In particular, `workflow/stages/03_review/output/review.md` stays where it is.

---

## Current Behavior (Evidence)

**Verdict conflicts**
- `docs/prompts/review.md:38`: `Verdict: PASS | FAIL`. Line 51: `On FAIL, end with this block...`. Line 54: `Review of task <id> failed.`
- `workflow/stages/03_review/CONTEXT.md:46`: `Status (\`APPROVED\` or \`REJECTED\`)`. Line 56: `If **REJECTED**: ...`.
- The orchestrator uses `APPROVED / CHANGES REQUESTED`.

**Spec location and stop point**
- `docs/prompts/task.md:18`: write the plan to `docs/plans/<YYYY-MM-DD>-task-<id>.md`. Line 26: `Then stop and wait for the word "approved"`.
- `docs/prompts/review.md:10`: read the plan from `docs/plans/*-task-<id>.md`. Under herdr, the spec lives in `workflow/stages/01_spec/output/`.
- `workflow/stages/01_spec/CONTEXT.md:41-44`: "Stop and present the specification for human confirmation before builder execution."

**Bookkeeping and scope**
- `workflow/stages/02_build/CONTEXT.md:10-11` allows `build-report.md` and the ledger, but `:45` says "`git diff --stat` must show only planned files".
- `workflow/stages/03_review/CONTEXT.md:28-29`: "Verify every modified file was authorized in the specification. Any unannounced modifications are blocking." There is no exception for bookkeeping files.

**Review file**
- `workflow/stages/03_review/output/review.md` is a legacy single-file review from Task 3.4 (commit `700ae5c`). It starts with `Verdict: PASS`. Neither CONTEXT.md says to ignore it.

**AGENTS.md ban**
- `workflow/stages/02_build/CONTEXT.md:14`: "Do NOT create `GEMINI.md` or modify `AGENTS.md`, `CLAUDE.md`, ...". This is an absolute ban.

**Execution strategy**
- `workflow/stages/02_build/CONTEXT.md` has no rules on full-file reading, sub-agents or re-verification across review rounds.

**Stale docs**
- `AGENTS.md:81`: `2026-10-12-remediation-plan.md  current task list (Phase 0 → 1 → 2)`. This line is wrong in two ways:
  1. The file is not at the repo root. The real path is `docs/audits/2026-10-12-remediation-plan.md` (`git ls-files`).
  2. It covers only Phases 0 to 2. Live status is in `docs/contexts/task-ledger.md`, which already tracks Phases 3 to 7.
- The same bare, wrong path appears in `docs/prompts/task.md:8` and `workflow/stages/01_spec/CONTEXT.md:15`.
- `docs/contexts/task-ledger.md:4`: `**Last Updated**: 2026-10-10`. Tasks 7.1 and 7.2 were recorded on 2026-10-15.

**Em dashes**
`grep` for U+2014 over the allowed files finds exactly three:

| File | Line | Text |
|---|---|---|
| `AGENTS.md` | 1 | `# AGENTS.md <U+2014> JHunt` |
| `docs/prompts/review.md` | 42 | `1. <file>:<line> <U+2014> <problem> <U+2014> <required fix>` (2 dashes) |
| `docs/prompts/review.md` | 45 | `- <file>:<line> <U+2014> <suggestion>` |

(`<U+2014>` stands for the literal em dash, which this spec does not reproduce.)

The other allowed files have 0. The Builder rewrites `build-report.md` and must keep it at 0. The `→` arrows in AGENTS.md are U+2192, not em dashes, and they stay.

---

## Proposed Changes

Wording below is normative. The Builder may change formatting (bold, list style) to match the surrounding file, but not the meaning.

### Part 1. Builder execution strategy: `workflow/stages/02_build/CONTEXT.md`
Insert a new section directly after `## Required Reading & Handoff Protocol` (after current line 20):
```markdown
## Execution Strategy
1. **Full-Context Read**: Before editing, read the whole spec, every target file, and the test file for each target file, in full. Do not work from snippets or search hits.
2. **Sub-Agent Discipline**: Sub-agents may only read and explore. They never edit files or run commands that write. The main agent makes every edit, then runs verification once, sequentially, after all edits are done.
3. **Deep Verification on Fix**: On a fix order, fix only the blocking items in `workflow/stages/03_review/output/task-<id>-review.md`. Then rerun the full test suite and recheck every blocking item from all earlier review rounds of the same task, not only the newest round.
```

### Part 2. Rule conflicts

**2.1 Verdicts (APPROVED / CHANGES REQUESTED)**
- `docs/prompts/review.md:38`: change to `Verdict: APPROVED | CHANGES REQUESTED`.
- `docs/prompts/review.md:51`: change to `On CHANGES REQUESTED, end with this block so it can be pasted into Antigravity unchanged:`.
- `docs/prompts/review.md:54`: change to `Review of task <id>: changes requested. Fix only the blocking items below, then repeat steps 5 and 6 of docs/prompts/task.md.`
- `workflow/stages/03_review/CONTEXT.md:46`: change to `Status (\`APPROVED\` or \`CHANGES REQUESTED\`)`.
- `workflow/stages/03_review/CONTEXT.md:56`: change to `If **CHANGES REQUESTED**: ...` and keep the rest of the line.

**2.2 Spec location and stop point**
- `docs/prompts/task.md`: insert directly under the `# Task protocol` heading:
  ```markdown
  > **Under herdr orchestration:** the spec at `workflow/stages/01_spec/output/task-<id>-spec.md` replaces `docs/plans/` (Step 2), and the human approval gate is the orchestrator's pause-after-spec option, not the word "approved".
  ```
- `docs/prompts/review.md`: at the end of Read item 2 (line 10), add `Under herdr orchestration, read workflow/stages/01_spec/output/task-<id>-spec.md instead.`. Without this, review.md still sends the reviewer to `docs/plans/`, which conflicts with the note above. This file is in the allowed list.
- `workflow/stages/01_spec/CONTEXT.md:41-44`: replace the `## Stop & Handoff` body with:
  ```markdown
  Once the specification is written to `workflow/stages/01_spec/output/task-<id>-spec.md`:
  - Do not make any code edits.
  - Stop and report `SPEC DONE`. The orchestrator decides whether to pause for human approval.
  ```

**2.3 Bookkeeping files (both `02_build/CONTEXT.md` and `03_review/CONTEXT.md`)**
Add this sentence to each file. In 02_build, put it under `## Allowed Writes & Boundary Constraints`. In 03_review, put it under Gate 3 `Scope & Plan Compliance`:
```markdown
- **Bookkeeping files**: `docs/contexts/task-ledger.md` and `workflow/stages/02_build/output/*` are always allowed and never count as a scope violation, even when the spec does not list them.
```
Also change `02_build/CONTEXT.md:45` to: `Git hygiene: \`git diff --stat\` must show only planned files plus the bookkeeping files above.`

**2.4 Review file (both CONTEXT.md files)**
Add the following. In 02_build, put it under `## Required Reading & Handoff Protocol`, item 3. In 03_review, put it under `## Allowed Writes & Boundary Constraints`:
```markdown
- Only `workflow/stages/03_review/output/task-<id>-review.md` counts as the review for a task. Ignore the legacy `workflow/stages/03_review/output/review.md` (Task 3.4). Do not delete or move it.
```

**2.5 AGENTS.md edits: `02_build/CONTEXT.md:14`**
Replace the line with:
```markdown
  - Do NOT create `GEMINI.md` or modify `CLAUDE.md`, `.gitignore`, `.mcp.json`, or `web/package.json`.
  - Do NOT modify `AGENTS.md` unless the task spec explicitly authorizes it.
```

### Part 3. Stale docs
- **`AGENTS.md:81`**: replace with the following, aligned to the map's column style:
  ```
  docs/audits/2026-10-12-remediation-plan.md   original remediation plan (Phases 0 to 2); live status is docs/contexts/task-ledger.md
  ```
  Edit nothing else in AGENTS.md except the line 1 em dash (4.1).
- **`docs/prompts/task.md:8` and `workflow/stages/01_spec/CONTEXT.md:15`**: change the bare `2026-10-12-remediation-plan.md` to `docs/audits/2026-10-12-remediation-plan.md`. These are the same stale-path defect, both files are in the allowed list, and both are already edited in Part 2. This is a reviewer addition; the orchestrator can strike it.
- **`docs/contexts/task-ledger.md:4`**: change to `> **Last Updated**: 2026-10-15`.
- **Ledger entry**: under `#### Phase 7: Build & Dependency Hygiene (P7)`, append:
  ```
  - [x] **Task 7.3: Workflow Rule Hygiene** (Verdicts unified to APPROVED / CHANGES REQUESTED; herdr spec location and SPEC DONE stop point; bookkeeping and legacy review file rules; Builder execution strategy; AGENTS.md map and ledger date corrected; em dashes removed).
  ```

### Part 4. Em dashes
- **4.1 `AGENTS.md:1`**: change to `# AGENTS.md: JHunt`. The order limits the Builder's AGENTS.md permission to part (3), but its Done-when requires zero em dashes in every allowed file, and AGENTS.md is one of them. This spec reads the limit as "no other content changes". A one-character title fix is the only way to meet Done-when. If the orchestrator disagrees, strike 4.1 and accept a Done-when exception for AGENTS.md line 1.
- **4.2 `docs/prompts/review.md:42`**: `1. <file>:<line> - <problem> - <required fix>`.
- **4.3 `docs/prompts/review.md:45`**: `- <file>:<line> - <suggestion>`.
- **4.4** No new em dash in any added text, including `build-report.md`.

---

## Out of scope
- **The older `### Phase 7: Scale, Performance & Cloud Architecture Upgrades` section** in `task-ledger.md` (around line 86). It is unrelated and predates the remediation plan. Leave it untouched, including its numbering collision with the new Remediation Phase 7.
- **Historical review outputs** (`workflow/stages/03_review/output/task-*-review.md`, including 7.1 and 7.2, and the legacy `review.md`). They still say `Verdict: PASS`. They are records, not rules, and they are not in the allowed list. The Done-when check "no verdict uses PASS, FAIL or REJECTED" applies to the allowed files.
- **Two review output formats.** `review.md`'s Output block and `03_review/CONTEXT.md`'s schema are different formats. The reviewer currently writes both. Merging them is a separate decision.
- **`AGENTS.md` Map `as of 2026-10-12` header** and any other AGENTS.md wording.
- **`HANDOFF.md`** (untracked, not in the allowed list), even though its line 21 describes the map issue this task fixes.

---

## Test Plan
No behavior change, so no new tests. The suite must be unchanged at **208**.

---

## Verification Plan (repo root)
1. **Suite:** `uv run python -m unittest discover tests`. Expect **Ran 208 tests, OK**.
2. **Scope:** `git diff --stat` lists only files from the allowed list.
3. **Em dashes, whole files:** run this and expect 0 for every file:
   ```powershell
   $files = 'AGENTS.md','docs\prompts\task.md','docs\prompts\review.md','workflow\stages\01_spec\CONTEXT.md','workflow\stages\02_build\CONTEXT.md','workflow\stages\03_review\CONTEXT.md','docs\contexts\task-ledger.md','workflow\stages\02_build\output\build-report.md'
   $files | % { "{0}: {1}" -f $_, (Select-String -Path $_ -Pattern ([char]0x2014) | Measure-Object).Count }
   ```
4. **Verdict words:** `Select-String -Path <allowed files> -Pattern '\bPASS\b','\bFAIL\b','REJECTED' -CaseSensitive` returns no line that states a review verdict. A lowercase `pass` in "tests pass" doesn't count. List any remaining uppercase hit in the build report with a reason.
5. **Content spot checks:** `Execution Strategy` exists in 02_build. The `SPEC DONE` stop is in 01_spec. The bookkeeping and legacy review notes appear in both 02_build and 03_review. The herdr note is in task.md and review.md. AGENTS.md has exactly two changed lines (1 and 81).
6. **CLAUDE.md is untouched:** `git diff --quiet -- CLAUDE.md`.

## Not verified by this plan
- Whether agy and herdr actually follow the new rules at runtime. That is only observable on the next orchestrated task.
