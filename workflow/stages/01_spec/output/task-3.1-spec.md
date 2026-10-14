# Plan: Task 3.1 — Web Performance and Interactive UX Polish

**Date:** 2026-10-14  
**Task ID:** 3.1  
**Reference:** `docs/contexts/task-ledger.md` (Phase 3), `AGENTS.md` (Definitions & Invariants), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Decouple Three.js from the initial client bundle via dynamic lazy-loading on the home page, enhance catalog discoverability with click-to-filter tech tags, streamline blueprint navigation with a sticky Table of Contents (TOC) and scroll-spy, and enable instant benchmark evaluation through one-click role stack presets in the Skill Gap Matcher, all strictly conforming to antislop Mode 1 (DURING) and WCAG AA accessibility standards.

---

## antislop & UX Protocol (Mode 1: DURING)

This specification strictly applies the `antislop` suite (`antislop`, `antislop-ui`, `antislop-layoutmobile`, `antislop-human`, `antislop-copywriting`, `antislop-code`):

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) anywhere in new or modified copy, UI labels, tooltips, or placeholders.
   - Use colons, commas, periods, or parentheses instead.
2. **R-03 (Mobile Responsiveness & Tap Targets)**:
   - All interactive controls (tech tags, stack preset buttons, TOC links, clear buttons) must meet or exceed the $\ge 44\text{px}$ minimum tap target standard (via touch padding, min-height, or touch hit area).
   - Zero horizontal overflow on mobile viewports ($320\text{px}$ to $428\text{px}$).
   - Responsive reflow: TOC collapses cleanly into an expandable/compact jump menu or mobile outline, preserving reading flow.
3. **R-25 (Color Contrast — WCAG AA)**:
   - Minimum $4.5:1$ contrast ratio for normal text and $3:1$ for large text against dark surfaces (`#08080a`, `#0c0d12`, `zinc-900`, `zinc-950`).
   - Forbid light grey on grey or muted low-contrast text. Inactive tags and TOC links must use `text-zinc-300` or `text-zinc-400` with verified contrast $\ge 4.8:1$. Active elements use `text-cyan-300` / `text-cyan-200` with contrast $> 7:1$.
4. **R-26 (Interactive Elements)**:
   - Zero non-functional, dead, or cosmetic-only controls.
   - Every tech tag must actively filter the catalog and toggle cleanly.
   - Every TOC link must smoothly scroll to a valid existing section.
   - Every stack preset button must instantly populate the benchmark stack and trigger recalculation.
5. **R-27 (UI States)**:
   - Preserve and verify all three required states: Empty state (e.g. no blueprints match filtered tag), Loading state (e.g. canvas loading placeholder, skill gap recalculation indicator), Error state.
