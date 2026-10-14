# Plan: Task 4.2: Actionable Solo Blueprint Schema Depth (walking_skeleton, acceptance_tests, out_of_scope) in schemas, ideation_engine, and exporter

**Date:** 2026-10-14  
**Task ID:** 4.2  
**Reference:** `docs/contexts/task-ledger.md` (Phase 4), `AGENTS.md` (Definitions & Invariants), `docs/audits/2026-10-11-architecture-feasibility.md` (Priority 4: Solo-Feasible Blueprints), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Elevate the technical depth and actionable feasibility of generated portfolio blueprints by enforcing strict schema contracts for `walking_skeleton` (step 1 thin slice), `acceptance_tests` (3 to 5 falsifiable local pytest/Locust/Playwright scenarios aliased with legacy `verification`), and `out_of_scope` (explicit anti-goals), updating prompt synthesis instructions, refreshing curated offline archetypes, standardizing markdown export rendering, and polishing dark-mode checklist presentation in `BlueprintReader.tsx`, strictly adhering to antislop Mode 1 (DURING) and WCAG AA standards.

---

## antislop & UX Protocol (Mode 1: DURING)

This specification strictly applies the `antislop` suite (`antislop`, `antislop-ui`, `antislop-layoutmobile`, `antislop-human`, `antislop-copywriting`, `antislop-code`):

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) anywhere in schema descriptions, system prompts, markdown section headers, fallback archetypes, or comments.
   - Use colons, commas, periods, or parentheses instead.
2. **R-03 (Mobile Responsiveness & Tap Targets)**:
   - Ordered walking skeleton steps and task checklist items must reflow cleanly without text truncation or horizontal overflow on narrow mobile screens ($320\text{px}$ to $428\text{px}$).
3. **R-17 / R-36 / R-38 (Honest Technical Architecture & Depth)**:
   - Walking skeleton Step 1 must always be a concrete, runnable thin end-to-end slice (request in, datastore row committed, result readable).
   - Acceptance tests must be falsifiable local checks stated as counts, invariants, or assertions (e.g. "100 duplicate deliveries produce exactly 1 ledger row").
   - Strictly forbid fake target metrics: zero latency percentiles ("p99 < 5ms"), throughput numbers ("10,000 rps"), or uptime claims ("99.99%").
   - Explicit `out_of_scope` list prevents speculative architectural bloat (no microservices, no multi-region, no Kafka when a table queue suffices).
4. **R-25 (Color Contrast: WCAG AA)**:
   - Checklist checkboxes and rendered markdown text must meet WCAG AA contrast $\ge 4.5:1$ against dark surfaces (`#08080a`, `#0c0d12`, `zinc-900`).
   - Checkbox border: `border-white/20`, accent color: `accent-cyan-400` ($> 7:1$).
5. **R-26 (Interactive Elements & No Dead Controls)**:
   - Checkboxes are displayed as clean, read-only checklist items; anchor links to `## walking-skeleton`, `## acceptance-tests`, and `## out-of-scope` must navigate smoothly.
6. **R-27 (UI & Backward Compatibility States)**:
   - Pydantic v2 `AliasChoices("acceptance_tests", "verification")` and property getters/setters ensure 100% backward compatibility for existing database records and legacy test fixtures.
7. **R-32 (Keyboard Accessibility)**:
   - Screen-reader accessible checkbox labels (`aria-label="Acceptance test item"`).
8. **R-35 (Craftsmanship Verification)**:
   - Verified via Next.js Turbopack build (`npm run build`), ESLint (`npm run lint`), and hermetic Python unit tests (`uv run python -m unittest discover tests`).

---

## Current Behavior (Evidence)

1. **Inconsistent Schema Naming (`src/extractor/schemas.py:116-120`)**:
   - `ProjectIdeaSpec` currently defines `verification: List[str]` instead of the standardized `acceptance_tests: List[str]`, despite architectural feasibility recommendations (`docs/audits/2026-10-11-architecture-feasibility.md:119`).
   - `walking_skeleton` and `out_of_scope` have basic descriptions but lack explicit field-level structural contracts.

2. **System Instruction Field Terminology (`src/generator/ideation_engine.py:20-43`)**:
   - `IDEATION_SYSTEM_INSTRUCTION` mentions `verification` rather than `acceptance_tests`.
   - The three fallback archetypes (`_BACKEND_FALLBACK`, `_DATA_FALLBACK`, `_FRONTEND_FALLBACK`) instantiate `verification=[...]` instead of `acceptance_tests=[...]`.

3. **Markdown Exporter Header (`src/generator/markdown_exporter.py:98-106`)**:
   - Section header is hardcoded as `## Local Verification` rather than `## Acceptance Tests`.
   - Does not explicitly support both `acceptance_tests` and legacy `verification` gracefully.

4. **Web Checklist Checkbox Styling (`web/src/components/BlueprintReader.tsx:440-470`)**:
   - `ReactMarkdown` uses `remark-gfm` which renders standard HTML `<input type="checkbox" disabled />`. Without custom styling, browser defaults render white boxes that look unstyled against the dark obsidian palette.

---

## Changes

