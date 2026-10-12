# tests/test_salary_parser.py
"""
Unit tests for deterministic salary parsing engine.
Asserts contract parity across platform payloads, Thai/English text patterns,
hourly/annual conversions, and noise rejection (phone numbers, postal codes, year ranges).
"""
import unittest
from src.extractor.salary_parser import parse_salary


class TestSalaryParser(unittest.TestCase):
    def test_standard_range_thai_and_english(self):
        # 50,000 - 80,000 THB -> (50000, 80000, 'THB')
        self.assertEqual(parse_salary("50,000 - 80,000 THB"), (50000, 80000, "THB"))
        # 50,000 - 80,000 บาท -> (50000, 80000, 'THB')
        self.assertEqual(parse_salary("50,000 - 80,000 บาท"), (50000, 80000, "THB"))
        # En-dash variation: ฿23,000 – ฿25,000 per month
        self.assertEqual(parse_salary("฿23,000 – ฿25,000 per month"), (23000, 25000, "THB"))

    def test_k_notation_ranges(self):
        # 30k - 50k / 30K - 50K -> (30000, 50000, 'THB')
        self.assertEqual(parse_salary("30k - 50k"), (30000, 50000, "THB"))
        self.assertEqual(parse_salary("30K - 50K"), (30000, 50000, "THB"))
        # 40-60k THB -> (40000, 60000, 'THB')
        self.assertEqual(parse_salary("40-60k THB"), (40000, 60000, "THB"))
        self.assertEqual(parse_salary("30 - 50k THB"), (30000, 50000, "THB"))

    def test_upper_bound_only(self):
        # Up to 120,000 / สูงสุด 120,000 -> (None, 120000, 'THB')
        self.assertEqual(parse_salary("Up to 120,000"), (None, 120000, "THB"))
        self.assertEqual(parse_salary("สูงสุด 120,000"), (None, 120000, "THB"))
        self.assertEqual(parse_salary("Up to 100k THB"), (None, 100000, "THB"))
        self.assertEqual(parse_salary("ไม่เกิน 85,000 บาท"), (None, 85000, "THB"))

    def test_lower_bound_only(self):
        # From 40,000 / เริ่มต้น 40,000 -> (40000, None, 'THB')
        self.assertEqual(parse_salary("From 40,000"), (40000, None, "THB"))
        self.assertEqual(parse_salary("เริ่มต้น 40,000"), (40000, None, "THB"))
        self.assertEqual(parse_salary("40,000+"), (40000, None, "THB"))
        self.assertEqual(parse_salary("40k+"), (40000, None, "THB"))
        self.assertEqual(parse_salary("Starting from 50,000 THB"), (50000, None, "THB"))

    def test_platform_payload_first(self):
        # Dict payload
        payload_dict = {"min": 45000, "max": 65000, "currency": "THB"}
        self.assertEqual(parse_salary(payload_dict), (45000, 65000, "THB"))

        # JSON string payload
        payload_json = '{"min_salary": 50000, "max_salary": 70000, "currency": "USD"}'
        self.assertEqual(parse_salary(payload_json), (50000, 70000, "USD"))

        # Platform payload with reversed order
        reversed_dict = {"min": 90000, "max": 60000}
        self.assertEqual(parse_salary(reversed_dict), (60000, 90000, "THB"))

    def test_description_fallback_when_header_empty(self):
        # When raw_salary_text is empty or negotiable, extracts from description
        desc = "We are seeking a Senior Backend Engineer. We offer 60,000 - 90,000 THB with annual bonus."
        self.assertEqual(parse_salary("Negotiable", desc), (60000, 90000, "THB"))
        self.assertEqual(parse_salary(None, desc), (60000, 90000, "THB"))
        self.assertEqual(parse_salary("ตามตกลง", desc), (60000, 90000, "THB"))

    def test_hourly_and_annual_conversions(self):
        # Hourly 300 - 500 THB/hr -> (300*160, 500*160) = (48000, 80000, 'THB')
        self.assertEqual(parse_salary("300 - 500 THB / hr"), (48000, 80000, "THB"))
        self.assertEqual(parse_salary("500 THB/hr"), (80000, 80000, "THB"))

        # Annual 600,000 - 1,200,000 / year -> (50000, 100000, 'THB')
        self.assertEqual(parse_salary("600,000 - 1,200,000 / year"), (50000, 100000, "THB"))

    def test_foreign_currencies(self):
        self.assertEqual(parse_salary("$3,000 - $5,000 USD"), (3000, 5000, "USD"))
        self.assertEqual(parse_salary("SGD 4,000 - 6,000"), (4000, 6000, "SGD"))

    def test_noise_rejection_guardrails(self):
        # Unrealistic numbers below 15,000 THB (and non-hourly) rejected
        self.assertEqual(parse_salary("5 - 10 THB"), (None, None, "THB"))
        self.assertEqual(parse_salary("5,000 - 10,000 THB"), (None, None, "THB"))

        # Year ranges: 2020 - 2024 rejected
        self.assertEqual(parse_salary("Experience: 2020 - 2024"), (None, None, "THB"))

        # Phone numbers: 081-234-5678 rejected
        self.assertEqual(parse_salary("Call HR: 081-234-5678 for details"), (None, None, "THB"))

        # Postal codes: 10110 rejected
        self.assertEqual(parse_salary("Office at Silom, Bangkok 10110"), (None, None, "THB"))

        # Above maximum threshold (> 1,000,000 THB/month) rejected
        self.assertEqual(parse_salary("2,000,000 - 5,000,000 THB"), (None, None, "THB"))

        # Pure boilerplate strings
        self.assertEqual(parse_salary("Negotiable"), (None, None, "THB"))
        self.assertEqual(parse_salary("ตามตกลง"), (None, None, "THB"))
        self.assertEqual(parse_salary(""), (None, None, "THB"))
        self.assertEqual(parse_salary(None), (None, None, "THB"))

    def test_ot_hourly_mention_does_not_corrupt_salary_period(self):
        self.assertEqual(
            parse_salary("Salary 35,000 - 45,000 THB. OT paid 200 THB/hour."),
            (35000, 45000, "THB"),
        )

    def test_client_or_merchant_counts_not_parsed_as_salary(self):
        self.assertEqual(
            parse_salary(description="We serve 50,000+ merchants across Southeast Asia."),
            (None, None, "THB"),
        )

    def test_project_budget_not_parsed_as_salary(self):
        self.assertEqual(
            parse_salary(description="Project budget 100,000 - 500,000 THB. Great team."),
            (None, None, "THB"),
        )

    def test_foreign_currency_mention_does_not_override_local_thb_salary(self):
        self.assertEqual(
            parse_salary(description="Serving US clients ($). Salary 60,000 THB per month."),
            (60000, 60000, "THB"),
        )

    def test_negotiable_header_with_engineer_count_in_desc_not_overridden(self):
        self.assertEqual(
            parse_salary("Negotiable", "Join our team of 20,000+ engineers worldwide."),
            (None, None, "THB"),
        )

    def test_annual_bonus_without_salary_keyword_rejected(self):
        self.assertEqual(
            parse_salary(description="Company benefits include performance bonus up to 120,000 THB annually."),
            (None, None, "THB"),
        )


if __name__ == "__main__":
    unittest.main()
