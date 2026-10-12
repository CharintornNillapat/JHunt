# Review protocol

The reviewer (Claude Code) checks a change written by another agent (Antigravity CLI).
This is a blind review: judge the code against the plan and AGENTS.md, not against the writer's report or chat.
Input: a task ID (for example `0.4`).

## Read

1. `AGENTS.md`.
2. The plan: `docs/plans/*-task-<id>.md`.
3. The change: `git diff` (uncommitted) or `git diff main...HEAD`, plus the full text of every changed function.
4. The task and its finding in the 2026-10-12 remediation plan and audit.

Do not edit any file. The writer fixes; you judge.

## Check

1. **Run the tests yourself.** `uv run python -m unittest discover tests`; and if `web/` changed, `cd web; npm run lint; npm run build`. Do not trust the reported count.
2. **Scope.** Every changed file appears in the plan. Anything unplanned is blocking unless the writer explained it.
3. **The task is actually solved.** Re-read the finding. Does the diff remove the cause, or only the symptom the test checks?
4. **Tests prove the change.** For each new test, name the line of the diff it depends on. A test that would also pass on the old code is blocking.
5. **Invariants.** For each AGENTS.md invariant the diff touches, state whether it still holds.
6. **Typical misses in this repo:**
   - an empty-string env var treated as set
   - SQL built with f-strings, or a write that is not idempotent
   - a test that can reach real Turso, Gemini or Telegram (`.env` loads at import), or calls `time.sleep`
   - `open()` without `encoding="utf-8"` on Thai text
   - a secret, token or database URL in a log line
   - a Gemini error classified by searching `str(e)`
   - a new request per job instead of per batch
   - a Turso write the plan said a human would run
7. **Production SQL in the plan.** If there is any, check it against the live schema differences listed in AGENTS.md, and check what happens to rows that conflict on a unique key.

## Output

```
Task: <id>
Verdict: PASS | FAIL
Tests: <N> passed (run by reviewer)

Blocking:
1. <file>:<line> — <problem> — <required fix>

Non-blocking:
- <file>:<line> — <suggestion>

Rule candidates:
- <one-line AGENTS.md rule that would have prevented a blocking item, if any>
```

On FAIL, end with this block so it can be pasted into Antigravity unchanged:

```
Review of task <id> failed. Fix only the blocking items below, then repeat steps 5 and 6 of docs/prompts/task.md.
<blocking items, copied verbatim>
```
