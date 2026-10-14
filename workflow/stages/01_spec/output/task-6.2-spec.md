# Plan: Task 6.2: Blueprint Catalog Interactive Filtering & Search UX Polish

**Date:** 2026-10-14  
**Task ID:** 6.2  
**Reference:** `docs/contexts/task-ledger.md` (Phase 6), `web/src/components/BlueprintCatalog.tsx`, `web/src/app/page.tsx`, Design Skill Suite (`impeccable`, `emil-design-eng`, `taste-skill`, `antislop-ui`, `antislop-layoutmobile`, `antislop-copywriting`)

---

## Goal

Upgrade the portfolio blueprint catalog interface (`BlueprintCatalog.tsx`) into a high-precision, tactile exploratory workspace with ergonomic live search (cyan focus ring, instant clear affordance, keyboard shortcut), reactive filter chips with active scale feedback, tabular numeral counts (`font-mono tabular-nums`), zero cumulative layout shift (`CLS = 0.00`), and a welcoming empty-state recovery UX.

---

## antislop & Engineering Protocol Compliance

This specification strictly applies the repository invariants and design standards:

1. **Rule R-02 (Zero Em Dashes Everywhere)**:
   - Zero em dashes in code, CSS, comments, specs, build reports, or reviews.
   - Use colons, hyphens, commas, periods, or parentheses instead.

2. **Aesthetic Restraint & Obsidian Hierarchy (`taste-skill`, `antislop-ui`)**:
   - Controls Container: `bg-zinc-900/80 border border-white/[0.08]` with crisp subtle borders.
   - Search Focus Ring: `focus:border-cyan-500/60 focus:ring-2 focus:ring-cyan-500/20 shadow-sm focus:shadow-cyan-950/30`.
   - Results Counter: `font-mono text-xs text-zinc-400 tabular-nums` matching telemetry standards.
   - Avoid generic AI slop: no garish glowing gradients, unnecessary spinners, or cartoonish badges.

3. **Tactile Interaction & Physics (`emil-design-eng`, `animate`)**:
   - Category Tabs: Snappy spring animation `{ type: "spring", stiffness: 380, damping: 28 }` with tactile press `active:scale-95`.
   - Filter Chips & Tech Pills: Tactile `active:scale-95` on click with instant tag filtering.
   - Clear Buttons: `active:scale-90 transition-transform` on dismiss icons.
   - Empty-State Recovery: Distinctive, tactile reset button `active:scale-95`.

4. **Zero Layout Shift & Accessibility (`impeccable`, `antislop-layoutmobile`)**:
   - Container min-height: `min-h-[480px]` on the catalog grid section to guarantee zero jarring layout jumps when filtering from many items to none.
   - Fixed-slot controls bar height to prevent vertical jitter when active tag chips mount.
   - Screen reader announcement: `aria-live="polite"` announcing `"Showing {count} of {total} architecture blueprints"`.
   - Mobile touch targets: Minimum 44px tap targets on all interactive buttons and mobile filters.

---

## Current Behavior (Evidence)

1. **Missing Result Counts & Telemetry (`web/src/components/BlueprintCatalog.tsx:120-193`)**:
   - Users currently see category tabs and a search input, but have zero visibility into how many blueprints match their current search query or active category until they scroll through the grid.
   - Tab counts are absent; users cannot tell in advance whether clicking "Data & ML Pipelines" will return 0, 2, or 10 blueprints.

2. **Search Input Ergonomics (`web/src/components/BlueprintCatalog.tsx:162-192`)**:
   - The search input uses `focus:border-cyan-500/50` without a subtle glow focus ring or input container elevation.
   - Search icon does not react when the input gains focus.
   - The clear button lacks tactile `:active` scale feedback.

3. **Tech Filter Pills Lack Tactile Feedback (`web/src/components/BlueprintCatalog.tsx:307-325`)**:
   - Tech pills on each card support click-to-filter, but lack tactile `:active` scale states (`active:scale-95`), feeling flat on click.

4. **Empty-State Recovery (`web/src/components/BlueprintCatalog.tsx:197-225`)**:
   - When zero blueprints match, the UI renders a simple dashed box with text link `Clear all filters ->`.
   - Lacks an authoritative tactile reset button and quick-recovery popular tag suggestions (e.g. Python, Docker, Go, FastAPI).

5. **Potential Layout Shift on Filter Changes (`web/src/components/BlueprintCatalog.tsx:195-356`)**:
   - The grid container has no `min-h` constraint. Filtering to empty state collapses the page height immediately, causing the footer to jump upward (Cumulative Layout Shift).

---

## Proposed Changes

### 1. Catalog Controls Bar & Telemetry Header (`web/src/components/BlueprintCatalog.tsx`)
- **Telemetry Counter**:
  Add a real-time matching counter next to the controls bar:
  ```tsx
  <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 select-none">
    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
    <span>Showing</span>
    <span className="font-semibold text-zinc-200 tabular-nums">{filteredProjects.length}</span>
    <span>of</span>
    <span className="tabular-nums">{initialProjects.length}</span>
    <span>blueprints</span>
  </div>
  ```