### 1. Schema Evolution & Backward Compatibility
- **File**: `src/extractor/schemas.py`
- Import `AliasChoices` from `pydantic`.
- Update `ProjectIdeaSpec`:
  ```python
  from pydantic import AliasChoices, BaseModel, ConfigDict, Field

  class ProjectIdeaSpec(BaseModel):
      """
      Buildable portfolio project spec: one core engineering problem, one service,
      one datastore, and checks a single developer can run locally.
      """
      model_config = ConfigDict(
          extra="ignore",
          str_strip_whitespace=True,
          populate_by_name=True,
      )

      title: str = Field(..., description="Specific project title naming the core problem")
      domain_industry: str = Field(..., description="Thailand business context (e.g. 'FinTech / PromptPay payments')")
      core_problem: str = Field(
          ...,
          description="The single engineering problem the project exists to solve, in one or two sentences",
      )
      target_tech_stack: List[str] = Field(
          default_factory=list,
          description="Only the technologies the core problem needs, without version numbers",
      )
      system_boundary: str = Field(
          ...,
          description="Exactly one service and one primary datastore (plus at most one cache or queue if the problem needs it). State what is in and out of scope",
      )
      walking_skeleton: List[str] = Field(
          default_factory=list,
          description="Ordered build steps (typically 3 to 7). Step 1 is a thin end-to-end slice that runs locally; each later step adds one capability",
      )
      contracts: str = Field(
          ...,
          description="Typed request, response and event contracts as Pydantic models or OpenAPI paths with status codes",
      )
      database_schema: str = Field(..., description="Tables, keys and constraints that enforce the core invariant")
      failure_modes: List[FailureMode] = Field(default_factory=list)
      acceptance_tests: List[str] = Field(
          default_factory=list,
          validation_alias=AliasChoices("acceptance_tests", "verification"),
          description="3 to 5 falsifiable local checks (pytest, Locust, Playwright) with concrete pass conditions such as counts or invariants. No latency percentiles or throughput targets",
      )
      out_of_scope: List[str] = Field(
          default_factory=list,
          description="Tempting additions deliberately excluded to keep the project buildable by one developer in 2 to 4 weeks",
      )
      difficulty: str = Field(
          default="Intermediate",
          description="'Junior', 'Intermediate', or 'Advanced'",
      )

      @property
      def verification(self) -> List[str]:
          """Backward-compatible alias for acceptance_tests."""
          return self.acceptance_tests

      @verification.setter
      def verification(self, val: List[str]) -> None:
          self.acceptance_tests = val
  ```

### 2. Ideation Engine Prompt & Fallback Archetypes
- **File**: `src/generator/ideation_engine.py`
- Update `IDEATION_SYSTEM_INSTRUCTION`:
  - Rename `- verification:` to `- acceptance_tests: 3 to 5 falsifiable checks runnable locally with pytest, Locust or Playwright, stated as counts or invariants (for example '100 duplicate deliveries produce exactly 1 ledger row'). Verification checks must hold true under any request interleaving (no flaky assumptions about scheduling order). For in-test concurrency, specify asyncio.gather with httpx.AsyncClient or a thread pool; never rely on pytest-xdist for in-test concurrency assertions.`
  - Clarify `- out_of_scope: 3 to 5 tempting additions deliberately excluded to keep the project buildable by one developer on a laptop in two to four weeks.`
- Update Fallback Specs (`_BACKEND_FALLBACK`, `_DATA_FALLBACK`, `_FRONTEND_FALLBACK`):
  - Pass `acceptance_tests=[...]` instead of `verification=[...]`.

### 3. Markdown Exporter Rendering
- **File**: `src/generator/markdown_exporter.py`
- In `render_spec_markdown()`:
  - Extract tests: `tests_list = spec.acceptance_tests or spec.verification or []`.
  - Format acceptance tests:
    ```python
    acceptance_tests_md = "\n".join(f"- [ ] {check}" for check in tests_list)
    ```
  - Standardize section header to `## Acceptance Tests`:
    ```markdown
    ## Walking Skeleton

    {skeleton_md}

    ## Contracts

    {spec.contracts}

    ## Data Model

    {spec.database_schema}

    ## Failure Modes & Recovery

    {failures_md}

    ## Acceptance Tests

    {acceptance_tests_md}

    ## Out of Scope

    {out_of_scope_md}
    ```

### 4. Web Component Polish: Dark-Themed Checklists
- **File**: `web/src/components/BlueprintReader.tsx`
- Add custom `input` component renderer to `ReactMarkdown.components`:
  ```tsx
  input(props) {
    if (props.type === "checkbox") {
      return (
        <input
          type="checkbox"
          checked={props.checked}
          readOnly
          aria-label="Acceptance test item"
          className="h-3.5 w-3.5 rounded border border-white/20 bg-zinc-900 text-cyan-400 accent-cyan-400 focus:ring-0 mr-2 inline-block align-middle cursor-default"
        />
      );
    }
    return <input {...props} />;
  }
  ```

### 5. Unit Tests Parity
- **File**: `tests/test_generator.py`
  - Update `make_spec()` to test both `acceptance_tests` and `verification` aliases.
  - Update heading assertion in `test_markdown_template_structure` to check `"## Acceptance Tests"`.
  - Add test asserting `spec.verification` and `spec.acceptance_tests` access the same list.

---

## Verification Plan

1. **Python Unit Tests**:
   - `uv run python -m unittest discover tests`
   - Assert all 198+ hermetic unit tests pass with zero network calls.
2. **Web Build & Lint**:
   - `cd web; npm run lint` passes with 0 errors and 0 warnings.
   - `cd web; npm run build` compiles clean Turbopack bundles with styled checkboxes in `BlueprintReader`.
3. **antislop & Quality Audit**:
   - Zero em dashes (`—`) across all updated prompt strings, schemas, fallback specs, and markdown sections.
   - WCAG AA contrast on checklist items (`accent-cyan-400`, `border-white/20`).
   - Clean TOC headings navigation (`#walking-skeleton`, `#acceptance-tests`, `#out-of-scope`).
