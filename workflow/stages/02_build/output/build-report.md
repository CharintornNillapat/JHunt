# Build Report: Task 1.3 — Structural Error Classification & Gemini Quota Preservation

**Task:** 1.3  
**Spec Reference:** `workflow/stages/01_spec/output/task-1.3-spec.md`  
**Test Suite:** 183 passed (`uv run python -m unittest discover tests`)

---

## Changes Implemented

1. **`src/extractor/gemini_client.py` (Structural Error Classification & Resilience)**:
   - Imported `ValidationError` from `pydantic`.
   - Defined `DEFAULT_OVERALL_DEADLINE = 75.0` (seconds).
   - Updated `is_deadline_or_timeout_error(err)` to inspect `.code == 504` and `.status == 'DEADLINE_EXCEEDED'` before word-boundary regex fallback `\b504\b`.
   - Updated `is_transient_error(err)`:
     - Immediately returns `TransientErrorInfo(False, False, False, False)` if `err` is an instance of `ValidationError` or contains `ValidationError`.
     - Structurally inspects `.code` / `.status_code` (`503`, `429`, `504`, `500`, `502`) and `.status` / `.status_code_name` (`UNAVAILABLE`, `RESOURCE_EXHAUSTED`, `DEADLINE_EXCEEDED`, `INTERNAL`).
     - Uses word-boundary regex patterns (`\b500\b`, `\b502\b`, `\b503\b`, `\b429\b`, `\b504\b`) so numbers like `1500`, `25000`, `50000`, and `5020` are never misclassified as server error codes.
   - Updated `BaseGeminiService._generate()`:
     - Enforces overall wall-clock deadline: tracks `start_time = time.monotonic()` and breaks retry loop if `elapsed + sleep_s >= DEFAULT_OVERALL_DEADLINE`.
     - Passes exception object `e` directly to `is_transient_error(e)` to preserve object attributes (`.code`, `.status`).
     - Separated response parsing/validation into a dedicated `try ... except ValidationError: ... except Exception:` block outside API error handling.
     - Immediately aborts on `ValidationError` without burning subsequent retries against the free-tier daily quota.

2. **`docs/contexts/task-ledger.md`**:
   - Marked Task 1.3 complete under Phase 1.

---

## Tests Added & Verified

- **`tests/test_extractor.py`**:
  - `test_is_transient_error_rejects_numbers_containing_500_and_502`: Asserts numbers like `1500`, `50000`, `25000`, and `5020` evaluate to `is_transient=False`.
  - `test_is_transient_error_rejects_pydantic_validation_error`: Asserts real `pydantic.ValidationError` containing numbers evaluates to `is_transient=False`.
  - `test_is_transient_error_structural_status_codes`: Asserts structural status codes (`503`, `429`, `504`, `500`, `502`) and status enums (`UNAVAILABLE`, `RESOURCE_EXHAUSTED`, `DEADLINE_EXCEEDED`) evaluate correctly, while `400` and `404` evaluate to `False`.
  - `test_generate_aborts_immediately_on_validation_error`: Asserts `_generate` does not retry when response payload fails Pydantic validation (`call_count == 1`, `sleep.call_count == 0`).
  - `test_generate_respects_overall_wall_clock_deadline`: Asserts `_generate` aborts retries when cumulative time exceeds `DEFAULT_OVERALL_DEADLINE`.

---

## Verification Status

- **Hermetic Unit Tests**: 183 passed, 0 failures, 0 errors.
- **Production Touch Points**: None (zero writes to Turso, zero Telegram calls, zero Gemini network calls).
