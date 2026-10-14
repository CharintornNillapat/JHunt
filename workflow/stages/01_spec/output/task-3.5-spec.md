# Plan: Task 3.5 — Market Analytics Interactive Category Filter & Data Export in AnalyticsCharts.tsx

**Date:** 2026-10-14  
**Task ID:** 3.5  
**Reference:** `docs/contexts/task-ledger.md` (Phase 3), `AGENTS.md` (Definitions & Invariants), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Transform `AnalyticsCharts.tsx` from a static vertical dashboard into an interactive, high-craft telemetry explorer by introducing an accessible category filter tab bar (allowing users to view all metrics or isolate Languages, Cloud Infrastructure, Compensation, or Databases & Frameworks) and client-side data export capabilities (formatted CSV with UTF-8 BOM and structured JSON), strictly enforcing antislop Mode 1 (DURING) and WCAG AA accessibility standards.

---

## antislop & UX Protocol (Mode 1: DURING)

This specification strictly adheres to the `antislop` suite (`antislop`, `antislop-ui`, `antislop-layoutmobile`, `antislop-human`, `antislop-copywriting`, `antislop-code`):

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) anywhere in UI copy, button labels, tooltips, chart headers, placeholders, or export filenames.
   - Use colons, commas, periods, or parentheses instead.
2. **R-03 (Mobile Responsiveness & Tap Targets)**:
   - All interactive elements (category filter tabs, CSV export button, JSON export button) must maintain $\ge 44\text{px}$ touch targets on mobile viewports (`min-h-[44px]`).
   - Category filter tabs must smoothly scroll horizontally on narrow mobile screens (`overflow-x-auto no-scrollbar`) without causing page-level horizontal overflow.
   - Clean column reflow: 1-column on mobile viewports ($< 768\text{px}$), 2-column on desktop viewports ($\ge 1024\text{px}$).
3. **R-25 (Color Contrast: WCAG AA)**:
   - All text, labels, and badges must meet WCAG AA contrast $\ge 4.5:1$ against dark surfaces (`#08080a`, `#0c0d12`, `zinc-900`, `zinc-950`).
   - Active filter tab: `bg-cyan-500/15 text-cyan-300 border-cyan-500/40` (contrast ratio $> 9:1$).
   - Inactive filter tab: `bg-zinc-900/80 text-zinc-400 hover:text-zinc-200 border-white/[0.08]` (contrast ratio $> 4.8:1$).
   - Export buttons: `bg-zinc-900 text-zinc-300 hover:text-white border-white/10 hover:border-cyan-500/40` (contrast ratio $> 7.5:1$).
4. **R-26 (Interactive Elements & No Dead Controls)**:
   - Export buttons must execute hermetic client-side `Blob` downloads using `URL.createObjectURL` with immediate visual feedback (`Exported!` indicator for 2 seconds).
   - Category tabs must immediately update the active view with zero layout shifts or unnecessary re-renders.
5. **R-27 (UI States)**:
   - Explicit default, active, hover, focus-visible, and downloaded states.
   - Maintain the existing empty state for compensation data if $n < 5$ postings are available.
6. **R-32 (Keyboard Accessibility & Screen Readers)**:
   - Category tablist must implement WAI-ARIA tab pattern: `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, and `id`.
   - Keyboard arrow navigation: Left/Right (and Up/Down) arrow keys cycle between tabs; Home and End jump to first and last tabs; Enter and Space activate.
   - Visible focus indicators: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950`.
   - Screen-reader live region (`aria-live="polite"`) announcing tab changes and export completion.
7. **R-35 (Craftsmanship Verification)**:
   - Verified via Next.js production build (`npm run build`), ESLint (`npm run lint`), hermetic Python tests, and cross-viewport responsive check.

---

## Current Behavior (Evidence)

1. **Static Monolithic Layout (`web/src/components/AnalyticsCharts.tsx:116-395`)**:
   - `AnalyticsCharts` statically renders all 4 sections consecutively:
     - 2-column grid: Language Demand Index (`BarChart`) and Cloud Infrastructure Share (`PieChart`).
     - Full-width card: Top Compensated Skills (`BarChart` + quick pills).
     - 2-column grid: Persistence & Storage Engines and Application Frameworks (CSS bar lists).
   - Users cannot filter or isolate specific clusters (such as focusing solely on Backend Languages or Cloud & Infrastructure). On mobile screens, this causes a lengthy 4-screen vertical scroll.

2. **No Data Export Capability (`web/src/components/AnalyticsCharts.tsx`)**:
   - Market intelligence data calculated by Turso is displayed visually in SVG charts, but users cannot export or download the underlying dataset for offline analysis, spreadsheet calculation, or portfolio research.
   - There are no CSV or JSON export buttons.

3. **Missing Category Navigation HUD**:
   - No interactive filter toolbar exists above the chart panels to give users high-level cluster counts and quick navigation.

---

## Changes

### 1. Interactive Category Filter Architecture
- **File**: `web/src/components/AnalyticsCharts.tsx`
- **Category Definitions**:
  ```typescript
  type AnalyticsCategory = "all" | "languages" | "cloud" | "compensation" | "frameworks";

  interface CategoryTabConfig {
    id: AnalyticsCategory;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    count?: number;
  }
  ```
  Categories configured:
  1. `all`: "All Metrics" (icon: `Layers`, count: total metrics displayed).
  2. `languages`: "Languages" (icon: `Code2`, count: `analytics.languages.length`).
  3. `cloud`: "Cloud & Infra" (icon: `Cloud`, count: `analytics.clouds.length`).
  4. `compensation`: "Compensation" (icon: `Banknote`, count: `analytics.top_compensated_skills?.length ?? 0`).
  5. `frameworks`: "Data & Frameworks" (icon: `Database`, count: `analytics.databases.length + analytics.frameworks.length`).

