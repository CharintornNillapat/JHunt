# Plan: Task 5.2: Desktop Web Reading & Study Refinements in web/

**Date:** 2026-10-14  
**Task ID:** 5.2  
**Reference:** `docs/contexts/task-ledger.md` (Phase 5), `web/src/components/BlueprintReader.tsx`, `web/src/app/globals.css`, `web/src/components/Navbar.tsx`, `antislop` Skill Suite (Mode 1 DURING)  

---

## Goal

Enhance the desktop reading and offline study experience for portfolio architecture blueprints by introducing a dedicated print and PDF export stylesheet (`@media print`), an accessible keyboard shortcuts cheat sheet modal with global key bindings (`?`, `p`, `Esc`), and print-optimized page-break hygiene across architecture specifications and solo depth sections.

---

## antislop & Engineering Protocol (Mode 1: DURING)

This specification adheres to the `antislop` suite (`antislop`, `antislop-code`, `antislop-human`, `antislop-ui`, `antislop-copywriting`) and repository invariants:

1. **R-02 (Copywriting)**:
   - Zero em-dashes anywhere in source code, CSS comments, modal dialog text, or markdown documentation.
   - Use colons, commas, periods, or parentheses instead.
2. **R-35 (Craftsmanship Verification)**:
   - High contrast compliance: text contrast in print mode is >= 12:1 (`#111827` on white); modal contrast on dark chrome is >= 7:1 (WCAG AA requires >= 4.5:1).
   - Touch targets and keyboard navigation: all modal close and shortcut action buttons maintain minimum 36px interactive heights with distinct focus indicators (`focus-visible:ring-2 focus-visible:ring-cyan-400`).
   - Clean page-break controls: prevent orphans and fractured architecture diagrams when exporting to paper or PDF.
3. **Repository Guardrails & Invariants (`AGENTS.md`)**:
   - Zero cost: purely client-side Next.js/React standard features; no external PDF generator libraries or paid APIs added.
   - Hermetic verification: all unit tests continue to pass offline (199 tests).

---

## Current Behavior (Evidence)

1. **Unformatted Print Output (`web/src/components/BlueprintReader.tsx:488-804`, `web/src/app/globals.css`)**:
   - Triggering browser print (`Ctrl+P`) currently captures dark backgrounds (`#08080a`), unreadable low-contrast dark cards, sticky desktop TOCs, sticky top headers, and action buttons.
   - `web/src/app/globals.css` contains no `@media print` rules, causing browser defaults to print dark background colors and fragment code blocks across arbitrary page breaks.
   - There is no direct "Print / Save PDF" trigger button in the blueprint action header.

2. **Hidden Desktop Keyboard Navigation**:
   - Power users reading deep blueprints have no quick discoverability for navigation shortcuts.
   - Pressing `?` does nothing; opening browser print requires native menus rather than single-key quick actions.

3. **Global Navigation Bar in Print (`web/src/components/Navbar.tsx:31`)**:
   - The persistent top navbar is printed on page 1 of printouts, consuming vertical space and obscuring the blueprint document title.

---

## Changes

### 1. Global Print Stylesheet (`web/src/app/globals.css`)
- Add comprehensive `@media print` declarations at the end of `web/src/app/globals.css`:
  - **Page Layout**: Set `@page { margin: 1.5cm; size: A4 portrait; }`.
  - **Color Inversion**: Force `body`, `main`, `article`, and container backgrounds to `#ffffff` and primary text to `#111827`.
  - **UI Suppression**: Hide headers, sticky elements, navigation bars, TOC sidebars, back buttons, and interactive copy buttons:
    ```css
    @media print {
      header,
      nav,
      aside,
      footer,
      .print\:hidden {
        display: none !important;
      }
    }
    ```
  - **Page-Break Hygiene**:
    - Avoid page breaks inside code blocks, tables, solo depth sections, checklist items, and hero HUD cards:
      `break-inside: avoid; page-break-inside: avoid;`
    - Prevent heading orphans:
      `h1, h2, h3 { break-after: avoid; page-break-after: avoid; }`
  - **Code & Syntax Blocks**: Replace dark terminal styles with high-contrast light borders (`#e5e7eb`), light-gray background (`#f3f4f6`), and dark monospace text (`#111827`).

