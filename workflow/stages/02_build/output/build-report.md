# Build Report: Task 2.2 — Statistically Honest Telemetry

**Task:** 2.2  
**Spec Reference:** `workflow/stages/01_spec/output/task-2.2-spec.md`  
**Test Suite:** 197 passed (`uv run python -m unittest discover tests`), `npm run lint` & `npm run build` passed.

---

## Changes Implemented

1. **`web/src/lib/turso.ts` (Statistical Rigor in Analytics & Skill-Gap Calculations)**:
   - **Fast Path (`getMarketAnalytics`)**: Raised filter threshold from `salary_count >= 1` to `salary_count >= 5` for `topCompensatedSkills`.
   - **Fallback Path (`getMarketAnalytics`)**: Added `AND j.currency = 'THB'` and raised `HAVING sample_count >= 1` to `HAVING sample_count >= 5` in raw compensation query.
   - **`calculateSkillGap()` Query**: Added `AND j.currency = 'THB'`, `HAVING sample_count >= 5`, and selected `sample_count` alongside `avg_salary`.
   - **`calculateSkillGap()` Metric Mapping**:
     - Removed the artificial 1% floor (`Math.max(1, ...)`). Unlocking 0 additional jobs now honestly reports `0%`.
     - Forwarded `salarySampleCount` from `salaryMap` into each `RecommendedSkill` item.

2. **`web/src/lib/skill-gap-types.ts` (Contract Extension)**:
   - Added `salarySampleCount?: number;` to the `RecommendedSkill` interface.

3. **`web/src/components/AnalyticsCharts.tsx` (Transparent Benchmark Telemetry)**:
   - Updated chart title to `Top Compensated Skills (THB/month, n ≥ 5)`.
   - Updated category badge to `Sample size: n ≥ 5 postings`.
   - Added sample count badge `(n={item.sample_count} jobs)` to quick benchmark pills.
   - Updated `CustomSalaryTooltip` to display `(n={data.sample_count} jobs)`.

4. **`web/src/components/SkillGapMatcher.tsx` (Honest Unlock & Salary Sample Count)**:
   - Rendered sample size badge `(n={rec.salarySampleCount})` alongside average compensation figures in recommended companion cards.
   - Preserved honest unlock potential formatting (`+{rec.unlockPercentage}% reach`) allowing 0% display when no additional jobs are unlocked.

5. **`src/storage/db.py` & `src/storage/turso_client.py` (Storage Parameterized Filtering)**:
   - Extended `get_skill_stats(..., min_salary_count: Optional[int] = None)` to filter `salary_count >= ?` using parameterized SQL and order by `avg_salary_thb DESC`.

6. **`tests/test_storage.py` (Hermetic Unit Testing)**:
   - Added `test_skill_stats_filter_by_sample_size`: verifies filtering by `min_salary_count=5` correctly excludes skills with 1–4 salary disclosures as well as USD salaries, while including skills with $\ge 5$.
   - Added `test_turso_get_skill_stats_filter_by_sample_size`: verifies parameterized query generation and argument passing in `TursoClient`.

---

## Verification Status

- **Hermetic Unit Tests**: 197 passed, 0 failures, 0 errors (`uv run python -m unittest discover tests`).
- **Web Verification**:
  - `npm run lint` passed (clean exit 0).
  - `npm run build` passed (Turbopack production build compiled successfully, all routes valid).
- **Git Diff Scope**: Only the 7 files relevant to Task 2.2 were modified.
- **Production Touch Points**: Zero live Turso writes, zero Telegram messages, zero Gemini API quota consumed.