- **Category Filter HUD Component**:
  - Render a top control bar above the charts containing the tab list on the left and the export button group on the right.
  - Implement full WAI-ARIA tab pattern:
    - Container: `<div role="tablist" aria-label="Market analytics category filters" className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">`
    - Tab buttons:
      - `role="tab"`
      - `id={`tab-${category.id}`}`
      - `aria-selected={activeCategory === category.id}`
      - `aria-controls={`panel-${category.id}`}`
      - `tabIndex={activeCategory === category.id ? 0 : -1}`
      - `min-h-[44px]` touch target on mobile viewports.
  - Keyboard listener:
    - Support Left/Right arrow keys to cycle focus and selection across tabs.
    - Support Home and End keys to jump to the first and last tabs.

### 2. Panel Filtering & Responsive Layout
- When `activeCategory === "all"`:
  - Render the standard comprehensive dashboard (Languages + Cloud 2-column, Compensation full-width, Databases + Frameworks 2-column).
- When a specific category is active:
  - Isolate the selected chart panel and expand it cleanly:
    - `"languages"`: Language Demand Index rendered in a full-width SpotlightCard with expanded height (`h-80`) for enhanced readability.
    - `"cloud"`: Cloud & Containerization Share rendered in a full-width SpotlightCard with expanded donut radius and spacious grid legend.
    - `"compensation"`: Top Compensated Skills rendered in a full-width SpotlightCard with salary benchmarks.
    - `"frameworks"`: Persistence & Storage Engines and Application Frameworks rendered side by side (or stacked on mobile).
  - Wrap panel in `<div role="tabpanel" id={`panel-${activeCategory}`} aria-labelledby={`tab-${activeCategory}`}>`.

### 3. Client-Side Data Export (CSV & JSON)
- **File**: `web/src/components/AnalyticsCharts.tsx`
- **CSV Generator (`exportMarketDataAsCSV`)**:
  - Structure columns: `Category,Skill_Name,Demand_Count,Demand_Percentage,Avg_Salary_THB,Sample_Count`.
  - Rows:
    - Languages: `"Language",item.name,item.count,item.percentage,"",""`
    - Cloud & Containerization: `"Cloud & Infra",item.name,item.count,item.percentage,"",""`
    - Persistence Engines: `"Database",item.name,item.count,item.percentage,"",""`
    - Application Frameworks: `"Framework",item.name,item.count,item.percentage,"",""`
    - Compensation: `"Compensation",item.skill,"","",item.avg_salary,item.sample_count`
  - Prepend UTF-8 BOM (`\uFEFF`) to prevent character encoding corruption in Microsoft Excel and Windows applications.
  - Robust CSV escaping: values containing quotes, commas, or line breaks wrapped in double quotes, with internal quotes escaped as `""`.
  - Trigger download with filename `jhunt-market-analytics-YYYY-MM-DD.csv`.
- **JSON Generator (`exportMarketDataAsJSON`)**:
  - Structure:
    ```json
    {
      "metadata": {
        "source": "JHunt Thailand Tech Market Telemetry",
        "exported_at": "ISO-8601 string",
        "total_jobs": number,
        "total_skills": number,
        "total_blueprints": number
      },
      "languages": [...],
      "clouds": [...],
      "top_compensated_skills": [...],
      "databases": [...],
      "frameworks": [...]
    }
    ```
  - Formatted with 2-space indentation.
  - Trigger download with filename `jhunt-market-analytics-YYYY-MM-DD.json`.
- **Hermetic Download Helper**:
  ```typescript
  function downloadBlob(content: string, filename: string, mimeType: string) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  ```
- **Export UX Feedback**:
  - State: `exportStatus: "idle" | "csv-success" | "json-success"`.
  - When triggered, show a green `Check` icon and label "Exported!" for 2000ms.
  - Maintain $\ge 44\text{px}$ touch target on mobile viewports.
  - Screen reader announcement: `<div className="sr-only" aria-live="polite">{announcement}</div>`.

---

## Verification Plan

1. **Static Analysis & Types**:
   - `cd web; npm run lint` passes with 0 errors and 0 warnings.
   - `cd web; npm run build` compiles clean Next.js static and dynamic bundles.
2. **Python Test Suite**:
   - `uv run python -m unittest discover tests` passes (hermetic, zero network).
3. **Accessibility & antislop Audit**:
   - Zero em dashes (`—`) across all copy, tooltips, buttons, and generated filenames.
   - Interactive touch targets $\ge 44\text{px}$ on mobile screens.
   - WAI-ARIA tab navigation: Left/Right arrows cycle tabs, Enter/Space selects, visible focus rings.
   - Screen-reader announcements for tab switching and data exports.
   - WCAG AA contrast ratio $\ge 4.5:1$ across all tab states, buttons, and badges.
4. **Data Export Integrity**:
   - CSV export verified: starts with `\uFEFF`, contains valid comma-separated rows, all 5 categories populated.
   - JSON export verified: valid JSON structure matching `MarketAnalytics` interface with ISO-8601 timestamp.