6. **R-32 (Keyboard Accessibility)**:
   - Full keyboard navigation: `Tab` / `Shift+Tab` across all presets, tags, and TOC items following visual DOM order.
   - Operable via `Enter` and `Space`.
   - Visible focus indicators on every control: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950`. No `outline: none` without custom replacement.
7. **R-35 (Craftsmanship Verification)**:
   - Verification via click-through audit across desktop and mobile viewports with zero console errors before delivery.

---

## Current Behavior (Evidence)

1. **Monolithic Initial Client Bundle (`web/src/app/page.tsx:3`)**:
   - `page.tsx` statically imports `ThreeCanvas` via `import ThreeCanvas from "@/components/ThreeCanvas";`.
   - `ThreeCanvas.tsx` imports `* as THREE from "three"`.
   - Because `ThreeCanvas` is in the direct import graph of `/`, Three.js (~600KB+ minified) is parsed and bundled in the client entry payload for the home page, increasing First Contentful Paint (FCP) and Time to Interactive (TTI) unnecessarily for users who only want to scan catalog blueprints.

2. **Non-Interactive Tech Stack Badges (`web/src/components/BlueprintCatalog.tsx:197-211`)**:
   - Tech stack tags in each blueprint card are rendered as passive `<span>` elements:
     ```tsx
     <span key={tech} className="font-mono text-[11px] px-2 py-0.5 rounded bg-zinc-800/70 border border-white/[0.06] text-zinc-300">
       {tech}
     </span>
     ```
   - Filtering by a specific technology requires the user to manually click into the search input and type the technology name.

3. **Missing Navigational Structure in Long Specs (`web/src/components/BlueprintReader.tsx:397-402`)**:
   - `BlueprintReader` renders long, detailed markdown specifications (often 200+ lines covering Architecture, Schemas, API Endpoints, and Failure Scenarios) in a single uninterrupted column.
   - There is no Table of Contents (TOC) and no scroll-spy mechanism. Users cannot see an overview of the blueprint sections or jump directly to specific implementation details without manually scrolling the entire page.

4. **Manual Skill Assembly Overhead (`web/src/components/SkillGapMatcher.tsx:323-352`)**:
   - Users who want to benchmark standard industry roles (e.g. "Full-Stack TypeScript", "Python Backend", "Data / ML Engineer", "Cloud Systems / Go") must either type skills individually or hunt through the 12 general popular skill chips one by one.
   - There are no pre-curated, authoritative role presets to simulate realistic market stacks with a single click.

---

## Changes

### 1. Lazy-Load Three.js Hero Canvas
- **Files**: `web/src/app/page.tsx`, `web/src/components/ThreeCanvas.tsx`
- **In `web/src/app/page.tsx`**:
  - Replace static import with `next/dynamic`:
    ```tsx
    import nextDynamic from "next/dynamic";

    const ThreeCanvas = nextDynamic(() => import("@/components/ThreeCanvas"), {
      ssr: false,
      loading: () => (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-[560px] -z-10 overflow-hidden select-none"
          aria-hidden="true"
        />
      ),
    });
    ```
  - This removes Three.js from the initial page payload while maintaining zero visual layout shift.
- **In `web/src/components/ThreeCanvas.tsx`**:
  - Ensure WebGL canvas container maintains `aria-hidden="true"`, `pointer-events-none`, and strict unmount cleanup (disposal of geometries, materials, renderer context, and observer disconnects).
  - Preserve `prefers-reduced-motion` static snapshot render.

### 2. Click-to-Filter Tech Tags in `BlueprintCatalog`
- **Files**: `web/src/components/BlueprintCatalog.tsx`
- **State & Logic**:
  - Add state `selectedTech: string | null` (or synchronize with an active filter chip).
  - Update `filteredProjects` filter calculation to require:
    - Role category matches (`selectedCategory`)
    - Search query matches (`searchQuery`)
    - If `selectedTech` is non-null: `parseTechStack(project.tech_stack).some(t => t.toLowerCase() === selectedTech.toLowerCase())`.
- **UI & Accessibility**:
  - Transform tech stack pills into interactive `<button>` elements.
  - Active state:
    - If `selectedTech` matches, style with `bg-cyan-950/90 border-cyan-500/50 text-cyan-200 ring-1 ring-cyan-500/30`.
    - Provide `aria-pressed={isSelected}` and `aria-label={`Filter by ${tech}`}`.
    - Clicking an active tag toggles it off (`setSelectedTech(null)`).
  - Tap target compliance (R-03):
    - Wrap tag in an accessible button with minimum touch dimension or touch-target padding (e.g., `py-1 px-2.5 min-h-[32px] sm:min-h-0` with adequate spacing).
  - Focus indicator (R-32):
    - `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-950`.
  - Filter Bar Feedback:
    - When `selectedTech` is active, display an active filter chip in the controls bar alongside the search box with an explicit `(x)` clear button and label `Tech: {selectedTech}`.
  - Empty State Handling (R-27):
    - Update empty state button to clear both search query and `selectedTech`.
    - No em dashes in copy (R-02).

### 3. Sticky Table of Contents (TOC) with Scroll-Spy in `BlueprintReader`
- **Files**: `web/src/components/BlueprintReader.tsx`
- **Heading Extraction & Slugs**:
  - Extract H2 and H3 headings from `cleanMarkdown` using a memoized parser:
    ```typescript
    interface TocHeading {
      id: string;
      text: string;
      level: 2 | 3;
    }
    ```
  - Generate deterministic, clean URL-safe slugs for each heading (e.g. `2-system-architecture`).
  - In `ReactMarkdown` custom components:
    - Render `h2` and `h3` with the matching `id={slug}` and `scroll-mt-32` (accounting for the sticky top-16 Navbar and top-16 action sub-header so headers are never obscured upon navigation).
- **Sticky Desktop TOC Layout**:
  - Refactor main content into a two-column responsive layout:
    - Large screens (`lg`): `lg:grid lg:grid-cols-[1fr_240px] gap-10 items-start`.
    - Spec markdown article occupies primary column.
    - TOC aside occupies sticky secondary column:
      ```tsx
      <aside className="hidden lg:block sticky top-36 max-h-[calc(100vh-10rem)] overflow-y-auto p-4 rounded-xl border border-white/[0.08] bg-[#0c0d12]/90 backdrop-blur-md">
        <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-400 mb-3 flex items-center gap-1.5">
          <List className="h-3.5 w-3.5 text-cyan-400" />
          <span>Table of Contents</span>
        </h3>
        ...
      </aside>
      ```
- **Mobile Jump Menu (R-03)**:
  - For viewports below `lg`, render a compact, accessible collapsible drawer or dropdown ("Jump to Section...") directly above the article, ensuring full accessibility without layout crowding.
- **Scroll-Spy via `IntersectionObserver`**:
  - Track visible headings using an `IntersectionObserver` configured with `rootMargin: "-100px 0px -60% 0px"`.
  - Highlight active heading in TOC with `text-cyan-300 font-medium border-l-2 border-cyan-400 bg-cyan-950/30 pl-2.5`.
  - Inactive links styled with `text-zinc-400 hover:text-zinc-200 transition-colors pl-2.5`.
- **Keyboard Navigation (R-32)**:
  - All TOC anchor links keyboard-focusable with visible focus rings.
  - Smooth in-page scrolling via native CSS `scroll-behavior: smooth` or `element.scrollIntoView({ behavior: 'smooth' })`.

### 4. One-Click Role Stack Presets in `SkillGapMatcher`
- **Files**: `web/src/components/SkillGapMatcher.tsx`
- **Curated Stack Presets**:
  - Define market-aligned presets based on Thailand tech hiring demand:
    ```typescript
    interface StackPreset {
      id: string;
      label: string;
      description: string;
      skills: string[];
    }

    const STACK_PRESETS: StackPreset[] = [
      {
        id: "fullstack-ts",
        label: "Full-Stack TS",
        description: "Modern TypeScript and React ecosystem",
        skills: ["TypeScript", "React", "Next.js", "Node.js", "PostgreSQL"],
      },
      {
        id: "python-backend",
        label: "Python Backend",
        description: "High-throughput asynchronous API services",
        skills: ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
      },
      {
        id: "data-ml",
        label: "Data & ML",
        description: "Data pipelines and distributed workloads",
        skills: ["Python", "PostgreSQL", "Docker", "AWS", "Kubernetes"],
      },
      {
        id: "cloud-systems",
        label: "Cloud Systems",
        description: "Microservices and infrastructure orchestration",
        skills: ["Go", "Docker", "Kubernetes", "PostgreSQL", "Redis"],
      },
    ];
    ```
- **UI & Placement**:
  - Position presets directly above the skill search input in the left column.
  - Render each preset as an accessible pill/button with title and badge.
  - Highlight active preset if `areSkillSetsEqual(selectedSkills, preset.skills)` is true.
  - Clicking a preset calls `setSelectedSkills(preset.skills)` in one click.
- **Accessibility & antislop**:
  - R-03: Minimum touch target size $\ge 44\text{px}$ (e.g. `min-h-[44px]` with flex alignment).
  - R-25: WCAG AA contrast compliance (`text-zinc-300` on `bg-zinc-900` > $5:1$; active `text-cyan-200` on `bg-cyan-950` > $7:1$).
  - R-26: Instant recalculation without page reload.
  - R-32: Keyboard operable with `Enter`/`Space`, clear focus ring.
  - R-02: Zero em dashes in descriptions or copy.

---

## Verification & Definition of Done

### 1. Web Suite Verification:
- `cd web; npm run lint`: Must pass with 0 errors and 0 warnings.
- `cd web; npm run build`: Next.js Turbopack production build must compile cleanly.

### 2. Python Hermetic Suite:
- `uv run python -m unittest discover tests`: All 197 hermetic tests must continue to pass.

### 3. antislop Craftsmanship & Click-Through Checklist (R-35):
- **Click-through verification on `/`**:
  - ThreeCanvas loads lazily without blocking hero text or catalog rendering.
  - Clicking a tech tag (e.g. `Python`) on any card immediately filters the catalog down to matching blueprints.
  - Active tech filter indicator appears in the controls bar; clicking `(x)` resets the filter.
  - Clicking the same active tag on a card toggles the filter off.
- **Click-through verification on `/blueprints/[id]`**:
  - Sticky Table of Contents appears on desktop screens $\ge 1024\text{px}$.
  - Clicking a TOC item smoothly scrolls to the heading with `scroll-mt-32` clearance.
  - Scrolling through the spec dynamically updates the highlighted active TOC item.
  - On mobile screens ($< 1024\text{px}$), layout reflows cleanly without horizontal overflow.
- **Click-through verification on `/analytics`**:
  - Stack Presets render above the skill input.
  - Clicking "Full-Stack TS", "Python Backend", "Data & ML", or "Cloud Systems" instantly populates the stack and recalculates market coverage.
  - Active preset highlights when matching the current stack.
- **Copywriting Audit (R-02)**:
  - Zero em dashes (`—`) across all new and modified strings.

---

## Out of Scope
- Modifying Turso database schema, migrations, or tables.
- Modifying Python backend scraping, extraction, or analysis pipelines.
- Introducing external UI component libraries (shadcn, mui, radix) — leverage existing Tailwind CSS, Lucide icons, and React patterns to preserve zero added bundle bloat.

---

## Production Touch Points
- **None**: No database mutations, no live Telegram messages, zero Gemini quota consumption.
