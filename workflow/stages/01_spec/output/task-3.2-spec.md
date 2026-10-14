# Plan: Task 3.2 — Adaptive Device Performance and Keyboard UX

**Date:** 2026-10-14  
**Task ID:** 3.2  
**Reference:** `docs/contexts/task-ledger.md` (Phase 3), `AGENTS.md` (Definitions & Invariants), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Optimize mobile device battery and GPU efficiency by scaling Three.js constellation particles on viewports below 768px, eliminate potential memory leaks in the Next.js API layer through bounded LRU cache eviction (max 200 entries), and enhance power-user navigation in the Blueprint Catalog with global '/' quick-focus and 'Esc' dismiss keyboard shortcuts, adhering strictly to antislop Mode 1 (DURING) and WCAG AA standards.

---

## antislop & UX Protocol (Mode 1: DURING)

This specification strictly applies the `antislop` suite (`antislop`, `antislop-ui`, `antislop-layoutmobile`, `antislop-human`, `antislop-copywriting`, `antislop-code`):

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) in all copy, tooltips, placeholders, and keyboard shortcut hints.
   - Use colons, commas, periods, or parentheses instead.
2. **R-03 (Mobile Responsiveness & Tap Targets)**:
   - Search input, clear buttons, and shortcut triggers must maintain comfortable, accessible touch targets ($\ge 44\text{px}$ on mobile).
   - Constellation canvas boundary and particle count must reflow gracefully across screen sizes ($320\text{px}$ to $428\text{px}$ mobile up to desktop) with zero horizontal overflow.
3. **R-25 (Color Contrast — WCAG AA)**:
   - Keyboard hint badges (`<kbd>/</kbd>`, `<kbd>Esc</kbd>`) and placeholders must meet WCAG AA contrast $\ge 4.5:1$ against dark surfaces (`text-zinc-400` on `bg-zinc-800` is $> 4.8:1$).
4. **R-26 (Interactive Elements)**:
   - Keyboard shortcuts must work deterministically without interfering with native browser behaviors (e.g., typing `/` in an active input should type the character, not re-focus).
   - Dismissing via `Esc` must cleanly clear query or active tech filter and blur input.
5. **R-27 (UI States)**:
   - Clear visual indicators when search is focused, empty, populated, or filtered.
6. **R-32 (Keyboard Accessibility)**:
   - Full keyboard accessibility with `aria-keyshortcuts="/"`, visible focus rings (`focus-visible:ring-2 focus-visible:ring-cyan-400`), and clean unmount of all event listeners.
7. **R-35 (Craftsmanship Verification)**:
   - Verify build, lint, and test pass with zero errors, zero console warnings, and verify shortcut actions.

---

## Current Behavior (Evidence)

1. **Static Heavy Particle Constellation on Mobile (`web/src/components/ThreeCanvas.tsx:35-42, 170-197`)**:
   - `ThreeCanvas` hardcodes:
     ```typescript
     const NODE_COUNT = 160;
     const BOUNDS = { x: 50, y: 35, z: 40 };
     const MAX_CONNECTIONS = 600;
     ```
   - In the animation loop, computing dynamic proximity lines executes an $O(N^2)$ nested loop:
     $\frac{160 \times 159}{2} = 12,720$ distance calculations per frame, running 60 times per second.
   - On low-power mobile viewports ($< 768\text{px}$), this causes unnecessary GPU and CPU thermal throttling and drains battery life, even though the viewport area is less than half of desktop.

2. **Unbounded In-Memory Response Cache (`web/src/app/api/skill-gap/route.ts:14-15, 48-51, 82-85`)**:
   - `responseCache` is initialized as a simple `new Map<string, CacheEntry>()`.
   - Cached responses are written with `responseCache.set(cacheKey, { data, expiresAt })`.
   - While entries expire logically after 10 minutes (`RESPONSE_CACHE_TTL_MS`), expired keys are never evicted unless manually flushed by `clearSkillGapResponseCache()`. If clients submit hundreds of arbitrary skill combinations, memory consumption grows monotonically without an upper bound.

3. **Missing Power-User Keyboard Shortcuts in Catalog (`web/src/components/BlueprintCatalog.tsx:122-132`)**:
   - `BlueprintCatalog` contains a search input without a ref or keyboard shortcut listeners.
   - Power users must reach for a mouse to focus the search box.
   - Pressing `Esc` does not dismiss or clear the current search query or active tech filter.

---

## Changes

