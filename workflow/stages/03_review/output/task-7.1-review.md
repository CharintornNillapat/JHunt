# Review: Task 7.1: Recompile requirements.lock for the CI Python (3.11)

- **Task ID:** 7.1
- **Date:** 2026-10-15
- **Reviewer:** Claude Code (REVIEWER session)
- **Target files:** `requirements.lock`, `AGENTS.md`, `tests/test_lockfile.py` (new), `docs/contexts/task-ledger.md`
- **Status:** APPROVED

```
Task: 7.1
Verdict: PASS
Tests: 204 passed (run by reviewer, Python 3.14 local and Python 3.11 throwaway venv)
Blocking: none
```

---

## 1. Executive Summary
The Builder recompiled `requirements.lock` in place with `--python-version 3.11`. Below Python 3.12 the lock now pins `sphinx==9.0.4`, and from 3.12 up it pins `sphinx==9.1.0`. All other pins are unchanged. The documented compile command in `AGENTS.md` now includes the flag. A new hermetic test fails whenever the lock's target Python and the CI Python disagree. The diff matches the spec hunk for hunk.

---

## 2. Deliverables & Invariants Verification

| Spec item | Evidence | Result |
|---|---|---|
| 1. Lock recompiled in place, no drift | `git diff requirements.lock`: only the header (line 2), the sphinx fork (lines 104-106) and the `typing-extensions` "via" comment (lines 126-127). These are the same three hunks as spec Evidence 5. `google-genai` stays at 2.30.1. | PASS |
| 1. Header exact | `requirements.lock:2` = `#    uv pip compile requirements.txt --universal --python-version 3.11 -o requirements.lock` | PASS |
| 2. `AGENTS.md:33-34` | Comment and command match the spec text exactly. No other edits. | PASS |
| 3. `tests/test_lockfile.py` | Identical to the spec. Uses `pathlib.Path` and `encoding="utf-8"`. No network or env access. | PASS |
| 4. Ledger | `docs/contexts/task-ledger.md:143-144`: new Phase 7 block under Remediation Plan, after Phase 6. The old Phase 7 section is untouched. | PASS |

**Scope (`git diff --stat`):** `AGENTS.md`, `docs/contexts/task-ledger.md`, `requirements.lock`, and the untracked `tests/test_lockfile.py` are all planned. `workflow/stages/02_build/output/build-report.md` is the Builder's own stage output, not source. `HANDOFF.md` was already untracked before this task. No unplanned source changes.

**Root cause:** the cause was that the lock was resolved against the local 3.14 interpreter. The fix sets the target interpreter explicitly in both the lock header and the documented command, so it is fixed at the source, not by hand-pinning sphinx. The new test guards against drift between the lock and CI.

**Test proves the change:** the test depends on `requirements.lock:2`. Against `git show HEAD:requirements.lock`, the first 5 lines have zero matches for `--python-version`. On the old file `lock` would be `None`, so the second assertion fails. The test does not pass on the old code.

**Invariants touched:**
- Free tier / no new dependency: holds. `requirements.txt` is unchanged and no package was added.
- Hermetic tests: holds. The new test reads two repo files only.
- UTF-8 / `pathlib`: holds.
- `.github/workflows/`: not modified. Holds.
- SQL, LLM, Telegram, state, secrets: not touched.

---

## 3. Verification & Quality Gates (all run by reviewer)
- **Python suite (local 3.14.7):** `uv run python -m unittest discover tests`: **Ran 204 tests, OK** (baseline 203 + 1).
- **Real CI interpreter:** throwaway venv in the scratchpad, `uv venv --python 3.11` and `uv pip install -r requirements.lock`. Install succeeded. `import sphinx, libsql_client, google.genai, pydantic` succeeded and printed `(3, 11) 9.0.4`. Suite under 3.11: **Ran 204 tests, OK**. Venv removed afterwards.
- **Idempotency:** I recompiled a copy of the new lock with the same command. Apart from the header path, the body is **identical**.
- **Web:** `web/` is not touched, so lint and build are not required.
- **R-02:** 0 em dashes in `tests/test_lockfile.py` and 0 in the lines added to `AGENTS.md`, `task-ledger.md` and `requirements.lock`.

---

## 4. What Was NOT Verified
- A real GitHub Actions run on `ubuntu-latest`. Starting one (`gh workflow run`) needs your approval. The first confirmation will be the next scheduled 01:00 UTC run, or a run you start yourself.
- Linux wheel installation. It is covered by the `--universal` markers, but I tested the install only on Windows.

---

## 5. Conclusion
**APPROVED.** All gates passed.

Non-blocking:
- `workflow/stages/02_build/output/build-report.md`: the Builder replaced the whole report, so the Phase 6 report text is now only in git history (HEAD). If reports are meant to accumulate, append future tasks instead of overwriting.
- Still out of scope, as the spec says: `libsql-client==0.3.1` pulls sphinx and its toolchain into production installs through `sphinx-press-theme`. Worth a follow-up task.

Rule candidates:
- AGENTS.md (Commands): "Recompile `requirements.lock` only with `--python-version` equal to the CI Python, in place, never with `--upgrade` unless the task says so." (Mostly covered now by the new command and test.)
