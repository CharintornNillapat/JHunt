# Plan: Task 1.3 — Structural Error Classification & Gemini Quota Preservation

**Date:** 2026-10-13  
**Task ID:** 1.3  
**Reference:** `docs/audits/2026-10-12-remediation-plan.md` (Task 1.3), `docs/audits/2026-10-12-architecture-reflection.md` (Section 2.1, Section 3.1 P1 row), `AGENTS.md` (LLM invariants)

---

## Goal
Classify transient Gemini errors structurally by HTTP status code and status enum, abort non-transient Pydantic validation errors immediately without retries, and bound generation retries with a wall-clock deadline.

---

## Disagreements / Alignment Notes
- None. `AGENTS.md`, `2026-10-12-remediation-plan.md`, and `2026-10-12-architecture-reflection.md` all explicitly mandate structural status code checking (`code in {429, 500, 502, 503, 504}`) and forbid substring searching of `str(e)` for digits because job text in Pydantic validation errors frequently contains numbers such as `1500`, `25,000`, and `50,000`.

---

## Current Behavior (Evidence)
1. **Loose Substring Digit Matching in `is_transient_error()`:**  
   In `src/extractor/gemini_client.py:101-131`:
   - `is_server_error` tests `"500" in err_str or "502" in err_str`.
   - `is_503` tests `"503" in err_str`.
   - Any string containing `1500` (e.g. `MAX_DESCRIPTION_CHARS = 1500`), `25,000`, or `50,000` evaluates to `True` for `is_server_error` because `"500"` is a substring.
   - For example: `is_transient_error("1500 jobs")` evaluates to `(True, False, False, False)`.
2. **Pydantic `ValidationError` Caught Inside Retry Loop:**  
   In `src/extractor/gemini_client.py:227-247`:
   - `adapter.validate_python(raw)` and `adapter.validate_json(...)` are executed inside the general `try: ... except Exception as e:` block.
   - When a deterministic schema validation failure occurs, Pydantic raises `pydantic.ValidationError` containing the payload context (such as salaries `50000` or description snippet `1500 chars`).
   - The handler runs `transient_info = is_transient_error(err)`. Because `"500"` is matched, `is_transient` is `True`, causing `_generate` to retry up to `MAX_RETRIES` (4 times), burning up to 4 precious API requests from the daily ~20 request free-tier quota.
3. **Unbounded Retry Wall-Clock Duration:**  
   In `src/extractor/gemini_client.py:224-262`:
   - `_generate()` iterates through `MAX_RETRIES` (4 attempts) without an overarching wall-clock deadline. In worst-case network latency and 503 backoff schedules (5s, 10s, 20s + jitter + 30s request timeouts), retries can stall CI past GitHub Actions job limits.

---

## Changes

### 1. `src/extractor/gemini_client.py`

#### A. Structural Error Inspection in `is_transient_error(err: Any) -> TransientErrorInfo`
- Check whether `err` is an instance of `pydantic.ValidationError` or string containing explicit validation errors; if so, immediately return `TransientErrorInfo(False, False, False, False)`.
- Inspect structural status codes via object attributes:
  - `code = getattr(err, "code", None) or getattr(err, "status_code", None)`
  - `status = getattr(err, "status", None) or getattr(err, "status_code_name", None)`
- If `code` is present as an integer or numeric string:
  - `is_503 = (code == 503) or (status in ("UNAVAILABLE",))`
  - `is_rate_limit = (code == 429) or (status in ("RESOURCE_EXHAUSTED",))`
  - `is_504_or_deadline = (code == 504) or (status in ("DEADLINE_EXCEEDED",))`
  - `is_server_error = (code in (500, 502)) or (status in ("INTERNAL",))`
  - `is_transient = is_503 or is_rate_limit or is_504_or_deadline or is_server_error`
- For fallback string matching (when `err` is a string or generic exception without `.code`):
  - Use regex word-boundary patterns rather than raw substring inclusion:
    - `re.search(r"\b503\b", err_str)` or explicit phrase `"service unavailable"`
    - `re.search(r"\b429\b", err_str)` or `"resource_exhausted"`
    - `re.search(r"\b504\b", err_str)` or `"gateway timeout"` or `"deadline_exceeded"`
    - `re.search(r"\b(500|502)\b", err_str)` or `"internal server error"` or `"bad gateway"`
  - Word boundary `\b500\b` ensures `1500`, `25000`, `50000`, and `5020` do NOT match.

