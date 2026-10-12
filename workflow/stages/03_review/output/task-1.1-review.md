# Review: Task 1.1 — Salary Parser Precision & Noise Rejection

Task: 1.1
Verdict: PASS
Tests: 167 passed (run by reviewer)

Blocking:
None

Non-blocking:
- `tests/test_salary_parser.py:95` — `self.assertEqual(parse_salary("Not specified"), (None, None, "THB"))` was removed during test cleanup. Although the boilerplate rejection logic in `_extract_from_text` still handles `"not specified"`, keeping the test assertion provides explicit regression coverage for that boilerplate variant.

Rule candidates:
None