- **Category Counts with Tabular Numerals**:
  Pre-calculate blueprint counts per category using `useMemo`:
  ```tsx
  const categoryCounts = useMemo(() => {
    return {
      ALL: initialProjects.length,
      BACKEND: initialProjects.filter((p) => p.role.toLowerCase().includes("backend")).length,
      DATA_AI: initialProjects.filter((p) => {
        const r = p.role.toLowerCase();
        return r.includes("data") || r.includes("ai") || r.includes("ml") || r.includes("analyst");
      }).length,
      FULLSTACK: initialProjects.filter((p) => {
        const r = p.role.toLowerCase();
        return r.includes("full") || r.includes("front") || r.includes("web");
      }).length,
    };
  }, [initialProjects]);
  ```
  Display counts inside category tabs with `font-mono text-[10px] tabular-nums` (e.g. `All Architectures (8)`).
- **Refined Spring Physics & Tactile Press**:
  - Category buttons: add `active:scale-95 transition-transform`.
  - Spring transition: `{ type: "spring", stiffness: 380, damping: 28 }`.

### 2. Search Input Ergonomics & Focus Glow
- **Target File**: `web/src/components/BlueprintCatalog.tsx`
- **Focus State Tracking**: Add `const [isSearchFocused, setIsSearchFocused] = useState(false);`.
- **Search Icon Reaction**: `Search` icon transitions to `text-cyan-400` when focused.
- **Cyan Glow Focus Ring**:
  ```tsx
  className={cn(
    "w-full bg-zinc-900/80 border rounded-lg pl-9 pr-10 py-2 text-xs text-zinc-200 placeholder:text-zinc-500 transition-all duration-150",
    isSearchFocused
      ? "border-cyan-500/60 ring-2 ring-cyan-500/20 shadow-lg shadow-cyan-950/30 bg-zinc-900"
      : "border-white/[0.08] hover:border-white/[0.14]"
  )}
  ```
- **Clear Button**:
  Tactile active press: `active:scale-90 transition-transform p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white`.
- **Active Tech Chip**:
  Refine with `bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 active:scale-95 transition-all`.

### 3. Card Tech Filter Pills Tactile Feedback
- **Target File**: `web/src/components/BlueprintCatalog.tsx`
- In card tech stack pills (lines 307-325):
  Add `active:scale-95 transition-all duration-150`.
  Selected state: `bg-cyan-950/90 border-cyan-500/50 text-cyan-200 ring-1 ring-cyan-500/30 shadow-sm`.
  Unselected state: `bg-zinc-800/70 border-white/[0.06] text-zinc-300 hover:border-cyan-500/40 hover:text-zinc-100`.

### 4. Zero Layout Shift & High-Craft Empty State
- **Container Stability**: Add `min-h-[480px]` to the catalog grid wrapper to eliminate page height collapsing.
- **Empty-State Recovery**:
  Upgrade empty state with:
  - Tactile primary action:
    ```tsx
    <button
      onClick={() => {
        setSelectedCategory("ALL");
        setSearchQuery("");
        setSelectedTech(null);
      }}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-950/80 hover:bg-cyan-900/90 border border-cyan-500/40 text-cyan-300 hover:text-white text-xs font-mono font-medium shadow-lg shadow-cyan-950/40 active:scale-95 transition-all min-h-[44px]"
    >
      <span>Reset All Filters</span>
      <span className="text-cyan-400">&rarr;</span>
    </button>
    ```
  - Quick filter recommendation chips (e.g. "Backend", "Python", "Go", "Docker") for 1-click recovery.

### 5. Screen Reader Live Region
- Add live region announcing filter results:
  ```tsx
  <div className="sr-only" aria-live="polite">
    Showing {filteredProjects.length} of {initialProjects.length} architecture blueprints
  </div>
  ```

### 6. Page Layout Wiring (`web/src/app/page.tsx`)
- Verify that `page.tsx` passes `projects` to `BlueprintCatalog`. Ensure no layout regressions or unneeded changes.

### 7. Task Ledger (`docs/contexts/task-ledger.md`)
- Log Task 6.2 under Phase 6.

---

## Hermetic Test Plan

1. **Python Unit Suite**:
   - `uv run python -m unittest discover tests`
   - All 203 unit tests must pass offline.

2. **Next.js Web Lint & Production Build**:
   - `cd web; npm run lint ; npm run build`
   - Zero ESLint errors or warnings.
   - Successful production compilation with Turbopack.

3. **Style & antislop Audit**:
   - Zero em dashes (`\u2014`) in all target files.

---

## Playwright MCP Verification Checkpoints

The Builder must capture two Playwright visual verification screenshots:

1. **Desktop Viewport (1440 x 900)**:
   - Command/Action: Resize viewport to 1440x900, navigate to `http://localhost:3000/`.
   - Interaction: Focus the search input (confirm cyan glow ring), verify tabular count (`Showing X of Y blueprints`), click a category tab (confirm active pill).
   - Target File: `workflow/stages/02_build/output/task-6.2-desktop.png`

2. **Mobile Viewport (390 x 844)**:
   - Command/Action: Resize viewport to 390x844 (iPhone 14 standard mobile), navigate to `http://localhost:3000/`.
   - Verify: Responsive reflow of category tabs (horizontal scrolling), search input with clear button, touch target accessibility (`>= 44px`), and zero horizontal overflow.
   - Target File: `workflow/stages/02_build/output/task-6.2-mobile.png`

---

## Out of Scope

- Modifying backend scrapers, extraction, or Turso storage queries.
- Altering existing blueprints schema.
- Adding third-party search libraries.
