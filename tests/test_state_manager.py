# tests/test_state_manager.py
"""
Hermetic unit tests for StateManager ID continuity migration and deduplication.
Verifies bare numeric ID migration to 'jobsdb_' prefix, collision date resolution,
v1 schema migration, and isolation from live data.
"""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from state_manager import StateManager


class TestStateManagerMigration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "seen_jobs.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_migrates_bare_numeric_ids_in_v2_seen(self):
        initial_data = {
            "version": 2,
            "seen": {
                "95104887": "2026-10-10",
                "jobsdb_12345": "2026-10-10",
                "blognone_slug": "2026-10-10",
                "๑๒๓": "2026-10-10",
            },
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        sm = StateManager(state_file=str(self.state_file))
        seen = sm._seen

        self.assertIn("jobsdb_95104887", seen)
        self.assertNotIn("95104887", seen)
        self.assertEqual(seen["jobsdb_95104887"], "2026-10-10")
        self.assertEqual(seen["jobsdb_12345"], "2026-10-10")
        self.assertEqual(seen["blognone_slug"], "2026-10-10")
        # Non-ASCII digits like Thai numerals must NOT be prefixed
        self.assertIn("๑๒๓", seen)
        self.assertNotIn("jobsdb_๑๒๓", seen)

    def test_load_migrates_bare_numeric_ids_in_v1_legacy(self):
        today = date.today().isoformat()
        initial_data = {
            "seen_ids": ["95104887", "blognone_slug", "๑๒๓"],
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        sm = StateManager(state_file=str(self.state_file))
        seen = sm._seen

        self.assertIn("jobsdb_95104887", seen)
        self.assertNotIn("95104887", seen)
        self.assertEqual(seen["jobsdb_95104887"], today)
        self.assertEqual(seen["blognone_slug"], today)
        self.assertIn("๑๒๓", seen)
        self.assertNotIn("jobsdb_๑๒๓", seen)

    def test_load_collision_keeps_newer_date(self):
        # Case 1: Prefixed entry has newer date
        case1_file = Path(self.temp_dir.name) / "case1.json"
        with open(case1_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": 2,
                    "seen": {
                        "95104887": "2026-10-08",
                        "jobsdb_95104887": "2026-10-11",
                    },
                },
                f,
            )
        sm1 = StateManager(state_file=str(case1_file))
        self.assertEqual(sm1._seen["jobsdb_95104887"], "2026-10-11")

        # Case 2: Bare numeric entry has newer date
        case2_file = Path(self.temp_dir.name) / "case2.json"
        with open(case2_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": 2,
                    "seen": {
                        "95104887": "2026-10-12",
                        "jobsdb_95104887": "2026-10-09",
                    },
                },
                f,
            )
        sm2 = StateManager(state_file=str(case2_file))
        self.assertEqual(sm2._seen["jobsdb_95104887"], "2026-10-12")

        # Case 3: One date is None
        case3_file = Path(self.temp_dir.name) / "case3.json"
        with open(case3_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": 2,
                    "seen": {
                        "95104887": None,
                        "jobsdb_95104887": "2026-10-10",
                    },
                },
                f,
            )
        sm3 = StateManager(state_file=str(case3_file))
        self.assertEqual(sm3._seen["jobsdb_95104887"], "2026-10-10")

    def test_save_persists_migrated_ids(self):
        initial_data = {
            "version": 2,
            "seen": {
                "95104887": "2026-10-10",
            },
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        sm = StateManager(state_file=str(self.state_file))
        sm.save()

        with open(self.state_file, "r", encoding="utf-8") as f:
            persisted = json.load(f)

        self.assertIn("jobsdb_95104887", persisted["seen"])
        self.assertNotIn("95104887", persisted["seen"])
        self.assertEqual(persisted["seen"]["jobsdb_95104887"], "2026-10-10")

    def test_filter_new_jobs_recognizes_migrated_id_as_seen(self):
        initial_data = {
            "version": 2,
            "seen": {
                "95104887": "2026-10-10",
            },
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        sm = StateManager(state_file=str(self.state_file))
        incoming_job = {
            "id": "jobsdb_95104887",
            "title": "Backend Developer",
            "company": "Tech Corp",
            "url": "https://th.jobsdb.com/job/95104887",
        }

        new_jobs = sm.filter_new_jobs([incoming_job])
        self.assertEqual(new_jobs, [])
        self.assertFalse(sm.is_new("jobsdb_95104887"))


if __name__ == "__main__":
    unittest.main()
