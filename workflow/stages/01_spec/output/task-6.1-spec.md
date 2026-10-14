# Plan: Task 6.1: Shell, Theme, Cards & Blueprint Reader Design Polish

**Date:** 2026-10-14  
**Task ID:** 6.1  
**Reference:** `docs/contexts/task-ledger.md` (Phase 6), `web/src/app/globals.css`, `web/src/components/Navbar.tsx`, `web/src/components/SpotlightCard.tsx`, `web/src/components/BlueprintReader.tsx`, Design Skill Suite (`impeccable`, `emil-design-eng`, `animate`, `animation-performance`, `taste-skill`, `antislop-ui`, `antislop-layoutmobile`, `antislop-copywriting`)

---

## Goal

Elevate the core JHunt interface (shell, navigation, spotlight cards, and blueprint reader) into a tactile, high-craft developer workspace with refined typography hierarchy, coherent Obsidian surface tokens (#08080a palette), delicate border contrast, and deliberate ease-out micro-interactions, preserving complete print fidelity and reduced-motion accessibility.

---

## antislop & Engineering Protocol Compliance

This specification strictly applies the repository invariants and design skills:

1. **Rule R-02 (Zero Em Dashes Everywhere)**:
   - Zero em dashes in code, CSS, comments, specs, build reports, or reviews.
   - Use colons, hyphens, commas, periods, or parentheses instead.

2. **Obsidian Palette & Surface Hierarchy (`taste-skill`, `antislop-ui`)**:
   - Canvas Substrate: `#08080a` (pure deep obsidian, zero blue glow bloat).
   - Card Slabs: `#0c0d12` to `#0d0e12` (subtle charcoal lift).
   - Elevated Chrome: `#12141a` to `#161822` (navbars, tooltips, dialogs).
   - Borders: `rgba(255, 255, 255, 0.07)` default, `rgba(255, 255, 255, 0.14)` hover sheen, `rgba(6, 182, 212, 0.25)` active focus.
   - Accents: surgical cyan (`#06b6d4`, `#22d3ee`, `#083344`), avoiding neon saturation traps.

3. **Spatial Rhythm & Typography (`impeccable`, `antislop-copywriting`)**:
   - Strict 4px/8px modular spacing rhythm.
   - Proportional scale: H1 (`text-2xl sm:text-3xl`), H2 (`text-xl sm:text-2xl`), H3 (`text-base sm:text-lg`), body (`text-sm sm:text-base leading-relaxed`).
   - Monospace precision: tabular figures, uppercase micro-labels (`tracking-wider`, `text-[10px]`, `text-[11px]`).
   - Anti-aliased font smoothing with `text-rendering: optimizeLegibility`.

4. **Tactile Motion & Performance (`emil-design-eng`, `animate`, `animation-performance`)**:
   - Only composite properties animated: `transform` and `opacity`.
   - Spring physics: snappy navigation pill (`stiffness: 380, damping: 28`).
   - Tactile button press: `active:scale-[0.98]` or `active:scale-95` on clickable items.
   - Strict preservation of `@media (prefers-reduced-motion: reduce)` (all animations clamped to 0.01ms, scroll-behavior auto).
   - Strict preservation of `@media print` rules (A4 portrait, color inversion, clean page-break hygiene).

5. **Mobile Touch Target Bounds (`antislop-layoutmobile`)**:
   - All interactive targets on mobile maintain `>= 44px` minimum height or touch area.
   - Zero horizontal overflow across mobile viewports down to 390px.

---

## Current Behavior (Evidence)

1. **Global Theme & Scrollbar (`web/src/app/globals.css:4-20`)**:
   - Background `#08080a` and foreground `#f4f4f5` are hard-coded in `:root` and `body` without explicit Obsidian surface semantic tokens in Tailwind v4 `@theme inline`.
   - Browser default scrollbars appear on Windows with stark white/gray contrast, breaking the dark Obsidian immersion.
   - Text rendering smoothing flags (`-webkit-font-smoothing`, `-moz-osx-font-smoothing`, `text-rendering`) are missing from `html` and `body`.

2. **Navbar Header Immersion (`web/src/components/Navbar.tsx:31-95`)**:
   - Sticky navbar uses solid opaque `bg-[#08080a]` without backdrop blur (`backdrop-blur-md`), creating a harsh cut when page content scrolls underneath.
   - Brand logo lacks tactile click feedback and spring response.
   - Active navigation pill uses `stiffness: 260, damping: 25`, which can feel slightly sluggish compared to modern snappy navigation bars.
   - Focus rings on nav items and GitHub button lack explicit cyan focus rings with dark offsets.

3. **SpotlightCard Motion & Sheen (`web/src/components/SpotlightCard.tsx:37-60`)**:
   - Uses a single radial gradient layer (`400px circle`) with static border inset shadow.
   - Lacks tactile hover lift (`hover:-translate-y-0.5`) and ease-out elevation.
   - Touch devices trigger mousemove state recalculations unnecessarily without active hover capability.

4. **BlueprintReader Typography & Spatial Harmony (`web/src/components/BlueprintReader.tsx:92-157, 540-840`)**:
   - Sticky action sub-header (line 541) uses solid opaque `bg-[#08080a]` without backdrop blur.
   - Action buttons in sub-header lack tactile active press states (`active:scale-[0.97]`).
   - Code block terminal header has slightly muted contrast on copy buttons.
   - Table of contents links on desktop lack smooth transition-colors and subtle hover backgrounds.
   - Keyboard shortcuts modal dialog lacks backdrop blur and tactile dismiss button response.

---

## Proposed Changes

### 1. Design Tokens, Font Smoothing & Scrollbars (`web/src/app/globals.css`)
- **Semantic Obsidian Tokens**: Add Obsidian surface scale and transition easing tokens to `@theme inline`:
  ```css
  @theme inline {
    --color-background: var(--background);
    --color-foreground: var(--foreground);
    --font-sans: var(--font-geist-sans);
    --font-mono: var(--font-geist-mono);
    --color-obsidian-950: #050507;
    --color-obsidian-900: #08080a;
    --color-obsidian-850: #0d0e12;
    --color-obsidian-800: #12141a;
    --color-obsidian-border: rgba(255, 255, 255, 0.07);
    --color-obsidian-border-subtle: rgba(255, 255, 255, 0.04);
    --color-obsidian-border-hover: rgba(255, 255, 255, 0.14);
    --color-obsidian-glow: rgba(6, 182, 212, 0.12);
  }
  ```
- **Typography Smoothing**:
  ```css
  html {
    scroll-behavior: smooth;
  }
  body {
    background-color: #08080a;
    color: #f4f4f5;
    min-height: 100vh;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  ```
- **Custom Obsidian Scrollbars & Selection**:
  ```css
  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  ::-webkit-scrollbar-track {
    background: #08080a;
  }
  ::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 9999px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.25);
  }
  ::selection {
    background-color: rgba(6, 182, 212, 0.25);
    color: #ffffff;
  }
  ```
- **Preservation**: Retain `@media (prefers-reduced-motion: reduce)` and `@media print` rules in full without alteration.

### 2. Navbar Tactile Motion & Visual Depth (`web/src/components/Navbar.tsx`)
- **Sticky Glass Shell**:
  Change header from `bg-[#08080a]` to `bg-[#08080a]/85 backdrop-blur-md border-b border-white/[0.07] transition-colors duration-200`.
- **Brand Logo Tactile Response**:
  - Add `active:scale-95 group-hover:scale-[1.03] transition-transform duration-200 ease-out` on logo container.
  - Add accessible focus ring: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#08080a]`.
- **Navigation Items & Active Pill**:
  - Container: `bg-zinc-900/90 border border-white/[0.06] p-1 rounded-lg`.
  - Links: Add `active:scale-[0.98] transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-900`.
  - Active pill spring: Update spring parameters to `{ type: "spring", stiffness: 380, damping: 28 }` for crisp responsiveness.
- **GitHub Link**:
  - Add `hover:bg-zinc-800 hover:border-white/[0.16] active:scale-95 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400`.

### 3. SpotlightCard Dual-Sheen & Tactile Hover Lift (`web/src/components/SpotlightCard.tsx`)
- **Dual Radial Spotlight**:
  Replace single gradient with a refined layered glow:
  - Concentrated core: 160px radius at `spotlightColor`.
  - Ambient halo: 420px radius with softer opacity (`rgba(6, 182, 212, 0.04)`).
- **Tactile Hover Elevation**:
  Update container classes:
  ```tsx
  className={cn(
    "relative rounded-xl border border-white/[0.07] bg-[#0d0e12] overflow-hidden transition-all duration-200 ease-out group",
    "hover:border-white/[0.14] hover:-translate-y-0.5 hover:shadow-xl hover:shadow-cyan-950/20 active:translate-y-0",
    "motion-reduce:hover:translate-y-0 motion-reduce:transition-none",
    className
  )}
  ```
- **Dynamic Border Sheen**:
  Enhance border highlight overlay with ease-out opacity transition.

### 4. BlueprintReader Typography Hierarchy & Tactile Feedback (`web/src/components/BlueprintReader.tsx`)
- **Sticky Action Sub-Header**:
  - Apply `bg-[#08080a]/90 backdrop-blur-md border-b border-white/[0.07]`.
  - Enhance all action buttons (Share, Copy Spec, Download, Print, Shortcuts) with tactile press `active:scale-[0.97] transition-all duration-150` and visible focus-visible rings.
- **Typography & Markdown Rendering**:
  - Headings: Refine tracking and borders:
    - H1: `text-2xl sm:text-3xl font-bold tracking-tight text-zinc-50 pb-3 border-b border-white/[0.08] mt-8 mb-4`
    - H2: `text-xl sm:text-2xl font-semibold tracking-tight text-zinc-100 pb-2 border-b border-white/[0.06] mt-8 mb-3`
    - H3: `text-base sm:text-lg font-semibold tracking-tight text-zinc-200 mt-6 mb-2`
  - Inline Code: `font-mono text-cyan-300 bg-zinc-900/90 border border-cyan-500/20 px-1.5 py-0.5 rounded text-[12px]`.
  - Blockquotes: `border-l-2 border-cyan-500 bg-cyan-950/20 py-3 px-4 rounded-r-lg my-5 text-zinc-300 font-sans not-italic`.
  - Code Block Terminal: Add `active:scale-95` on copy button and refined border contrast `border-white/[0.08]`.
  - Section Hash Copy: Ensure `active:scale-90` tactile feedback on anchor clicks.
- **Table of Contents (Desktop & Mobile)**:
  - Mobile TOC: Preserve `>= 44px` touch targets with smooth chevron rotation.
  - Desktop TOC: Elevated surface with `bg-[#0c0d12]/90 backdrop-blur-md border border-white/[0.08] p-4 rounded-xl`, active cyan indicator, and smooth hover backgrounds.
- **Keyboard Shortcuts Dialog**:
  - Dialog backdrop: `bg-black/80 backdrop-blur-md`.
  - Modal card: `bg-zinc-900/95 border border-white/[0.12] shadow-2xl p-6 rounded-xl`.
  - Kbd tags: `px-2 py-0.5 text-xs font-mono font-semibold rounded bg-zinc-800 text-cyan-300 border border-white/[0.12] shadow-sm`.
  - Dismiss button: `active:scale-95 transition-all min-h-[36px]`.

### 5. Task Ledger (`docs/contexts/task-ledger.md`)
- Add Task 6.1 under Phase 6 with summary of shell, theme, cards, and blueprint reader design polish.

---

## Hermetic Test Plan

1. **Python Backend & CLI Suite**:
   - `uv run python -m unittest discover tests`
   - Must pass 203 tests hermetically offline with zero network access.

2. **Next.js Web Lint & Production Build**:
   - `cd web; npm run lint ; npm run build`
   - Zero ESLint errors or warnings.
   - Successful compilation with Next.js 16.4.0 (Turbopack) and TypeScript 5.

3. **Style & antislop Audit**:
   - Zero em dashes (`\u2014`) across all 5 target files.
   - Verified via programmatic scan.

---

## Playwright MCP Verification Checkpoints

The Builder must capture two Playwright visual verification screenshots:

1. **Desktop Viewport (1440 x 900)**:
   - Command/Action: Resize viewport to 1440x900, navigate to `http://localhost:3000/blueprints/1` (or local equivalent).
   - Verify: Obsidian theme `#08080a`, sticky backdrop-blur navbar, dual-sheen spotlight cards, desktop TOC sidebar, typography hierarchy, and code block headers.
   - Target File: `workflow/stages/02_build/output/task-6.1-desktop.png`

2. **Mobile Viewport (390 x 844)**:
   - Command/Action: Resize viewport to 390x844 (iPhone 14 / modern standard mobile), navigate to `http://localhost:3000/blueprints/1`.
   - Verify: Responsive reflow, collapsible mobile TOC details dropdown, minimum 44px tap targets, zero horizontal scroll overflow.
   - Target File: `workflow/stages/02_build/output/task-6.1-mobile.png`

---

## Out of Scope

- Modifying API route handlers (`/api/skill-gap`, `/api/revalidate`).
- Backend database schema or scraper alterations.
- Installing new third-party animation libraries or design packages.
