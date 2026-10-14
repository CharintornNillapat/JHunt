# Plan: Task 3.3 — Skill Gap UX Polish: Visual ROI Delta Feedback, Compact Mobile HUD Reflow, and Accessibility Polish

**Date:** 2026-10-14  
**Task ID:** 3.3  
**Reference:** `docs/contexts/task-ledger.md` (Phase 3), `AGENTS.md` (Definitions & Invariants), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Deliver real-time visual ROI delta feedback when users simulate added competencies (including animated gauge highlights and unlocked architecture blueprint callouts), implement a compact responsive HUD reflow on mobile screens below 640px to keep key telemetry above the fold without vertical bloat, and polish accessibility with screen-reader live regions and visible keyboard focus states, adhering strictly to antislop Mode 1 (DURING) and WCAG AA standards.

---

## antislop & UX Protocol (Mode 1: DURING)

This specification strictly applies the `antislop` suite (`antislop`, `antislop-ui`, `antislop-layoutmobile`, `antislop-human`, `antislop-copywriting`, `antislop-code`):

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) anywhere in copy, badges, callouts, or screen-reader text.
   - Use colons, commas, periods, or parentheses instead.
2. **R-03 (Mobile Responsiveness & Tap Targets)**:
   - Mobile screens ($< 640\text{px}$) must reflow into a compact, space-efficient HUD layout:
     - RadialGauge scales down from $96\text{px}$ to $64\text{px}$ ($w\text{-}16\ h\text{-}16$) to eliminate massive vertical spacing.
     - Card padding tightens from `p-6` to `p-4 sm:p-6 lg:p-8`.
     - Controls and telemetry sit side-by-side above the fold on standard mobile viewports ($375\text{px}$ to $428\text{px}$).
   - All interactive controls retain $\ge 44\text{px}$ touch target bounds.
   - Zero horizontal overflow across all breakpoints.
3. **R-25 (Color Contrast — WCAG AA)**:
   - Positive ROI delta badges: `text-emerald-300` on `bg-emerald-950` with `border-emerald-500/40` (contrast $> 6.5:1$).
   - High-match blueprint callouts: `text-cyan-200` on `bg-cyan-950` (contrast $> 7:1$).
   - Muted secondary text: `text-zinc-400` on `#08080a` (contrast $> 4.8:1$).
4. **R-26 (Interactive Elements)**:
   - Clicking "Simulate adding {skill}" or a role preset immediately triggers visible ROI delta feedback and recalculation without page reload.
5. **R-27 (UI States)**:
   - Dynamic reach delta badge appears when coverage changes positively (`+12% Reach`).
   - Loading indicator with pulse animation while recalculating.
   - Unlocked blueprint callout (`Fully Unlocked` or `High Match`) updates dynamically as skill coverage grows.
6. **R-32 (Keyboard Accessibility)**:
   - All interactive elements (preset buttons, remove chips, simulation buttons, clear stack) keyboard-operable with visible focus rings (`focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950`).
   - Add `aria-live="polite"` live region so screen readers announce coverage updates and delta increases.
7. **R-35 (Craftsmanship Verification)**:
   - Clean lint, clean production build, and verified click-through audit across desktop and mobile screens.

---

## Current Behavior (Evidence)

1. **Missing Visual ROI Delta on Skill Simulation (`web/src/components/SkillGapMatcher.tsx:527-534`)**:
   - In `recommendedSkills`, clicking "Simulate adding {skill}" triggers `addSkill(rec.name)` and fires `/api/skill-gap`.
   - When the response arrives, the coverage percentage updates statically.
   - There is no visual delta indicator or feedback badge (e.g. `+12% Reach`) highlighting what changed. Users cannot immediately perceive the value of adding the skill without remembering the previous number.

2. **Static Blueprint Match Badges (`web/src/components/SkillGapMatcher.tsx:585-594`)**:
   - Blueprint cards in the right column display a static match badge (`{bp.matchPercentage}% Stack Match`).
   - When a simulated skill brings a blueprint to 100% (fully unlocked) or above $\ge 75\%$, there is no distinctive callout badge (e.g., `Fully Unlocked` or `High Match`) celebrating the accomplishment and guiding the user to view the spec.

3. **Vertical Layout Bloat on Mobile Viewports (`web/src/components/SkillGapMatcher.tsx:210, 248, 356, 445`)**:
   - The outer container has `p-6 sm:p-8`.
   - The preset buttons, search input, chips, and quick-add buttons stack vertically with large margins (`mb-5`, `space-y-6`).
   - In the HUD column, `RadialGauge` renders as a fixed `w-24 h-24` ($96\text{px}$) circle. On small viewports ($< 640\text{px}$), this forces the gauge and recommendation cards deep below the fold, requiring extensive vertical scrolling to see the benchmark result.

4. **Screen Reader Non-Observability**:
   - When coverage rate changes dynamically, screen readers receive no announcement. Visually impaired users have to navigate the DOM to discover the updated percentage.

---

## Changes

### 1. Visual ROI Delta Feedback & RadialGauge Pulse
- **File**: `web/src/components/SkillGapMatcher.tsx`
- **State & Delta Tracking**:
  - Maintain `prevCoverageRef = useRef<number>(initialData?.coverageRate ?? 0)`.
  - Add `const [delta, setDelta] = useState<number | null>(null)`.
  - When `data?.coverageRate` updates:
    ```typescript
    useEffect(() => {
      if (data?.coverageRate !== undefined && data.coverageRate !== prevCoverageRef.current) {
        const diff = data.coverageRate - prevCoverageRef.current;
        if (diff !== 0) {
          setDelta(diff);
          const timer = setTimeout(() => setDelta(null), 3000);
          prevCoverageRef.current = data.coverageRate;
          return () => clearTimeout(timer);
        }
      }
    }, [data?.coverageRate]);
    ```
