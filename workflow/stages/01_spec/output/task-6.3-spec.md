# Plan: Task 6.3: Market Analytics & Skill Gap Matcher Telemetry Polish

**Date:** 2026-10-14  
**Task ID:** 6.3  
**Reference:** `docs/contexts/task-ledger.md` (Phase 6), `web/src/components/SkillGapMatcher.tsx`, `web/src/components/AnalyticsCharts.tsx`, `web/src/components/AnalyticsSkeleton.tsx`, Design Skill Suite (`impeccable`, `taste-skill`, `emil-design-eng`, `antislop-ui`, `antislop-layoutmobile`, `antislop-copywriting`)

---

## Goal

Redesign and polish the data density, visual hierarchy, and mobile ergonomics of the Market Analytics dashboard (`AnalyticsCharts.tsx`, `AnalyticsSkeleton.tsx`) and talent benchmark tool (`SkillGapMatcher.tsx`), eliminating generic AI card nesting, enforcing strict alignment with `font-mono tabular-nums` across all salary/ROI/coverage telemetry, and refining chart visual restraint and skeleton loading states.

---

## antislop & Engineering Protocol Compliance

This specification strictly applies the repository invariants and design standards:

1. **Rule R-02 (Zero Em Dashes Everywhere)**:
   - Zero em dashes in code, CSS, comments, specs, build reports, or reviews.
   - Use colons, hyphens, commas, periods, or parentheses instead.

2. **Aesthetic Restraint & Anti-Slop Layout (`taste-skill`, `antislop-ui`)**:
   - Eliminate redundant card-in-card nesting: replace nested boxy containers with unified Obsidian slabs (`bg-[#0c0d12] border border-white/[0.07] rounded-xl`) and clean spatial dividers (`border-white/[0.06]`).
   - Remove loud neon drop-shadows and garish glows: replace heavy colored drop-shadows with crisp surgical cyan and emerald borders (`border-cyan-500/30`, `border-emerald-500/40`).
   - Unified telemetry palette: surgical cyan (`#06b6d4`), indigo (`#6366f1`), sky (`#38bdf8`), emerald (`#10b981`), and muted zinc (`#71717a`).

3. **Strict Alignment & Tabular Typography (`impeccable`)**:
   - Every metric, percentage, sample size (`n=X`), and currency value (`฿X/mo`) must render with `font-mono tabular-nums` to eliminate jitter and misalignment.
   - Compensation table and benchmark lists must adhere to strict tabular columns (Skill, Average Salary, Sample Size, Demand Share).

4. **Tactile Interaction & Micro-Interactions (`emil-design-eng`)**:
   - Quick-add skills chips, role presets, and simulation buttons: tactile `active:scale-95 transition-all duration-150`.
   - Category filter tabs in analytics: snappy spring transition `{ type: "spring", stiffness: 380, damping: 28 }` with `active:scale-95`.
   - Data export buttons (CSV / JSON): tactile press feedback and clear success states.

5. **Mobile Ergonomics (`antislop-layoutmobile`)**:
   - Compact mobile HUD layout: side-by-side RadialGauge and reach metrics on viewports under 640px.
   - Touch targets: minimum 44px height on all interactive simulation buttons, preset chips, and filter tabs.
   - Zero horizontal overflow across mobile viewports down to 390px.

---

## Current Behavior (Evidence)

1. **Superfluous Card-in-Card Nesting (`web/src/components/SkillGapMatcher.tsx:274-697`)**:
   - Outer `SpotlightCard` wraps the whole component, inside which the right column wraps another card (`bg-zinc-900/40 border border-white/[0.06] rounded-xl`), which then embeds further cards for recommended skills (`p-3.5 rounded-xl bg-zinc-900/60 border border-white/[0.06]`) and blueprints (`block p-4 rounded-xl border`).
   - This triple-nested card structure produces visual noise, redundant borders, and cramped padding.

2. **Non-Tabular Telemetry Numerals (`web/src/components/SkillGapMatcher.tsx:487, 546, 561`, `web/src/components/AnalyticsCharts.tsx:86, 385`)**:
   - Numbers in the RadialGauge, market coverage HUD (`{matchedJobsCount} / {totalTechJobs}`), ROI delta badges (`+{rec.unlockPercentage}% reach`), and salary tooltips (`฿{data.avg_salary.toLocaleString()}/mo`) lack explicit `tabular-nums`.
   - Glyphs shift slightly in width as numbers fluctuate during recalculations, causing micro layout jitter.

3. **Chart Visual Restraint & Over-Saturated Effects (`web/src/components/SkillGapMatcher.tsx:93`)**:
   - RadialGauge applies an aggressive neon glow: `drop-shadow-[0_0_10px_rgba(52,211,153,0.6)]`, conflicting with the restrained Obsidian aesthetic.
   - Compensation benchmark pills beneath the bar chart (lines 377-392) are horizontally stacked without strict tabular alignment.

4. **AnalyticsSkeleton Layout Misalignment (`web/src/components/AnalyticsSkeleton.tsx:1-184`)**:
   - Skeleton pulses use generic gray blocks rather than Obsidian dark tones matching the actual page hierarchy.
   - Skeletons lack representation of the interactive category filter bar and export controls.

---

## Proposed Changes

### 1. Skill Gap Matcher Hierarchy & Ergonomics (`web/src/components/SkillGapMatcher.tsx`)
- **Flatten Card Hierarchy**:
  - Retain outer `SpotlightCard` as the single authoritative surface (`bg-[#0c0d12] border border-white/[0.08] rounded-2xl`).
  - Flatten the Market Coverage HUD (lines 464-514): use subtle background tint (`bg-zinc-900/30 border border-white/[0.05]`) with clean divider lines.
  - Flatten recommendations and blueprint lists: eliminate nested boxiness with sleek, border-delimited rows or clean minimal cards.
