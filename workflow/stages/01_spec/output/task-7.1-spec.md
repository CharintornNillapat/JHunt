# Plan: Task 7.1: Recompile requirements.lock for the CI Python (3.11)

**Date:** 2026-10-15
**Task ID:** 7.1
**Target paths:** `requirements.lock`, `AGENTS.md`, `tests/test_lockfile.py` (new), `docs/contexts/task-ledger.md`
**Reference:** `AGENTS.md` (Commands, Definition of done), `.github/workflows/scraper_cron.yml`, Task 4.3 spec (lockfile origin)
**Skills:** `antislop`, `antislop-copywriting` (R-02: zero em dashes)

---

## Goal
Make `requirements.lock` installable on the CI interpreter (Python 3.11) by compiling it with `--python-version 3.11`, and record that flag in the documented compile command so the next recompile does not repeat the problem.

---

## Engineering & antislop Protocol Compliance
- **R-02:** zero em dashes (U+2014) in every touched file, including the new test and the ledger line.
- **No new dependency:** `requirements.txt` is unchanged. The only resolution change allowed is the `sphinx` fork described below.
- **No workflow change:** `.github/workflows/scraper_cron.yml` is read, not edited. CI already installs 3.11 and installs from `requirements.lock`; its cache key (`cache-dependency-glob: "requirements.lock"`) rotates on its own when the lock changes.
- **Hermetic tests:** the new test reads two repo files. No network, no `.env`, no clients, no `time.sleep`.
- **UTF-8:** every `read_text` in the new test passes `encoding="utf-8"`. Paths use `pathlib.Path`.

---

## Current Behavior (Evidence)

1. **CI runs Python 3.11.** `.github/workflows/scraper_cron.yml:53`: `run: uv python install 3.11`, then `:57-58` `uv venv` and `uv pip install -r requirements.lock`.
2. **The lock was resolved for the local 3.14 interpreter.** The local default is Python 3.14.7. The compile command in `requirements.lock:2` and `AGENTS.md:34` is `uv pip compile requirements.txt --universal -o requirements.lock` with no `--python-version`. For `--universal`, uv uses the current interpreter as the lower bound for `requires-python`. That is 3.14 here.
3. **The failing pin.** `requirements.lock:104`: `sphinx==9.1.0` with no marker. sphinx 9.1.0 requires Python >=3.12, so the install fails on 3.11.
4. **Why sphinx is there at all.** `requirements.lock:104-107`: `sphinx` comes via `sphinx-press-theme`, which comes via `libsql-client==0.3.1`. This is an upstream packaging bug in libsql-client. It is out of scope (see below).
5. **Reviewer dry run (scratchpad only, repo untouched).** I copied the current lock into the scratchpad and recompiled it in place with `--python-version 3.11`, so the existing pins were used as preferences. Diff against the committed lock:
   ```
   2c2   header: command now includes --python-version 3.11
   104c104,106
   < sphinx==9.1.0
   > sphinx==9.0.4 ; python_full_version < '3.12'
   >     # via sphinx-press-theme
   > sphinx==9.1.0 ; python_full_version >= '3.12'
   123a126,127   typing-extensions "# via" comment gains aiohttp, aiosignal
   ```
   No other version changed. The 3.11 fork resolves to `sphinx==9.0.4`.
   **Pitfall:** compiling into a fresh output file, with no existing pins to prefer, also bumped `google-genai` 2.30.1 to 2.31.0. That drift is not allowed in this task. See step 1.

---

## Proposed Changes

### 1. `requirements.lock` (regenerate in place)
Run from the repo root, using the relative output path so the header stays clean:
```powershell
uv pip compile requirements.txt --universal --python-version 3.11 -o requirements.lock
```
- Do **not** pass `--upgrade` or `--upgrade-package`. Do not delete the lock first. uv keeps the existing pins only when the output file already exists.
- **Acceptance:** `git diff requirements.lock` shows only the three hunks in Evidence 5. Line 2 must read exactly `#    uv pip compile requirements.txt --universal --python-version 3.11 -o requirements.lock`. If any other package version changes, stop and report. Do not hand-edit the lock.

### 2. `AGENTS.md:34`
Replace the line with:
```powershell
uv pip compile requirements.txt --universal --python-version 3.11 -o requirements.lock
```
Change the comment above it (`AGENTS.md:33`) to:
`# Updating dependencies (recompile lockfile from requirements.txt; 3.11 = CI Python, keep in sync with scraper_cron.yml)`
Make no other edits to AGENTS.md.

