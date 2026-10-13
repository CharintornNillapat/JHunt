# Plan: Task 2.2 — Statistically Honest Telemetry

**Date:** 2026-10-13  
**Task ID:** 2.2  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 2.2), `docs/audits/2026-10-12-architecture-reflection.md` (Section 1.3, Section 3.1 P2 row), `AGENTS.md` (Definitions & Invariants)

---

## Goal
Enforce statistical rigor and transparency across analytics dashboards by filtering salary benchmarks to THB-only with a minimum sample size ($n \ge 5$), displaying sample size badges alongside all compensation figures, and removing artificial 1% floors on skill unlock metrics.

---

## Disagreements / Alignment Notes
1. **Sample Size Threshold ($n \ge 5$ vs $n \ge 30$)**:  
   Section 3.1 of the architecture reflection mentions hiding metrics below $n = 30$, while Task 2.2 in the remediation plan specifies $n \ge 5$ for salary benchmarks. Given the current sample size in the Thailand tech market dataset (~259–300 rows total with ~30 disclosed salaries), an $n \ge 30$ threshold would wipe out all salary benchmarks entirely. We strictly adopt the remediation plan's requirement ($n \ge 5$), accompanied by transparent sample size badges (`n=X jobs`).
2. **Location of Unlock Floor**:  
   The remediation plan notes "In `SkillGapMatcher.tsx`, remove artificial `Math.max(1, ...)` floor". Grep confirms the `Math.max(1, ...)` floor actually lives in `web/src/lib/turso.ts:569` inside `calculateSkillGap()`, which computes the data passed to `SkillGapMatcher`. We fix both the calculation in `turso.ts` and ensure `SkillGapMatcher.tsx` renders 0% honestly.

---

## Current Behavior (Evidence)
1. **Unfiltered & Low-Sample Salary Benchmarks**:  
   - In `web/src/lib/turso.ts:175`, `topCompensatedSkills` filters on `salary_count >= 1`, allowing single-job outliers to skew top compensation.
   - In `web/src/lib/turso.ts:213-221`, the fallback compensation query lacks `j.currency = 'THB'` and uses `HAVING sample_count >= 1`.
2. **Missing Sample Size Badges in UI**:  
   - In `web/src/components/AnalyticsCharts.tsx:308-319`, quick benchmark pills display `฿{item.avg_salary.toLocaleString()}/mo` without stating the sample size $n$.
   - In `web/src/components/SkillGapMatcher.tsx:417-422`, recommended skill cards show `฿{rec.avgSalary}/mo avg` without showing how many job postings that benchmark represents.
3. **Artificial 1% Floor on Unlock Potential**:  
   - In `web/src/lib/turso.ts:569-572`:
     ```typescript
     const unlockPct = Math.max(
       1,
       Math.round((c.unlockCount / totalTechJobs) * 100)
     );
     ```
     When a candidate skill unlocks 0 additional jobs (`c.unlockCount == 0`), it still reports `+1%` market reach.

---

## Changes

### 1. `web/src/lib/turso.ts`
- **Fast Path (via `skill_stats`)**:
  - In `getMarketAnalytics()`, raise the compensation filter threshold from `salary_count >= 1` to `salary_count >= 5`.
- **Fallback Compensation Query**:
  - Add `AND j.currency = 'THB'` to the WHERE clause.
  - Raise `HAVING sample_count >= 1` to `HAVING sample_count >= 5`.
- **`calculateSkillGap()`**:
  - In candidate recommended skills, if reading salaries, enforce `j.currency = 'THB'` and `salary_count >= 5`.
  - Pass `salarySampleCount` in `RecommendedSkill` objects.
  - Remove the artificial floor on `unlockPct`:
    ```typescript
    const unlockPct = totalTechJobs > 0
      ? Math.round((c.unlockCount / totalTechJobs) * 100)
      : 0;
    ```

### 2. `web/src/lib/skill-gap-types.ts`
- Update `RecommendedSkill` interface:
  - Add optional field `salarySampleCount?: number;` to hold sample size $n$.

### 3. `web/src/components/AnalyticsCharts.tsx`
- In header for compensation benchmarks:
  - Update title to `Top Compensated Skills (THB/month, n ≥ 5)` and badge to show minimum threshold `Sample size: n ≥ 5 postings`.
- In quick benchmark pills:
  - Display sample size badge `(n={item.sample_count} jobs)` next to each salary figure.
- In `CustomSalaryTooltip`:
  - Clearly display `฿{data.avg_salary.toLocaleString()}/mo (n={data.sample_count} jobs)`.

### 4. `web/src/components/SkillGapMatcher.tsx`
- In recommended skill cards:
  - Render sample size badge `(n={rec.salarySampleCount})` alongside the average salary.
- In unlock percentage metric:
  - Render `+{rec.unlockPercentage}%` without forcing non-zero display when unlock count is 0.

### 5. `tests/test_storage.py`
- Add unit test verifying that storage records and salary aggregations respect the $n \ge 5$ threshold and `currency = 'THB'` requirement.

---

## Tests to Add / Update

### In `tests/test_storage.py`:
1. `test_skill_stats_filter_by_sample_size`:
   - **Asserts**: Verifies queries for top compensated skills filtering by `salary_count >= 5` correctly exclude skills with 1 to 4 salary disclosures while including skills with 5 or more.
   - **Why it fails today**: Existing tests only assert `salary_count >= 1`.

### In `web/` (TypeScript & React verification):
2. Type check and build verification:
   - `npm run lint`: clean exit 0.
   - `npm run build`: clean production build confirming updated contracts in `skill-gap-types.ts`, `turso.ts`, `AnalyticsCharts.tsx`, and `SkillGapMatcher.tsx`.
3. Node logic assertion:
   - Verify `unlockPct` equals 0 when `unlockCount` is 0.
   - Verify salary benchmarks reject rows with $n < 5$ or `currency != 'THB'`.

---

## Out of Scope
- Task 2.3: ISR revalidation route (`/api/revalidate`) and webhook call from GitHub Actions.
- Task 2.4: Eliminating duplicate client mount query in `SkillGapMatcher.tsx`.

---

## Production Touch Points
- None. (Zero writes to Turso, zero Telegram messages, zero Gemini quota spent).
