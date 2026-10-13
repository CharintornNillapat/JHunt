# Build Report: Task 2.3 — ISR Caching & On-Demand Revalidation

**Task:** 2.3  
**Spec Reference:** `workflow/stages/01_spec/output/task-2.3-spec.md`  
**Test Suite:** 197 passed (`uv run python -m unittest discover tests`), `npm run lint` & `npm run build` passed.

---

## Changes Implemented

1. **`web/src/app/page.tsx` (Homepage ISR Transition)**:
   - Removed `export const dynamic = "force-dynamic";`.
   - Updated `export const revalidate = 3600;` (1-hour stale-while-revalidate window).

2. **`web/src/app/analytics/page.tsx` (Analytics ISR Transition)**:
   - Removed `export const dynamic = "force-dynamic";`.
   - Removed `export const fetchCache = "force-no-store";`.
   - Updated `export const revalidate = 3600;` (1-hour stale-while-revalidate window).

3. **`web/src/app/api/revalidate/route.ts` (On-Demand Revalidation Endpoint)**:
   - Created secure `POST` route handler.
   - Validates `x-revalidate-token` header against `process.env.REVALIDATE_TOKEN`.
   - Returns HTTP 401 Unauthorized on missing or mismatched token.
   - Returns HTTP 500 on server misconfiguration if `REVALIDATE_TOKEN` is unset.
   - Calls `revalidatePath("/")` and `revalidatePath("/analytics")` to purge edge CDN cache immediately.
   - Returns HTTP 200 `{ revalidated: true, paths: ["/", "/analytics"], now: Date.now() }`.

4. **`.github/workflows/scraper_cron.yml` (CI Webhook Step)**:
   - Added Step 8 (`Revalidate Dashboard ISR Cache`) after job state cache save.
   - Guarded with `if: success()` and shell check `if [ -n "$SITE_URL" ] && [ -n "$REVALIDATE_TOKEN" ]` to guarantee non-fatal execution when secrets are not yet configured.

---

## Verification Status

- **Hermetic Unit Tests**: 197 passed, 0 failures, 0 errors (`uv run python -m unittest discover tests`).
- **Web Verification**:
  - `npm run lint` passed (clean exit 0).
  - `npm run build` passed:
    - `/` classified as ISR route (`Revalidate 1h, Expire 1y`).
    - `/analytics` classified as ISR route (`Revalidate 1h, Expire 1y`).
    - `/api/revalidate` compiled as dynamic API route handler (`ƒ /api/revalidate`).
- **Git Diff Scope**: Modified files strictly limited to `.github/workflows/scraper_cron.yml`, `web/src/app/page.tsx`, `web/src/app/analytics/page.tsx`, `web/src/app/api/revalidate/route.ts`, and `workflow/stages/02_build/output/build-report.md`.
- **Production Touch Points**:
  - Zero live database mutations, zero Telegram messages sent, zero Gemini quota consumed.
  - Requires user configuration of `SITE_URL` and `REVALIDATE_TOKEN` in GitHub Secrets and Vercel Environment Variables.
  - Per `AGENTS.md`, pushing changes to `.github/workflows/` requires explicit user confirmation.
