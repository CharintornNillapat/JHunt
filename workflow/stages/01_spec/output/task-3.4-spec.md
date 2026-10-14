# Plan: Task 3.4 — Code Snippet Clipboard & Blueprint Deep-Linking UX in BlueprintReader.tsx

**Date:** 2026-10-14  
**Task ID:** 3.4  
**Reference:** `docs/contexts/task-ledger.md` (Phase 3), `AGENTS.md` (Definitions & Invariants), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Elevate the technical reading experience in `BlueprintReader.tsx` by adding line count metadata, robust clipboard copy with fallback, and keyboard-accessible code snippet actions, while implementing comprehensive blueprint deep-linking with hoverable section anchor links, URL hash synchronization, initial hash scroll restoration, and a header share button, all conforming to antislop Mode 1 (DURING) and WCAG AA standards.

---

## antislop & UX Protocol (Mode 1: DURING)

This specification strictly applies the `antislop` suite (`antislop`, `antislop-ui`, `antislop-layoutmobile`, `antislop-human`, `antislop-copywriting`, `antislop-code`):

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) anywhere in copy, tooltips, toast feedback, button labels, or placeholders.
   - Use colons, commas, periods, or parentheses instead.
2. **R-03 (Mobile Responsiveness & Tap Targets)**:
   - Code snippet copy buttons, section anchor link triggers, and sub-header action buttons must maintain $\ge 44\text{px}$ touch targets on mobile viewports.
   - Syntax body horizontal overflow must be cleanly contained with responsive font scaling (`text-xs sm:text-[13px]`) and smooth touch scrolling.
   - Zero horizontal overflow across the page layout on mobile screens ($320\text{px}$ to $428\text{px}$).
3. **R-25 (Color Contrast — WCAG AA)**:
   - Anchor links, line count badges, and action buttons must meet WCAG AA contrast $\ge 4.5:1$ against dark surfaces (`#08080a`, `#0c0d12`, `zinc-900`).
   - Line count and metadata badges: `text-zinc-400` on `bg-zinc-800` (contrast $> 4.8:1$).
   - Active copied feedback: `text-emerald-400` with `bg-emerald-950/60` (contrast $> 6.5:1$).
4. **R-26 (Interactive Elements)**:
   - Every copy button and anchor link must perform real, verifiable clipboard writes with visual confirmation and zero dead controls.
   - Heading anchor buttons must update the browser URL hash without triggering full page reloads or layout jumps.
5. **R-27 (UI States)**:
   - Explicit default, hover, focused, and copied states for code snippet headers and section anchor links.
   - Graceful clipboard fallback if browser permissions or secure context restrict the Clipboard API.
6. **R-32 (Keyboard Accessibility)**:
   - Heading anchor buttons and code snippet copy buttons must be focusable via `Tab`, activatable via `Enter` / `Space`, with visible focus indicators (`focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950`).
   - Include `aria-live="polite"` feedback for screen-reader users upon copying.
7. **R-35 (Craftsmanship Verification)**:
   - Verified via clean lint, production build, and click-through audit across desktop and mobile screens.

---

## Current Behavior (Evidence)

1. **Basic Code Snippet Clipboard Header (`web/src/components/BlueprintReader.tsx:57-114`)**:
   - `CodeBlockComponent` provides a basic copy button, but lacks:
     - Line count metadata (e.g. `24 lines`) to give engineers immediate sense of snippet scale.
     - Specific accessible labels (generic `title="Copy code snippet"` rather than `aria-label="Copy {language} snippet"`).
     - Screen-reader announcement (`aria-live="polite"`) when copying succeeds.
     - Fallback handling if `navigator.clipboard.writeText` fails or is blocked in non-secure or iframe contexts.

2. **No Section Deep-Linking or Anchor Copying (`web/src/components/BlueprintReader.tsx:299-324`)**:
   - While `h2` and `h3` components generate slugified `id` attributes, there is no way for a reader to copy a direct link to a specific section.
   - Hovering over a heading shows no anchor link (`#` or link icon).
   - Sharing a specific section (e.g., `#database-schema` or `#concurrency-challenges`) requires manually inspecting the DOM or hand-crafting the URL.

3. **URL Hash Desynchronization on Navigation (`web/src/components/BlueprintReader.tsx:196-224, 435-490`)**:
   - Clicking a Table of Contents (TOC) link calls `scrollToHeading(id)`, which calls `element.scrollIntoView({ behavior: "smooth" })`, but calls `e.preventDefault()` without updating the browser URL bar.
   - Consequently, bookmarking, copying the browser URL, or refreshing the page loses the reader's position.
   - Furthermore, navigating directly to a deep-linked URL (e.g. `/blueprints/1#system-architecture`) does not automatically scroll to the target heading on initial mount.

4. **Missing Quick Share Action in Header (`web/src/components/BlueprintReader.tsx:389-417`)**:
   - The sticky action sub-header provides "Copy Raw Spec" and "Download .md", but lacks a "Share / Copy Link" button to easily copy the canonical URL or current section deep link.

---

## Changes

### 1. Enhanced Code Snippet Clipboard & Metadata UX
- **File**: `web/src/components/BlueprintReader.tsx`
- **Line Count & Metadata Badge**:
  - Calculate line count from `codeString`: `const lineCount = useMemo(() => codeString.split("\n").length, [codeString])`.
  - In the code block header, display a metadata badge:
    ```tsx
    <span className="text-[10px] font-mono text-zinc-400 px-2 py-0.5 rounded bg-zinc-800/80 border border-white/[0.06]">
      {lineCount} {lineCount === 1 ? "line" : "lines"}
    </span>
    ```
