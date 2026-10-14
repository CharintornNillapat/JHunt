# Plan: Task 5.1: CI Lockfile Integration in .github/workflows/scraper_cron.yml

**Date:** 2026-10-14  
**Task ID:** 5.1  
**Reference:** `docs/contexts/task-ledger.md` (Phase 5), `AGENTS.md` (Stop and ask first & Invariants), `docs/audits/2026-10-11-architecture-feasibility.md` (Priority 5: Reproducibility), `antislop` Skill Suite (Mode 1 DURING)  

---

## Goal

Integrate the deterministic universal dependency lockfile (`requirements.lock`) into the GitHub Actions CI pipeline (`.github/workflows/scraper_cron.yml`) by updating the `astral-sh/setup-uv@v5` cache invalidation glob and the dependency installation command to use `requirements.lock`, synchronize setup documentation in `README.md`, and verify offline test suites and web compilation.

---

## antislop & Engineering Protocol (Mode 1: DURING)

This specification strictly adheres to the `antislop` suite (`antislop`, `antislop-code`, `antislop-copywriting`) and repository invariants:

1. **R-02 (Copywriting)**:
   - Zero em-dashes anywhere in workflow comments, markdown documentation, or commit specifications.
   - Use colons, commas, periods, or parentheses instead.
2. **R-35 (Craftsmanship Verification)**:
   - Full dependency graph reproducibility: CI runner installs identical frozen package versions as the local developer environment.
   - Hermetic verification: all unit tests run without network access, using mocked external clients.
3. **Repository Guardrails & Invariants (`AGENTS.md`)**:
   - **Stop and ask first**:
     "Never run them unless I approve in the current conversation: gh workflow run|disable|enable, or pushing changes to .github/workflows/."
     The Builder agent edits `.github/workflows/scraper_cron.yml` locally, but MUST NOT trigger `gh workflow run`, modify remote GitHub settings, or execute `git push`.
   - **No new dependencies**:
     No new packages or actions added; retains `astral-sh/setup-uv@v5` and standard `uv` commands.

---

## Current Behavior (Evidence)

1. **CI Cache Invalidation on Loose Requirements (`.github/workflows/scraper_cron.yml:47-50`)**:
   - The workflow configures `astral-sh/setup-uv@v5` to cache dependencies based on `requirements.txt`:
     ```yaml
     - name: Set up uv
       uses: astral-sh/setup-uv@v5
       with:
         enable-cache: true
         cache-dependency-glob: "requirements.txt"
     ```
   - Because `requirements.txt` only specifies unpinned minimum bounds (`requests>=2.32.0`, `google-genai>=0.1.0`), modifications to transitive package resolutions do not invalidate the action cache.

2. **Unpinned Dependency Installation in CI (`.github/workflows/scraper_cron.yml:55-59`)**:
   - The install step currently executes:
     ```yaml
     - name: Install dependencies
       run: |
         uv venv
         uv pip install -r requirements.txt
     ```
   - Running `uv pip install -r requirements.txt` allows the CI environment to resolve arbitrary upstream minor and patch releases, introducing non-deterministic behavior and potential pipeline breakage.

3. **Stale Quickstart Documentation (`README.md:214, 216`)**:
   - In `README.md`, the backend installation instructions still direct users to run `uv pip install -r requirements.txt` instead of the newly committed `requirements.lock`.
   - The test count in `README.md:216` references 128 tests rather than the current 199 tests.

---

## Changes

### 1. CI Workflow Update
- **Target File**: `.github/workflows/scraper_cron.yml`
- **Location**: Lines 47-59
- **Changes**:
  1. Change `cache-dependency-glob: "requirements.txt"` to `cache-dependency-glob: "requirements.lock"`.
  2. Change `uv pip install -r requirements.txt` to `uv pip install -r requirements.lock`.

```yaml
      # ── 4. Set up uv and Python ───────────────────────────────────
      - name: Set up uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
          cache-dependency-glob: "requirements.lock"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -r requirements.lock
```

### 2. Documentation Synchronization
- **Target File**: `README.md`
- **Location**: Section 1 under "Backend Ingestion Pipeline" (lines 211-218)
- **Changes**:
  1. Update install instruction to `uv pip install -r requirements.lock`.
  2. Update hermetic test suite comment from `(128 tests)` to `(199 tests)`.

### 3. Task Ledger Tracking
- **Target File**: `docs/contexts/task-ledger.md`
- **Location**: Add Phase 5 heading and record task completion:
  ```markdown
  #### Phase 5: Production Operations, Automation & Reliability (P5)
  - [x] **Task 5.1: CI Lockfile Integration in .github/workflows/scraper_cron.yml** (Pin CI uv dependency caching and installation to requirements.lock, align README setup commands).
  ```

---

## Verification Plan

1. **Workflow Integrity**:
   - Verify indentation and syntax in `.github/workflows/scraper_cron.yml`.
   - Ensure step structure remains intact.
2. **Hermetic Test Suite**:
   - Run `uv run python -m unittest discover tests`.
   - Verify all 199 hermetic unit tests pass with 0 failures and 0 errors.
3. **Web Build & Lint**:
   - Run `cd web; npm run lint ; npm run build`.
   - Verify clean TypeScript compilation and 0 ESLint warnings.
4. **antislop Copywriting Audit**:
   - Verify zero em-dashes across all modified files (`.github/workflows/scraper_cron.yml`, `README.md`, `docs/contexts/task-ledger.md`).
5. **Safety Gate Audit**:
   - Confirm no `gh workflow run`, remote CI triggers, or git pushes were executed.
