# Plan: Task 2.3 — ISR Caching & On-Demand Revalidation

**Date:** 2026-10-13  
**Task ID:** 2.3  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 2.3), `docs/audits/2026-10-12-architecture-reflection.md` (Section 2.4, Section 3.1 P2 row), `AGENTS.md` (CI & Stop-and-ask invariants)

---

## Goal
Transition `/` and `/analytics` from `force-dynamic` SSR to Incremental Static Regeneration (ISR with `revalidate = 3600`) and implement an authenticated on-demand cache revalidation endpoint (`/api/revalidate`), allowing GitHub Actions to purge and refresh cache immediately after daily pipeline execution.

---

## Disagreements / Alignment Notes
1. **ISR Stale-While-Revalidate TTL**:  
   Both the remediation plan and architecture reflection agree on `export const revalidate = 3600;` (1 hour background revalidation window). Combined with on-demand cache purging (`revalidatePath`), the dashboard renders near-instantaneously from Vercel edge CDN with zero Turso database hits during normal traffic, while updating within seconds of the daily pipeline finish.
2. **GitHub Actions Workflow Modifications**:  
   Per `AGENTS.md` ("Stop and ask first: gh workflow run|disable|enable, or pushing changes to .github/workflows/"), modifying `.github/workflows/scraper_cron.yml` touches CI configuration. The plan specifies the exact addition to `scraper_cron.yml` with fail-safe secret checks (`if [ -n "$SITE_URL" ] && [ -n "$REVALIDATE_TOKEN" ]`) so unconfigured environments do not fail the workflow. Committing or pushing changes to `.github/workflows/` will be explicitly flagged for user approval.

---

## Current Behavior (Evidence)
1. **Uncached Server-Side Rendering (`force-dynamic`)**:  
   - In `web/src/app/page.tsx:5-6`:
     ```typescript
     export const dynamic = "force-dynamic";
     export const revalidate = 0;
     ```
   - In `web/src/app/analytics/page.tsx:7-9`:
     ```typescript
     export const dynamic = "force-dynamic";
     export const revalidate = 0;
     export const fetchCache = "force-no-store";
     ```
   Every single visitor request triggers live database execution against Turso. Because tech postings only refresh daily, this wastes database bandwidth and compute quota.
2. **Missing Revalidation Webhook**:  
   There is currently no API route in `web/src/app/api/` to trigger on-demand cache invalidation.
3. **CI Does Not Notify Deployment on Complete**:  
   In `.github/workflows/scraper_cron.yml`, the workflow finishes without pinging Vercel edge cache after database ingestion.

---

## Changes

### 1. `web/src/app/page.tsx`
- Remove `export const dynamic = "force-dynamic";`.
- Change `export const revalidate = 0;` to:
  ```typescript
  export const revalidate = 3600;
  ```

### 2. `web/src/app/analytics/page.tsx`
- Remove `export const dynamic = "force-dynamic";`.
- Remove `export const fetchCache = "force-no-store";`.
- Change `export const revalidate = 0;` to:
  ```typescript
  export const revalidate = 3600;
  ```

### 3. `web/src/app/api/revalidate/route.ts` (New File)
- Create secure route handler accepting `POST`:
  - Validates `x-revalidate-token` header against `process.env.REVALIDATE_TOKEN`.
  - Rejects missing or mismatched tokens with HTTP 401 Unauthorized (`{ message: "Unauthorized" }`).
  - Rejects if server lacks `REVALIDATE_TOKEN` environment variable with HTTP 500 (`{ message: "Server misconfiguration" }`).
  - Calls `revalidatePath("/")` and `revalidatePath("/analytics")` from `next/cache`.
  - Returns HTTP 200 `{ revalidated: true, paths: ["/", "/analytics"], now: Date.now() }`.

### 4. `.github/workflows/scraper_cron.yml`
- Add step after state save to trigger on-demand cache invalidation:
  ```yaml
      # ── 8. Revalidate Dashboard ISR Cache ─────────────────────────
      - name: Revalidate Dashboard ISR Cache
        if: success()
        env:
          SITE_URL: ${{ secrets.SITE_URL }}
          REVALIDATE_TOKEN: ${{ secrets.REVALIDATE_TOKEN }}
        run: |
          if [ -n "$SITE_URL" ] && [ -n "$REVALIDATE_TOKEN" ]; then
            echo "Triggering on-demand ISR cache revalidation at $SITE_URL..."
            curl -fsS -X POST -H "x-revalidate-token: $REVALIDATE_TOKEN" "$SITE_URL/api/revalidate" || echo "Warning: Revalidation webhook call failed non-fatally."
          else
            echo "Skipping cache revalidation: SITE_URL or REVALIDATE_TOKEN not configured."
          fi
  ```

---

## Tests to Add / Update

### In `web/` (Build & Route Verification):
1. **`npm run lint`**:
   - Must pass cleanly with 0 lint errors or warnings.
2. **`npm run build`**:
   - Production Next.js Turbopack build must show `/` and `/analytics` classified as ISR/prerendered routes (`● (SSG)` or `ISR (3600s)`) instead of `ƒ (Dynamic)`.
   - `/api/revalidate` must compile cleanly as a route handler.

### In `tests/`:
3. Run existing Python test suite (`uv run python -m unittest discover tests`) to confirm hermetic pipeline passes (197 passed).

---

## Out of Scope
- Task 2.4: Eliminating duplicate client mount query in `SkillGapMatcher.tsx` (Phase 2 final task).
- Adding custom dashboard analytics tracking.

---

## Production Touch Points (GitHub Actions & Vercel Secrets)
- **Vercel / Next.js Environment Variable**: Add `REVALIDATE_TOKEN=<strong-secret>` to Vercel project settings.
- **GitHub Repository Secrets**: Add `SITE_URL=https://jhunt.vercel.app` (or user's deployment URL) and `REVALIDATE_TOKEN=<strong-secret>` to GitHub repository secrets.
- **Workflow Push**: Per `AGENTS.md`, modifications to `.github/workflows/scraper_cron.yml` will be submitted for explicit user approval before pushing.
