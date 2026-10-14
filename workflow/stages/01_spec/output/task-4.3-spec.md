# Plan: Task 4.3: Deterministic Dependency Lockfile (generate requirements.lock with uv pip compile and verify hermetic tests)

**Date:** 2026-10-14  
**Task ID:** 4.3  
**Reference:** `docs/contexts/task-ledger.md` (Phase 4), `AGENTS.md` (Definitions & Invariants), `docs/audits/2026-10-11-architecture-feasibility.md` (Priority 5: Reproducibility), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Generate a deterministic, universal dependency lockfile (`requirements.lock`) from `requirements.txt` using `uv pip compile --universal`, freezing exact versions and platform markers for all direct and transitive dependencies across Windows and Linux, and verify that the hermetic Python unit test suite passes completely offline with zero network access.

---

## antislop & Engineering Protocol (Mode 1: DURING)

This specification strictly adheres to the `antislop` suite (`antislop`, `antislop-code`, `antislop-copywriting`) and repository invariants:

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) anywhere in documentation, lockfile header comments, command guides, or commit specifications.
   - Use colons, commas, periods, or parentheses instead.
2. **R-35 (Craftsmanship Verification)**:
   - Full dependency graph reproducibility: every package resolution pinned to an exact version.
   - Hermetic verification: all unit tests run without network access, using mocked external clients.
3. **Repository Guardrails & Invariants (`AGENTS.md`)**:
   - **No new dependencies**: Pinned dependencies must reflect only the resolution of existing packages declared in `requirements.txt`.
   - **Workflow Guardrail**: In accordance with `AGENTS.md` ("Stop and ask first: pushing changes to `.github/workflows/`"), `.github/workflows/scraper_cron.yml` is not modified directly in this task; the recommended CI diff is documented in this plan for the developer to review and apply.
   - **Platform Portability**: Use `--universal` to generate platform-agnostic environment markers (`sys_platform == 'win32'`, `platform_python_implementation != 'PyPy'`), ensuring identical deterministic behavior on Windows (developer laptop) and Linux (`ubuntu-latest` CI runner).

---

## Current Behavior (Evidence)

1. **Unpinned Upstream Requirements (`requirements.txt:1-6`)**:
   - `requirements.txt` declares minimum versions with open-ended `>=` constraints:
     ```
     requests>=2.32.0
     python-dotenv>=1.0.0
     pydantic>=2.0.0
     google-genai>=0.1.0
     libsql-client>=0.3.0
     ```
   - Each `uv pip install -r requirements.txt` or CI run can resolve different transitive dependencies (such as newer releases of `anyio`, `httpx`, `aiohttp`, or `pydantic-core`), exposing the pipeline to unexpected upstream breakage.

2. **Missing Committed Lockfile**:
   - There is currently no `requirements.lock` in the repository root.
   - `docs/audits/2026-10-11-architecture-feasibility.md:123` specifically flags this reproducibility gap:
     `"Priority 5: reproducibility: Pin google-genai and commit a lock (pip freeze > requirements.lock, installed in CI)."`

3. **Developer Setup Documentation (`AGENTS.md:31`)**:
   - Setup instructions instruct developers to install from unpinned `requirements.txt`.

---

## Changes

### 1. Universal Lockfile Compilation
- **Target File**: `requirements.lock`
- **Command**:
  ```powershell
  uv pip compile requirements.txt --universal -o requirements.lock
  ```
- **Technical Characteristics**:
  - **Direct Dependencies Pinned**:
    - `requests==2.34.2`
    - `python-dotenv==1.2.4`
    - `pydantic==2.14.1`
    - `google-genai==2.30.1`
    - `libsql-client==0.3.1`
  - **Transitive Dependencies Pinned**:
    - Complete closure of all 49 transitive libraries (`aiohttp`, `anyio`, `cryptography`, `google-auth`, `httpx`, `pydantic-core`, `typing-extensions`, etc.).
  - **Environment Markers**:
    - Universal markers ensure packages like `colorama` are installed only on `sys_platform == 'win32'` while packages with platform wheels (`cffi`, `pycparser`) specify correct implementation markers.

### 2. Developer Documentation Update
- **File**: `AGENTS.md`
- Update the Setup instructions in the `Commands (PowerShell)` section:
  ```powershell
  # Setup (deterministic install from lockfile)
  uv venv; .venv\Scripts\activate; uv pip install -r requirements.lock

  # Updating dependencies (recompile lockfile from requirements.txt)
  uv pip compile requirements.txt --universal -o requirements.lock
  ```

### 3. Recommended CI Configuration (For Developer Reference)
- In `.github/workflows/scraper_cron.yml`, when the developer chooses to update the workflow:
  ```yaml
        # Set up uv caching for requirements.lock
        - name: Set up uv
          uses: astral-sh/setup-uv@v5
          with:
            enable-cache: true
            cache-dependency-glob: "requirements.lock"

        # Install from deterministic lockfile
        - name: Install dependencies
          run: |
            uv venv
            uv pip install -r requirements.lock
  ```

---

## Verification Plan

1. **Lockfile Generation**:
   - `uv pip compile requirements.txt --universal -o requirements.lock` completes cleanly with 0 resolution errors.
2. **Hermetic Test Suite**:
   - Run `uv run python -m unittest discover tests`.
   - Verify all 199 hermetic unit tests pass with 0 failures and 0 errors.
3. **Clean Web Build & Lint**:
   - `cd web; npm run lint` passes with 0 errors and 0 warnings.
   - `cd web; npm run build` compiles cleanly.
4. **antislop Audit**:
   - Zero em dashes (`—`) across all modified documentation and lockfile comments.
