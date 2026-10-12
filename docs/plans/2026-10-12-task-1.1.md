# Plan: Task 1.1 — Salary Parser Precision & Noise Rejection

**Date:** 2026-10-12  
**Task ID:** 1.1  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 1.1), `docs/audits/2026-10-12-architecture-reflection.md` (Section 2.2)

---

## Goal
Harden `parse_salary()` against description fallback noise by anchoring description searches to explicit salary keywords, localizing currency and frequency detection to the matched salary substring, and rejecting candidate/merchant count nouns.

---

## Disagreements / Alignment Notes
- None. `2026-10-12-remediation-plan.md` and `2026-10-12-architecture-reflection.md` describe the identical 6 failing edge cases and the window/localized detection solution.

---

## Current Behavior (Evidence)
1. **Global Frequency Pollution:**  
   In `src/extractor/salary_parser.py:184`, `_extract_from_text` runs `_detect_period(norm)` across the entire input text. An incidental mention such as `"OT paid 200 THB/hour"` sets `period = 'hourly'` for the entire posting, causing a valid monthly salary like `"Salary 35,000 - 45,000 THB"` to be multiplied by 160.
2. **Global Currency Pollution:**  
   In `src/extractor/salary_parser.py:183`, `_detect_currency(norm)` scans the full text for `$`, `usd`, etc. A phrase like `"US clients ($)"` relabels an explicit `"Salary 60,000 THB"` to USD.
3. **Metric & Count Ingestion:**  
   In `src/extractor/salary_parser.py:245-255`, `suffix_plus_regex` matches any `\d+\+` pattern. Business metrics like `"50,000+ merchants"` or team sizes like `"20,000+ engineers"` are misparsed as minimum salaries (`min_salary = 50000`).
4. **Unanchored Description Fallback:**  
   In `src/extractor/salary_parser.py:298-301`, `parse_salary` passes the entire unstructured `description` to `_extract_from_text` without requiring salary anchor keywords. Mentions of `"Project budget 100,000 - 500,000 THB"` or annual bonuses are captured as base salaries.
5. **Missing Annual Bonus / Period Tokens:**  
   In `src/extractor/salary_parser.py:64`, `_detect_period` checks `(?:/\s*(?:year|yr|annum)|per\s+(?:year|annum)|ต่อ\s*ปี)`, but omits `annually` and `yearly`.

---

## Changes

### 1. `src/extractor/salary_parser.py`
- **Define Anchor & Noise Patterns**:
  ```python
  RE_SALARY_ANCHOR = re.compile(
      r"(?i)(?:salary|เงินเดือน|ค่าตอบแทน|compensation|remuneration|รายได้|ค่าจ้าง|base\s*salary|offer)\s*[:\s]",
      re.UNICODE,
  )
  RE_COUNT_NOUN = re.compile(
      r"(?i)^\s*(?:merchants?|users?|people|engineers?|customers?|clients?|members?|accounts?|คน|ร้านค้า|ท่าน)\b"
  )
  ```
- **Update `_detect_period`**:
  Include `annually` and `yearly` in the annual regex:
  ```python
  if re.search(r"(?:/\s*(?:year|yr|annum)|per\s+(?:year|annum)|ต่อ\s*ปี|annually|yearly)", lower):
      return "yearly"
  ```
- **Localize Currency & Period Detection in `_extract_from_text`**:
  - Instead of computing `currency` and `period` globally from the entire `text`, determine them from the matched substring and its immediate context (within ~25 characters trailing the match, stopping before delimiters).
  - Check trailing tokens against `RE_COUNT_NOUN`; if matched, reject the number token (e.g. `50,000+ merchants`).
- **Anchor Description Search in `parse_salary`**:
  - When `raw_salary_text` is empty, `"Negotiable"`, or uninformative, inspect `description` **only** within windows (150 chars) following `RE_SALARY_ANCHOR` matches:
    ```python
    if description and isinstance(description, str):
        for anchor_match in RE_SALARY_ANCHOR.finditer(description):
            window = description[anchor_match.end() : anchor_match.end() + 150]
            min_s, max_s, curr = _extract_from_text(window)
            if min_s is not None or max_s is not None:
                return min_s, max_s, curr
    ```
  - If no anchor matches or none yield a valid salary, return `(None, None, "THB")`.

### 2. `docs/contexts/task-ledger.md`
- Mark Task 1.1 complete upon verification.

---

## Tests to Add

### In `tests/test_salary_parser.py`:
1. `test_ot_hourly_mention_does_not_corrupt_salary_period`:
   - **Input**: `"Salary 35,000 - 45,000 THB. OT paid 200 THB/hour."`
   - **Asserts**: `(35000, 45000, "THB")`
   - **Why it fails today**: Global period detection picks up `/hour` and converts to `(32000, 32000, "THB")` or invalid hourly math.
2. `test_client_or_merchant_counts_not_parsed_as_salary`:
   - **Input**: `description = "We serve 50,000+ merchants across Southeast Asia."`
   - **Asserts**: `(None, None, "THB")`
   - **Why it fails today**: `50,000+` matches `suffix_plus_regex` and returns `min_salary = 50000`.
3. `test_project_budget_not_parsed_as_salary`:
   - **Input**: `description = "Project budget 100,000 - 500,000 THB. Great team."`
   - **Asserts**: `(None, None, "THB")`
   - **Why it fails today**: `range_regex` matches `100,000 - 500,000 THB` without an anchor keyword.
4. `test_foreign_currency_mention_does_not_override_local_thb_salary`:
   - **Input**: `description = "Serving US clients ($). Salary 60,000 THB per month."`
   - **Asserts**: `(60000, 60000, "THB")`
   - **Why it fails today**: Global currency detection matches `$` and sets currency to `USD`.
5. `test_negotiable_header_with_engineer_count_in_desc_not_overridden`:
   - **Input**: `raw_salary_text = "Negotiable"`, `description = "Join our team of 20,000+ engineers worldwide."`
   - **Asserts**: `(None, None, "THB")`
   - **Why it fails today**: Description fallback extracts `20,000+` as `min_salary = 20000`.
6. `test_annual_bonus_without_salary_keyword_rejected`:
   - **Input**: `description = "Company benefits include performance bonus up to 120,000 THB annually."`
   - **Asserts**: `(None, None, "THB")`
   - **Why it fails today**: `max_regex` extracts `up to 120,000` as monthly maximum salary 120,000 THB.

---

## Out of Scope
- Task 1.2: One-time historical salary backfill script `scripts/backfill_salaries.py`.
- Task 1.3: Gemini transient error classification.
- Database schema changes.

---

## Production Touch Points
- **Turso Database**: No SQL queries executed or required.
- **Telegram**: No messages sent.
- **Gemini**: No API calls made.
- **CI**: Local modifications only.
