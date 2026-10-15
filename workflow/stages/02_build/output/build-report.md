# Build Report: Task 7.1 - Recompile requirements.lock for CI Python (3.11)

## Summary
- **Task ID**: 7.1
- **Status**: BUILT
- **Target**: Recompile `requirements.lock` using `--python-version 3.11` to fork `sphinx` to 9.0.4 for Python < 3.12, update compilation documentation in `AGENTS.md`, add hermetic regression guard test `tests/test_lockfile.py`, and record task status in `docs/contexts/task-ledger.md`.

---

## 1. Deliverables & Modified Files

### 1.1 `requirements.lock`
- Recompiled in-place using `uv pip compile requirements.txt --universal --python-version 3.11 -o requirements.lock`.
- Resolved `sphinx` fork: `sphinx==9.0.4 ; python_full_version < '3.12'` and `sphinx==9.1.0 ; python_full_version >= '3.12'`.
- All other package versions preserved with zero drift.

### 1.2 `AGENTS.md`
- Updated compilation command and documentation at line 33-34:
  `# Updating dependencies (recompile lockfile from requirements.txt; 3.11 = CI Python, keep in sync with scraper_cron.yml)`
  `uv pip compile requirements.txt --universal --python-version 3.11 -o requirements.lock`

### 1.3 `tests/test_lockfile.py` (New File)
- Added `TestLockfileTargetsCiPython.test_lock_compiled_for_ci_python_version`.
- Fast hermetic test asserting that the Python version pinned in `.github/workflows/scraper_cron.yml` matches `--python-version` declared in `requirements.lock` header.
- Verified failure on unpatched lockfile and pass on patched lockfile.

### 1.4 `docs/contexts/task-ledger.md`
- Added Phase 7 (`Phase 7: Build & Dependency Hygiene (P7)`) with Task 7.1 checked under `Remediation Plan (2026-10-12)`.

---

## 2. Verification & Quality Gates

### 2.1 Test-First Regression Verification
- Command: `uv run python -m unittest tests.test_lockfile -v`
- Result before recompile: FAIL (`AssertionError: unexpectedly None : requirements.lock was compiled without --python-version`).
- Result after recompile: PASS (`1 test in 0.001s, OK`).

### 2.2 Full Python Test Suite
- Command: `uv run python -m unittest discover tests`
- Result: **204 passed in 13.433s** (OK, 0 failures, 0 errors, completely hermetic).

### 2.3 Throwaway Python 3.11 Environment Verification
- Created isolated throwaway virtual environment under Python 3.11.16:
  - Installed `requirements.lock` cleanly: 54 packages installed in 862ms.
  - Verified `sphinx` resolves to `9.0.4`: `(3, 11) 9.0.4`.
  - Executed full test suite under Python 3.11: **204 passed in 13.936s** (OK).
  - Cleanly removed throwaway virtual environment.

### 2.4 Compilation Idempotency
- Re-ran compile command on existing output file; verified `git diff requirements.lock` remained strictly identical.

### 2.5 antislop Copywriting Hygiene (Rule R-02)
- Programmatic check for em dashes (`\u2014`) across all touched files and this build report: 0 em dashes found.

---

## 3. What Was NOT Verified
- Triggering live GitHub Actions workflow (`gh workflow run scraper_cron.yml`) per `AGENTS.md` boundaries.
- Live Linux wheel installation on runner (covered via `--universal` marker resolution).