### 3. `tests/test_lockfile.py` (new, regression guard)
The root cause is that the lock's target Python drifted from the CI Python. This test fails whenever they disagree:
```python
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestLockfileTargetsCiPython(unittest.TestCase):
    def test_lock_compiled_for_ci_python_version(self):
        workflow = (ROOT / ".github" / "workflows" / "scraper_cron.yml").read_text(encoding="utf-8")
        lock_header = "\n".join((ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()[:5])

        ci = re.search(r"uv python install (\d+\.\d+)", workflow)
        lock = re.search(r"--python-version (\d+\.\d+)", lock_header)

        self.assertIsNotNone(ci, "CI workflow no longer pins a Python via 'uv python install'")
        self.assertIsNotNone(lock, "requirements.lock was compiled without --python-version")
        self.assertEqual(lock.group(1), ci.group(1))


if __name__ == "__main__":
    unittest.main()
```
- **Fails on current code:** `requirements.lock:2` has no `--python-version`, so `lock` is `None` and the second assertion fails.
- **Passes after step 1:** the header carries `--python-version 3.11`, which matches `scraper_cron.yml:53`.

### 4. `docs/contexts/task-ledger.md`
Under `### Remediation Plan (2026-10-12)`, after the Phase 6 block, add:
```
#### Phase 7: Build & Dependency Hygiene (P7)
- [x] **Task 7.1: Lockfile Compiled for CI Python 3.11** (`requirements.lock` recompiled with `--python-version 3.11` so sphinx forks to 9.0.4 below 3.12; AGENTS.md compile command updated; lockfile/CI version guard test).
```
Do not touch the older, unrelated `### Phase 7: Scale, Performance & Cloud Architecture Upgrades` section near line 86.

---

## Out of scope
- **Removing sphinx from the dependency tree.** libsql-client 0.3.1 wrongly declares `sphinx-press-theme` as a runtime dependency, which pulls sphinx and about 15 other packages into production. A uv `--override` or a libsql-client upgrade could drop them. That is a separate task.
- **Local dev on 3.14 while CI runs 3.11.** A `.python-version` file would pin local uv to 3.11, but it is a new top-level file, and that needs approval.
- **Any `.github/workflows/` edit.** None is needed.

---

## Hermetic Test Plan
| Test | Depends on | Old code | New code |
|---|---|---|---|
| `tests.test_lockfile.TestLockfileTargetsCiPython.test_lock_compiled_for_ci_python_version` | `requirements.lock:2` header from step 1 | FAIL (no `--python-version`) | PASS |

No mocks are needed: the test reads only repo files, with no network, clients, env vars or sleeps.

---

## Verification Plan (PowerShell, repo root)
1. **Test fails first:** add `tests/test_lockfile.py` before recompiling, then run `uv run python -m unittest tests.test_lockfile -v` and expect 1 failure.
2. **Recompile** (step 1). Then check `git diff --stat`. Expect `requirements.lock`, `AGENTS.md`, `docs/contexts/task-ledger.md` and the new `tests/test_lockfile.py` (untracked). Check that the lock diff contains only the Evidence 5 hunks.
3. **Recompiling twice gives the same file:** run the step 1 command again. `git diff --quiet requirements.lock` must report no change compared with the first recompile (stage or copy the first result to compare).
4. **Real 3.11 install, the actual CI failure.** Use a throwaway venv outside the repo, and don't touch `.venv`:
   ```powershell
   $v = Join-Path $env:TEMP "jhunt-py311"
   uv venv $v --python 3.11
   uv pip install -r requirements.lock --python "$v\Scripts\python.exe"
   & "$v\Scripts\python.exe" -c "import sys, sphinx; print(sys.version_info[:2], sphinx.__version__)"   # expect (3, 11) 9.0.4
   & "$v\Scripts\python.exe" -m unittest discover tests                                               # expect 204 OK
   Remove-Item -Recurse -Force $v -Confirm:$false
   ```
   This reads from PyPI over the network, which is allowed: it is not production. Python 3.11.16 is already installed locally through uv.
5. **Local suite:** run `uv run python -m unittest discover tests`. Expect **204 passed** (the reviewer measured a baseline of 203, plus 1 new test).
6. **Em dashes:** `Select-String -Path AGENTS.md,tests\test_lockfile.py,docs\contexts\task-ledger.md -Pattern ([char]0x2014)` must not match any line this task added.
7. **Web:** `web/` is not touched, so lint and build are not required.

## Not verified by this plan
- A real GitHub Actions run. Triggering the workflow (`gh workflow run`) needs explicit approval. The first confirmation in CI will be the next scheduled 01:00 UTC run or a run you start yourself.
- Linux wheel availability is covered by `--universal` markers, but this plan only tests the install on Windows.
