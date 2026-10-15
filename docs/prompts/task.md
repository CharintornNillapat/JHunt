# Task protocol

> **Under herdr orchestration:** the spec at `workflow/stages/01_spec/output/task-<id>-spec.md` replaces `docs/plans/` (Step 2), and the human approval gate is the orchestrator's pause-after-spec option, not the word "approved".

Use this for any task from the remediation plan, or any change to `src/`, `web/` or CI.
Input: a task ID (for example `0.4`) or a one-line description.

## Step 1. Understand (read only, no edits)

1. Read the task in `docs/audits/2026-10-12-remediation-plan.md` and the matching finding in the 2026-10-12 audit. The audit has the evidence and file:line references.
2. Open every file the task names, plus its tests. If a named path does not exist, grep for the symbol and use the real path.
3. Write down:
   - current behavior, with file:line
   - what must change
   - which AGENTS.md invariants apply
4. If the plan, the audit and the code disagree, list each disagreement. Do not pick one silently.

## Step 2. Plan (write the file, then STOP)

Write `docs/plans/<YYYY-MM-DD>-task-<id>.md` containing:

- **Goal**: one sentence.
- **Changes**: each file, with the specific change.
- **Tests to add**: test name, what it asserts, and why it fails today.
- **Out of scope**: things you noticed but will not touch.
- **Production touch points**: Turso writes, Telegram, Gemini quota, CI. Any SQL goes here, for a human to run.

Then stop and wait for the word "approved".

## Step 3. Test first

Write the new tests. Run them. Confirm they fail for the expected reason and paste the failing line.

## Step 4. Implement

Make the smallest change that makes the tests pass. Edit only files listed in the plan; if you need another file, say why before editing it.

## Step 5. Verify

- `uv run python -m unittest discover tests`: all pass.
- If `web/` changed: `cd web; npm run lint; npm run build`.
- `git diff --stat` and `git status --porcelain --untracked-files=all`: every changed or new file appears in the plan. A new untracked file (a `??` line) that is not in the plan is blocking. The plan or spec file itself and the bookkeeping files (`docs/contexts/task-ledger.md`, `workflow/stages/02_build/output/*`) do not count.
- Re-read the AGENTS.md invariants and confirm each one the diff touches still holds.

## Step 6. Report

```
Task: <id> <title>
Changed:
- <file>: <one line>
Tests: <N> passed (new: <test names>)
Not verified: <for example "SQL not run", "CI not run">
Needs human: <SQL to run, secrets to add, workflow change to push>
```

Then mark the task in `docs/contexts/task-ledger.md`.

## Rules for the whole task

- The same error twice after a fix: stop and report what you tried.
- Never run anything in the AGENTS.md "Stop and ask first" list.
