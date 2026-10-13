# Plan: Task 2.4 — Eliminate Duplicate Client Mount Query & API Memoization

**Date:** 2026-10-14  
**Task ID:** 2.4  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 2.4), `docs/audits/2026-10-12-architecture-reflection.md` (Section 2.4, Section 3.1 P2 row), `AGENTS.md` (Definitions & Invariants)

---

## Goal
Eliminate redundant client-side re-fetching on initial mount in `SkillGapMatcher.tsx` and implement in-memory memoization with a 10-minute TTL for `calculateSkillGap` / `/api/skill-gap` to eliminate repetitive Turso database full-scans.

---

## Disagreements / Alignment Notes
1. **Memoization Layer**:  
   The remediation plan mentions:
   > "In `web/src/app/api/skill-gap/route.ts`, memoize the in-memory skill map with a 10-minute TTL."
   
   Architecture reflection Section 2.4 & 3.1 clarifies that the heavy cost amplification vector is the Turso full-table scan and blueprint JSON parsing performed inside `calculateSkillGap` in `web/src/lib/turso.ts`. If we only memoize in `route.ts`, server-side calls from `analytics/page.tsx` remain unmemoized, and requests with different permutations of skills would still trigger uncached Turso full-table scans.  
   **Alignment:**
   - In `web/src/lib/turso.ts`: Memoize the base dataset (`jobSkillsMap`, `canonicalMap`, `overallFrequency`, `salaryMap`, `allProjects`) with a 10-minute TTL and in-flight promise deduplication.
   - In `web/src/app/api/skill-gap/route.ts`: Implement a 10-minute TTL response cache keyed by canonical sorted skills (`fastapi,python`) and return HTTP 503 instead of 500 when database services are unavailable.
   - In `web/src/app/api/revalidate/route.ts`: Purge the in-memory memoized caches when on-demand revalidation is triggered by CI.

2. **Error Status Code Parity**:  
   Section 3.1 of the architecture reflection calls for returning HTTP 503 instead of 200 with zeroed stats on service error. We align `route.ts` error handlers to return HTTP 503 Service Unavailable when `calculateSkillGap` encounters an unrecoverable failure.

---

## Current Behavior (Evidence)
1. **Unconditional Fetch on Client Mount**:  
   - In `web/src/components/SkillGapMatcher.tsx:109-144`:
     ```typescript
     useEffect(() => {
       ...
       async function fetchGap() {
         setIsLoading(true);
         try {
           const res = await fetch("/api/skill-gap", {
             method: "POST",
             headers: { "Content-Type": "application/json" },
             body: JSON.stringify({ userSkills: selectedSkills }),
             signal: controller.signal,
           });
           ...
     ```
     `useEffect` executes on initial mount, firing a POST request with `{"userSkills": ["Python", "FastAPI"]}` even though `initialData` was already computed by the server during SSR/ISR and passed via `initialData` props. In React 18/19 StrictMode (and during fast client navigation), this fires multiple duplicate requests.

2. **Uncached API Route Executions**:  
   - In `web/src/app/api/skill-gap/route.ts:9-27` and `29-48`:
     Every call to `POST` or `GET` immediately executes `calculateSkillGap(sanitizedSkills)` without any response or dataset caching.

3. **Repetitive Turso Full-Table Scans**:  
   - In `web/src/lib/turso.ts:428-459`:
     Every call to `calculateSkillGap()` issues 3 Turso queries (`skills_extracted` scan, `getAllProjects()`, and grouped compensation query) and iterates through all extracted skills to rebuild `jobSkillsMap`. At 300+ jobs, this burns serverless compute and Turso free-tier row reads needlessly.

---

## Changes

### 1. `web/src/components/SkillGapMatcher.tsx`
- Add order-agnostic, case-insensitive comparison helper `areSkillSetsEqual(a?: string[], b?: string[]): boolean`.
- Track the last fetched or initialized skill set using `useRef<string[] | null>(initialData?.userSkills ?? null)`.
- In `useEffect([selectedSkills])`:
  - Check if `areSkillSetsEqual(selectedSkills, lastFetchedSkillsRef.current ?? undefined)`.
  - If equal, return immediately without calling `fetch("/api/skill-gap", ...)`.
  - When a fetch completes successfully, update `lastFetchedSkillsRef.current = selectedSkills`.

### 2. `web/src/lib/turso.ts`
- Define `SkillGapBaseData` interface:
  ```typescript
  export interface SkillGapBaseData {
    jobSkillsMap: Map<string, Set<string>>;
    canonicalMap: Map<string, string>;
    overallFrequency: Map<string, number>;
    salaryMap: Map<string, { avgSalary: number; sampleCount: number }>;
    allProjects: ProjectIdea[];
    timestamp: number;
  }
  ```
- Implement `getSkillGapBaseData()`:
  - Cache snapshot with a 10-minute TTL (`const SKILL_GAP_CACHE_TTL_MS = 10 * 60 * 1000`).
  - Deduplicate concurrent in-flight fetches with a singleton `baseDataPromise`.
  - If Turso is unconfigured, return safe fallback baseline without error.
  - If Turso query fails, fall back to existing expired cache if available before throwing.
- Refactor `calculateSkillGap(userSkills: string[] = [])`:
  - Await `getSkillGapBaseData()` instead of executing raw SQL queries directly.
  - Perform candidate skill matching and blueprint ranking purely in-memory against the memoized base dataset.
- Export `clearSkillGapCache()`:
  - Resets cached base data so on-demand revalidation can force an immediate refresh.

### 3. `web/src/app/api/skill-gap/route.ts`
- Maintain an in-memory response cache with a 10-minute TTL:
  - Cache key: sorted, normalized, comma-separated skill string (e.g. `fastapi,python`).
  - Cache entry: `{ data: SkillGapResponse; expiresAt: number }`.
- In `POST` and `GET`:
  - Check response cache before calling `calculateSkillGap()`.
  - If present and valid, return cached JSON.
  - If not cached, compute result, store in cache with 10-minute expiration, and return.
- On caught errors:
  - Return HTTP 503 Service Unavailable (`{ error: "Service temporarily unavailable" }`).
- Export `clearSkillGapResponseCache()` to flush response cache on revalidate.

### 4. `web/src/app/api/revalidate/route.ts`
- In the revalidation handler, import and call `clearSkillGapCache()` from `@/lib/turso` and `clearSkillGapResponseCache()` from `@/app/api/skill-gap/route` so daily pipeline completion clears all in-memory caches immediately.

---

## Tests to Add / Update

### In `web/` (Build & Lint Verification):
1. **`npm run lint`**:
   - Must pass cleanly with 0 lint errors or warnings.
2. **`npm run build`**:
   - Must build cleanly with Turbopack, verifying all TypeScript types and exports.

### In `tests/`:
3. Run existing Python test suite (`uv run python -m unittest discover tests`) to confirm hermetic pipeline passes (197 passed).

---

## Out of Scope
- Task 3.x / Post-Phase 2 items.
- Modifying Turso database schema or SQL tables.
- Adding third-party caching dependencies (Redis, Upstash) — standard library / in-memory JS Maps preserve 100% free-tier invariant.

---

## Production Touch Points
- None. No database writes, migrations, or CI configuration changes required.