### 1. Adaptive Particle Constellation on Mobile
- **File**: `web/src/components/ThreeCanvas.tsx`
- **Logic & Configuration**:
  - Detect viewport width during canvas initialization:
    ```typescript
    const isMobile = width < 768;
    const NODE_COUNT = isMobile ? 60 : 160;
    const MAX_CONNECTIONS = isMobile ? 200 : 600;
    const BOUNDS = {
      x: isMobile ? 30 : 50,
      y: isMobile ? 30 : 35,
      z: isMobile ? 30 : 40,
    };
    ```
  - On mobile viewports ($< 768\text{px}$):
    - Node count drops from 160 to 60.
    - Proximity loop iterations drop from 12,720 to $\frac{60 \times 59}{2} = 1,770$ per frame (an ~86% reduction in CPU and GPU arithmetic operations).
    - Boundary width (`BOUNDS.x`) scales down from 50 to 30, keeping constellation node density visually rich, crisp, and centered on smaller mobile screens.
  - Maintain `prefers-reduced-motion` static snapshot render and clean unmount context disposal.

### 2. Bounded LRU Cache Eviction in `/api/skill-gap`
- **File**: `web/src/app/api/skill-gap/route.ts`
- **LRU Architecture**:
  - Define `MAX_CACHE_ENTRIES = 200`.
  - Implement zero-dependency LRU semantics utilizing JavaScript `Map` insertion-order guarantees:
    ```typescript
    const MAX_CACHE_ENTRIES = 200;

    function getFromCache(key: string, now: number): SkillGapResponse | null {
      const cached = responseCache.get(key);
      if (!cached) return null;
      if (now >= cached.expiresAt) {
        responseCache.delete(key);
        return null;
      }
      // Refresh LRU recency: re-insert at end of Map
      responseCache.delete(key);
      responseCache.set(key, cached);
      return cached.data;
    }

    function setInCache(key: string, data: SkillGapResponse, now: number): void {
      if (responseCache.has(key)) {
        responseCache.delete(key);
      } else if (responseCache.size >= MAX_CACHE_ENTRIES) {
        // Evict least recently used (first key in Map iterator)
        const oldestKey = responseCache.keys().next().value;
        if (oldestKey !== undefined) {
          responseCache.delete(oldestKey);
        }
      }
      responseCache.set(key, {
        data,
        expiresAt: now + RESPONSE_CACHE_TTL_MS,
      });
    }
    ```
  - Update `POST` and `GET` handlers to use `getFromCache()` and `setInCache()`.
  - Ensure `clearSkillGapResponseCache()` continues to flush all entries cleanly on revalidate.

### 3. Keyboard Navigation Shortcuts in `BlueprintCatalog`
- **File**: `web/src/components/BlueprintCatalog.tsx`
- **Ref & Event Listeners**:
  - Add `searchInputRef = useRef<HTMLInputElement>(null)`.
  - Attach a global `keydown` event listener in `useEffect`:
    ```typescript
    useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        // Ignore shortcut if user is currently typing in an input, textarea, or contentEditable
        const target = e.target as HTMLElement | null;
        const isEditing =
          target?.tagName === "INPUT" ||
          target?.tagName === "TEXTAREA" ||
          target?.isContentEditable;

        // '/' shortcut: focus search input
        if (e.key === "/" && !isEditing) {
          e.preventDefault();
          searchInputRef.current?.focus();
          searchInputRef.current?.select();
          return;
        }

        // 'Escape' shortcut: dismiss query or active tag filter
        if (e.key === "Escape") {
          if (document.activeElement === searchInputRef.current) {
            if (searchQuery) {
              setSearchQuery("");
            } else {
              searchInputRef.current?.blur();
            }
          } else if (selectedTech) {
            setSelectedTech(null);
          } else if (searchQuery) {
            setSearchQuery("");
          }
        }
      };

      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }, [searchQuery, selectedTech]);
    ```
- **UI & Accessibility**:
  - Add `aria-keyshortcuts="/"` to the search input.
  - Render a visual `<kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-400 border border-white/[0.08] pointer-events-none select-none">` indicator inside the search container when empty.
  - When input has text, display an accessible clear button or `Esc` hint to allow immediate dismissal.
  - No em dashes in copy (R-02).
  - High-contrast text meeting WCAG AA $\ge 4.5:1$ (R-25).

---

## Verification & Definition of Done

### 1. Web Suite Verification:
- `cd web; npm run lint`: Must pass with 0 errors and 0 warnings.
- `cd web; npm run build`: Next.js Turbopack production build must compile cleanly.

### 2. Python Hermetic Suite:
- `uv run python -m unittest discover tests`: All 197 hermetic tests must continue to pass.

### 3. antislop Craftsmanship & Click-Through Checklist (R-35):
- **Desktop & Mobile Canvas Verification**:
  - On viewports $< 768\text{px}$, particle count scales to 60 with bounded limits, eliminating stutter and high battery drain.
  - On viewports $\ge 768\text{px}$, full 160-node constellation renders smoothly.
- **Cache Eviction Verification**:
  - `/api/skill-gap` correctly caches up to 200 entries and strictly evicts the least recently used entry when reaching capacity.
- **Keyboard Shortcuts Verification**:
  - Pressing `/` while anywhere on the page focuses the search input and prevents character insertion into the field.
  - Pressing `Esc` while focused clears search text or blurs the input.
  - Pressing `Esc` while an active tech filter is applied resets `selectedTech`.
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