### 2. Print & Shortcuts Actions in `BlueprintReader.tsx`
- **Target File**: `web/src/components/BlueprintReader.tsx`
- **Lucide Icons**: Import `Printer`, `Keyboard`, `X` from `lucide-react`.
- **New State**:
  ```tsx
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  ```
- **Global Keyboard Event Listener (`useEffect`)**:
  - Listen for `keydown` on `window`:
    - If active element is an input, textarea, or contentEditable element, ignore shortcut key events.
    - Key `?` (Shift + `/` or `key === "?"`): Toggle `isShortcutsOpen`.
    - Key `p` or `P` (without Ctrl/Meta or with Ctrl/Meta): Intercept or allow `window.print()`.
    - Key `Escape`: If `isShortcutsOpen` is true, close the modal (`setIsShortcutsOpen(false)`).
- **Action Header Enhancements (lines 515-562)**:
  - Add **Print / Save PDF** button:
    ```tsx
    <button
      onClick={() => window.print()}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-white/[0.08] transition-all min-h-[36px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 print:hidden"
      title="Print or save as PDF (P or Ctrl+P)"
      aria-label="Print blueprint or save as PDF"
    >
      <Printer className="h-3.5 w-3.5 text-zinc-400" />
      <span className="hidden sm:inline">Print / PDF</span>
      <span className="sm:hidden">Print</span>
    </button>
    ```
  - Add **Keyboard Shortcuts** help button:
    ```tsx
    <button
      onClick={() => setIsShortcutsOpen(true)}
      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-white border border-white/[0.08] transition-all min-h-[36px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 print:hidden"
      title="Keyboard shortcuts (?)"
      aria-label="Open keyboard shortcuts cheat sheet"
    >
      <Keyboard className="h-3.5 w-3.5 text-zinc-400" />
      <span className="hidden md:inline text-[11px] px-1 py-0.2 rounded bg-zinc-800 border border-white/[0.06] text-cyan-400">?</span>
    </button>
    ```

### 3. Accessible Keyboard Shortcuts Modal Dialog
- Render an accessible modal dialog in `BlueprintReader.tsx`:
  - `role="dialog"`
  - `aria-modal="true"`
  - `aria-labelledby="shortcuts-dialog-title"`
  - Accessible title: `<h2 id="shortcuts-dialog-title">Keyboard Shortcuts</h2>`
  - Backdrop overlay with smooth transition and click-to-close behavior (`onClick={() => setIsShortcutsOpen(false)}`).
  - Dialog container stops click propagation (`onClick={(e) => e.stopPropagation()}`).
  - Accessible close button with `X` icon, minimum 36px touch target, and `aria-label="Close keyboard shortcuts dialog"`.
  - Shortcuts reference table:
    | Key Combination | Action Description |
    |---|---|
    | `?` | Toggle keyboard shortcuts cheat sheet |
    | `p` / `Ctrl+P` | Print blueprint or export to PDF |
    | `Esc` | Close open dialog or exit overlay |
    | `Tab` / `Shift+Tab` | Navigate interactive controls and checkboxes |
    | `Space` / `Enter` | Toggle section checklists or trigger buttons |
  - Clean focus states and contrast compliance (badges `bg-zinc-800 text-cyan-300 font-mono border border-white/[0.1]`).

### 4. Navbar Print Suppression (`web/src/components/Navbar.tsx`)
- Add `print:hidden` to the outer `<header>` element in `web/src/components/Navbar.tsx` so the navigation bar never leaks into printed copies.

### 5. Task Ledger (`docs/contexts/task-ledger.md`)
- Record Task 5.2 under Phase 5.

---

## Verification Plan

1. **Python Hermetic Test Suite**:
   - Run `uv run python -m unittest discover tests`.
   - Verify all 199 hermetic unit tests pass with 0 failures and 0 errors.

2. **Next.js Web Lint & Production Build**:
   - Run `cd web; npm run lint ; npm run build`.
   - Verify 0 ESLint errors/warnings and successful compilation of all static and dynamic pages.

3. **Accessibility & Contrast Verification**:
   - Inspect modal dialog semantics (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`).
   - Check contrast ratios: modal text >= 7:1 against card background; print stylesheet text >= 12:1 (`#111827` on `#ffffff`).
   - Verify keyboard interactions: pressing `?` toggles dialog, pressing `Esc` closes dialog, backdrop click closes dialog.

4. **antislop Copywriting Audit**:
   - Verify zero em-dashes across all modified files (`globals.css`, `BlueprintReader.tsx`, `Navbar.tsx`, `task-ledger.md`).