- **RadialGauge Highlight & Delta Pill**:
  - When `delta !== null && delta > 0`, highlight the gauge circle with a subtle emerald glow (`stroke-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]`).
  - Display an animated delta badge directly beside or under the percentage:
    ```tsx
    {delta !== null && delta > 0 && (
      <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-950/90 border border-emerald-500/50 text-emerald-300 shadow-sm animate-pulse">
        <TrendingUp className="h-2.5 w-2.5" />
        +{delta}% Reach
      </span>
    )}
    ```
  - Screen Reader Live Region (R-32):
    ```tsx
    <div className="sr-only" aria-live="polite">
      {`Market coverage updated to ${coverageRate}%${delta ? `, a ${delta}% increase` : ""}`}
    </div>
    ```

### 2. Unlocked Architecture Blueprint Callout Badges
- **File**: `web/src/components/SkillGapMatcher.tsx`
- **Callout Logic in `relevantBlueprints`**:
  - If `bp.matchPercentage === 100`:
    Render a prominent callout badge:
    ```tsx
    <span className="inline-flex items-center gap-1 text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-md bg-emerald-950 border border-emerald-500/50 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.25)]">
      <CheckCircle2 className="h-3 w-3 text-emerald-400" />
      <span>Fully Unlocked</span>
    </span>
    ```
    And style card border with `border-emerald-500/40 bg-zinc-900/90`.
  - If `bp.matchPercentage >= 75` (and `< 100`):
    Render:
    ```tsx
    <span className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md bg-cyan-950/90 border border-cyan-500/50 text-cyan-200">
      <span>{bp.matchPercentage}% High Match</span>
    </span>
    ```

### 3. Compact Responsive HUD Reflow on Mobile Screens (< 640px)
- **File**: `web/src/components/SkillGapMatcher.tsx`
- **Responsive Gauge Sizing**:
  - Update `RadialGauge` to accept an optional responsive size or scale:
    ```tsx
    function RadialGauge({ percentage, isHighlight }: { percentage: number; isHighlight?: boolean }) {
      ...
      return (
        <div className="relative flex items-center justify-center shrink-0">
          <svg className="w-16 h-16 sm:w-24 sm:h-24 transform -rotate-90" viewBox="0 0 96 96">
            ...
          </svg>
          <div className="absolute flex flex-col items-center justify-center text-center">
            <span className="text-lg sm:text-2xl font-bold font-mono text-white tracking-tight">
              {percentage}%
            </span>
            <span className="text-[8px] sm:text-[9px] font-mono uppercase tracking-wider text-zinc-400">
              Reach
            </span>
          </div>
        </div>
      );
    }
    ```
- **HUD Section Reflow**:
  - Tighten container padding: `p-4 sm:p-6 lg:p-8`.
  - On mobile screens, reflow the gauge and stat readout into a tight horizontal row:
    `flex flex-row items-center gap-4 py-3 sm:py-4`.
  - Tighter preset buttons on mobile: `grid grid-cols-2 sm:grid-cols-4 gap-1.5 sm:gap-2` with `p-2 sm:p-2.5`.
  - Reduces total component height by ~140px on mobile screens, bringing the gauge, fit assessment, and first ROI recommendations above the fold on mobile viewports.

### 4. Accessibility & Touch Target Polish
- **File**: `web/src/components/SkillGapMatcher.tsx`
- Ensure all interactive buttons maintain $\ge 44\text{px}$ touch targets:
  - Presets: `min-h-[44px]`.
  - Quick-add skill chips: `min-h-[36px]` with touch padding.
  - "Simulate adding": `min-h-[44px]`.
- Focus indicators:
  - Explicit `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950`.
- Zero em dashes across all copy strings (R-02).

---

## Verification & Definition of Done

### 1. Web Suite Verification:
- `cd web; npm run lint`: Must pass with 0 errors and 0 warnings.
- `cd web; npm run build`: Next.js Turbopack production build must compile cleanly.

### 2. Python Hermetic Suite:
- `uv run python -m unittest discover tests`: All 197 hermetic tests must continue to pass.

### 3. antislop Craftsmanship & Click-Through Checklist (R-35):
- **Simulation Feedback**:
  - Clicking "Simulate adding Docker" shows `+X% Reach` delta pill badge and highlights the RadialGauge.
  - Screen reader receives polite live announcement.
- **Blueprint Callouts**:
  - Blueprints matching 100% display glowing `★ Fully Unlocked` callout badge.
  - Blueprints matching $\ge 75\%$ display `High Match` badge.
- **Mobile Viewport Reflow (< 640px)**:
  - Gauge reflows to compact $64\text{px}$ diameter side-by-side with telemetry stats.
  - No horizontal overflow on $320\text{px}$ to $428\text{px}$ viewports.
  - All interactive buttons meet $\ge 44\text{px}$ touch target standards.
- **Copywriting Audit (R-02)**:
  - Zero em dashes (`—`) across all new and modified strings.

---

## Out of Scope
- Modifying Turso database schema or backend scraping pipeline.
- Changes outside `web/src/components/SkillGapMatcher.tsx`.

---

## Production Touch Points
- **None**: Zero database writes, zero Telegram messages, zero Gemini quota consumed.