- **Strict Tabular Telemetry**:
  - RadialGauge center: `<span className="text-xl sm:text-2xl font-bold font-mono text-white tracking-tight tabular-nums">{percentage}%</span>`.
  - RadialGauge stroke: Clean surgical stroke with `text-emerald-400` on highlight; eliminate aggressive `drop-shadow`.
  - Coverage ratio: `<span className="text-xl sm:text-2xl font-bold font-mono text-white tracking-tight tabular-nums">{matchedJobsCount}</span> <span className="text-xs sm:text-sm font-normal text-zinc-400 font-sans">/ <span className="tabular-nums">{totalTechJobs}</span> postings</span>`.
  - Delta badge: `<span className="font-mono tabular-nums font-bold">+{delta}% Reach</span>`.
  - ROI Skills:
    - Reach gain: `<span className="font-mono tabular-nums font-semibold">+{rec.unlockPercentage}% reach</span>`.
    - Companion stat: `<span className="font-mono tabular-nums text-zinc-200">{rec.coOccurrenceRate}%</span>`.
    - Salary badge: `<span className="font-mono tabular-nums text-cyan-300 font-semibold">฿{rec.avgSalary.toLocaleString()}/mo</span>`.
    - Sample count: `<span className="font-mono tabular-nums text-zinc-500 text-[10px]">(n={rec.salarySampleCount})</span>`.
  - Matched Blueprints:
    - Match percentage: `<span className="font-mono tabular-nums font-bold">{bp.matchPercentage}% Stack Match</span>`.
- **Mobile HUD Reflow & Touch Targets**:
  - Ensure side-by-side gauge and text on mobile (`flex-row items-center gap-4`).
  - Guarantee all interactive elements (presets, quick-adds, simulation buttons) maintain `>= 44px` interactive touch targets.
  - Add tactile `:active:scale-95` feedback across all clickable chips and buttons.

### 2. Market Analytics Strict Alignment & Restraint (`web/src/components/AnalyticsCharts.tsx`)
- **Compensation Breakdown Table/List**:
  - Replace wrapping pills with a cleanly aligned tabular benchmark list beneath the salary chart:
    - Skill column (left-aligned)
    - Average Salary (`฿X/mo`, right-aligned, `font-mono tabular-nums text-cyan-300 font-semibold`)
    - Sample size badge (`n=X`, right-aligned, `font-mono tabular-nums text-zinc-500 text-[10px]`)
- **Tabular Figures on All Tooltips**:
  - CustomSalaryTooltip: `font-mono tabular-nums text-cyan-300 font-semibold`.
  - CustomBarTooltip: `font-mono tabular-nums text-cyan-300`.
  - CustomPieTooltip: `font-mono tabular-nums text-indigo-300`.
- **Category Filter Tabs & Export Buttons**:
  - Category tabs: enforce `active:scale-95 transition-all` with tab counts in `font-mono text-[10px] tabular-nums`.
  - Data export buttons (CSV / JSON): tactile press feedback `active:scale-95`.
- **Database & Framework Bar Lists**:
  - Strict right-alignment for percentage numbers: `<span className="font-mono tabular-nums text-cyan-400">{db.percentage ?? 0}%</span>`.

### 3. Analytics Skeleton Enhancement (`web/src/components/AnalyticsSkeleton.tsx`)
- **Obsidian Theme Pulse**:
  - Replace flat gray blocks with refined Obsidian dark pulse styling: `bg-zinc-900/60 border border-white/[0.06] animate-pulse`.
- **Header & Filter Skeleton**:
  - Add skeleton representations for the category filter tabs and data export action bar to prevent layout shift during dynamic load.
- **Accurate Chart Skeletons**:
  - Accurately mirror vertical bar charts, donut charts, and compensation tabular lists.

### 4. Task Ledger (`docs/contexts/task-ledger.md`)
- Log Task 6.3 under Phase 6.

---

## Hermetic Test Plan

1. **Python Unit Suite**:
   - `uv run python -m unittest discover tests`
   - Must pass all 203 unit tests hermetically offline.

2. **Next.js Web Lint & Production Build**:
   - `cd web; npm run lint ; npm run build`
   - Zero ESLint errors or warnings.
   - Clean production compilation with Next.js 16.4.0 (Turbopack) and TypeScript 5.

3. **Style & antislop Audit**:
   - Zero em dashes (`\u2014`) in all target files.

---

## Playwright MCP Verification Checkpoints

The Builder must capture two Playwright visual verification screenshots:

1. **Desktop Viewport (1440 x 900)**:
   - Target Route: `http://localhost:3000/` and `http://localhost:3000/analytics`.
   - Capture: `workflow/stages/02_build/output/task-6.3-desktop.png`
   - Verify: Flattened card hierarchy in `SkillGapMatcher`, RadialGauge without loud glow, tabular numbers across coverage, compensation table alignment in `AnalyticsCharts`, and category tab counts.

2. **Mobile Viewport (390 x 844)**:
   - Target Route: `http://localhost:3000/` and `http://localhost:3000/analytics`.
   - Capture: `workflow/stages/02_build/output/task-6.3-mobile.png`
   - Verify: Compact mobile HUD reflow in `SkillGapMatcher`, minimum 44px tap targets, clean horizontal scrolling tabs in `AnalyticsCharts`, and zero horizontal scroll overflow.

---

## Out of Scope

- Modifying backend analytics calculations in `src/analyzer/`.
- Changing Turso database schema or SQL queries.
- Altering existing API routes (`/api/skill-gap`).