#### B. Separate API Generation from Response Parsing in `_generate`
- Move response validation (`adapter.validate_python` / `adapter.validate_json`) into a separate block or dedicated `try ... except ValidationError:` handler:
  ```python
  try:
      resp = self.client.models.generate_content(model=model, contents=contents, config=config)
  except Exception as e:
      err = str(e)
      if is_daily_quota_exhausted(err):
          raise DailyQuotaExhaustedError(err) from e
      transient_info = is_transient_error(e)
      if not transient_info.is_transient:
          logger.error(f"[{tag}] Non-transient error: {err[:200]}")
          break
      # Backoff and retry transient error...
      ...
      continue

  # Parsing & Validation (Non-transient)
  try:
      raw = getattr(resp, "parsed", None)
      if raw is not None:
          parsed = adapter.validate_python(raw)
      elif getattr(resp, "text", None):
          parsed = adapter.validate_json(resp.text)
      else:
          parsed = None
      if parsed is not None:
          self._consecutive_failures = 0
          return parsed
      logger.warning(f"[{tag}] Attempt {attempt}: empty response.")
  except ValidationError as ve:
      logger.error(f"[{tag}] Schema validation error (non-transient): {ve}")
      break
  except Exception as pe:
      logger.error(f"[{tag}] Response parsing error (non-transient): {pe}")
      break
  ```
- Any `ValidationError` terminates immediately without retrying, preserving the daily request quota.

#### C. Wall-Clock Deadline in `_generate`
- Define `DEFAULT_OVERALL_DEADLINE = 75.0` seconds.
- Record `start_time = time.monotonic()` before entering the retry loop.
- Before sleeping for backoff, verify that `time.monotonic() - start_time + sleep_s < deadline`. If the overall deadline would be exceeded, log a warning and break out of the retry loop.

---

## Tests to Add

### In `tests/test_extractor.py`:
1. `test_is_transient_error_rejects_numbers_containing_500_and_502`:
   - **Asserts**: `is_transient_error("Input exceeded 1500 chars")`, `is_transient_error("Salary 50000 THB")`, `is_transient_error("25000")`, and `is_transient_error("Error in line 5020")` all return `is_transient=False`.
   - **Why it fails today**: Substrings `"500"` and `"502"` match inside these numbers, returning `is_transient=True`.
2. `test_is_transient_error_rejects_pydantic_validation_error`:
   - **Asserts**: Passing a real or mock `ValidationError` containing numbers like `1500` or `50000` evaluates to `is_transient=False`.
   - **Why it fails today**: The exception string contains `"500"`, evaluating to `is_transient=True`.
3. `test_is_transient_error_structural_status_codes`:
   - **Asserts**: Mock error objects with `code=503`, `code=429`, `code=500`, `code=502`, and `code=504` are correctly classified as transient with appropriate flags (`is_503`, `is_rate_limit`, `is_504_or_deadline`), while `code=400` and `code=404` are non-transient.
   - **Why it fails today**: `is_transient_error` does not inspect `.code` attributes structurally.
4. `test_generate_aborts_immediately_on_validation_error`:
   - **Asserts**: When Gemini returns a response whose payload fails Pydantic schema validation, `_generate` logs the error, terminates immediately, and does NOT retry (`call_count == 1`).
   - **Why it fails today**: `ValidationError` is caught in `except Exception:` and misclassified as transient if the payload text contains `1500` or `50000`, retrying 4 times (`call_count == 4`).
5. `test_generate_respects_overall_wall_clock_deadline`:
   - **Asserts**: When transient errors occur but accumulated elapsed time exceeds the overall deadline, `_generate` aborts before exhausting all 4 retries.
   - **Why it fails today**: `_generate` has no wall-clock deadline guard.

---

## Out of Scope
- Task 1.4: Schema reconciliation (`target_role` column vs `role` index in `generated_projects`).
- Task 1.5: Blueprint prompt constraints and markdown exporter formatting.
- Changes to scraper modules or database schemas.

---

## Production Touch Points
- **Turso Database**: Zero writes or queries.
- **Telegram**: Zero messages dispatched.
- **Gemini**: Zero live API calls (all unit tests hermetic with mocks).
- **CI**: Local modifications only.