- **Robust Clipboard Copy with Fallback**:
  - Implement robust copy helper with fallback to `document.execCommand("copy")` if `navigator.clipboard` is restricted:
    ```typescript
    const copyToClipboard = async (text: string): Promise<boolean> => {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
          return true;
        }
      } catch {
        // Fallback for non-secure context or restricted permission
      }
      try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const success = document.execCommand("copy");
        document.body.removeChild(textArea);
        return success;
      } catch {
        return false;
      }
    };
    ```
- **Accessibility & Touch Targets**:
  - Touch target size: `min-h-[36px] sm:min-h-[32px] px-2.5 py-1` with comfortable touch padding.
  - `aria-label={`Copy ${language || "code"} snippet`}`.
  - Visible focus ring: `focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-900`.
  - Screen reader live region: `<span className="sr-only" aria-live="polite">{copied ? "Code copied to clipboard" : ""}</span>`.

### 2. Section Deep-Linking & Heading Anchor UX
- **File**: `web/src/components/BlueprintReader.tsx`
- **Heading Anchor Buttons**:
  - For `h2` and `h3` components, render an anchor copy button alongside the heading text:
    ```tsx
    h2(props) {
      ...
      return (
        <h2 id={id} className="group relative scroll-mt-32 ...">
          <span className="flex items-center justify-between gap-3">
            <span>{props.children}</span>
            <button
              type="button"
              onClick={() => handleCopySectionLink(id)}
              aria-label={`Copy link to section: ${getNodeText(props.children)}`}
              title="Copy link to section"
              className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity p-1 text-zinc-500 hover:text-cyan-400 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            >
              {copiedSectionId === id ? (
                <Check className="h-4 w-4 text-emerald-400" />
              ) : (
                <Hash className="h-4 w-4" />
              )}
            </button>
          </span>
        </h2>
      );
    }
    ```
  - Clicking the anchor:
    - Copies `${window.location.origin}${window.location.pathname}#${id}` to clipboard.
    - Updates browser URL without page reload via `window.history.replaceState(null, "", `#${id}`)`.
    - Shows temporary checkmark feedback on that specific heading.
    - Announces to screen reader: `"Link to section copied to clipboard"`.

### 3. URL Hash Synchronization & Initial Mount Scroll
- **File**: `web/src/components/BlueprintReader.tsx`
- **TOC Click Synchronization**:
  - In `scrollToHeading(id)`:
    - Update browser address bar hash: `window.history.replaceState(null, "", `#${id}`)`.
    - Scroll smoothly to target element.
- **Initial Mount Hash Detection**:
  - In `useEffect`:
    - Check `window.location.hash`.
    - If non-empty, strip the leading `#`, locate the element, and trigger smooth scroll to the section:
      ```typescript
      useEffect(() => {
        if (typeof window !== "undefined" && window.location.hash) {
          const targetId = window.location.hash.replace(/^#/, "");
          const timer = setTimeout(() => {
            const el = document.getElementById(targetId);
            if (el) el.scrollIntoView({ behavior: "smooth" });
          }, 200);
          return () => clearTimeout(timer);
        }
      }, []);
      ```

### 4. Quick Share Action in Sticky Action Sub-Header
- **File**: `web/src/components/BlueprintReader.tsx`
- **Button & Feedback**:
  - Add "Share Link" action button in the sub-header quick-action group:
    ```tsx
    <button
      onClick={handleShareLink}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-white/[0.08] transition-all min-h-[36px]"
      aria-label="Copy direct blueprint link"
    >
      {copiedShare ? (
        <>
          <Check className="h-3.5 w-3.5 text-emerald-400" />
          <span className="text-emerald-400">Copied Link</span>
        </>
      ) : (
        <>
          <Share2 className="h-3.5 w-3.5 text-zinc-400" />
          <span className="hidden sm:inline">Share Link</span>
          <span className="sm:hidden">Share</span>
        </>
      )}
    </button>
    ```
  - Copies current canonical link including any active hash.

---

## Verification & Definition of Done

### 1. Web Suite Verification:
- `cd web; npm run lint`: Must pass with 0 errors and 0 warnings.
- `cd web; npm run build`: Next.js Turbopack production build must compile cleanly.

### 2. Python Hermetic Suite:
- `uv run python -m unittest discover tests`: All 197 hermetic tests must continue to pass.

### 3. antislop Craftsmanship & Click-Through Checklist (R-35):
- **Code Block Verification**:
  - Line count badge displays accurately (e.g. `1 line` or `24 lines`).
  - Clicking "Copy" copies exact code content, transitions to "Copied" with emerald icon for 2 seconds, and provides screen-reader announcement.
  - Fallback logic executes reliably if Clipboard API is restricted.
- **Deep-Linking & Heading Anchors Verification**:
  - Hovering over any H2 or H3 reveals the `#` anchor button.
  - Clicking the anchor button copies the exact deep link (`...#slug`), updates the browser URL bar without page jump, and shows green checkmark confirmation.
  - Clicking any TOC link updates the browser URL bar hash.
  - Refreshing or navigating directly to a URL with `#slug` scrolls directly to that heading.
- **Header Share Button**:
  - Clicking "Share Link" copies the current canonical URL with instant visual feedback.
- **Copywriting Audit (R-02)**:
  - Zero em dashes (`—`) across all new and modified strings.

---

## Out of Scope
- Database schema changes.
- Backend pipeline changes.
- External dependencies.

---

## Production Touch Points
- **None**: Zero database writes, zero Telegram messages, zero Gemini quota consumed.
