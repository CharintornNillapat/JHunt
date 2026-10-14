# scripts/migrate_jobsdb_ids.py
"""
Standalone one-time migration script for Task 0.1:
Prefixes legacy bare numeric JobsDB IDs with 'jobsdb_' in Turso database.
Uses an atomic batch with deferred foreign key constraints.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path if run as script
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
import libsql_client

load_dotenv()
logger = logging.getLogger("migrate_jobsdb_ids")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="One-time atomic migration to prefix numeric JobsDB IDs with jobsdb_ in Turso"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        default=True,
        help="Preview changes without modifying storage (default)",
    )
    group.add_argument(
        "--apply",
        action="store_false",
        dest="dry_run",
        help="Apply updates to database",
    )

    args = parser.parse_args(argv)

    raw_url = os.getenv("TURSO_DATABASE_URL")
    auth_token = os.getenv("TURSO_AUTH_TOKEN")

    if not raw_url:
        print("ERROR: TURSO_DATABASE_URL is not set in environment or .env")
        return 1

    url = raw_url.replace("libsql://", "https://")
    client = libsql_client.create_client_sync(url=url, auth_token=auth_token or None)

    try:
        jobs_num = client.execute("SELECT count(1) FROM jobs WHERE id GLOB '[0-9]*'").rows[0][0]
        skills_num = client.execute("SELECT count(1) FROM skills_extracted WHERE job_id GLOB '[0-9]*'").rows[0][0]

        print("=" * 60)
        print("TURSO ID CONTINUITY MIGRATION REPORT")
        print("=" * 60)
        print(f"Mode:                                 {'DRY RUN (preview only)' if args.dry_run else 'APPLY'}")
        print(f"Candidate jobs with numeric IDs:      {jobs_num}")
        print(f"Candidate skills with numeric job_id: {skills_num}")
        print("=" * 60)

        if args.dry_run:
            print("\nPreview complete. No changes were made.")
            print("To apply changes to Turso, run with: --apply")
            return 0

        print("\nExecuting atomic batch migration with deferred foreign keys...")
        client.batch([
            "PRAGMA defer_foreign_keys = ON;",
            "UPDATE jobs SET id = 'jobsdb_' || id, source = 'jobsdb' WHERE id GLOB '[0-9]*';",
            "UPDATE skills_extracted SET job_id = 'jobsdb_' || job_id WHERE job_id GLOB '[0-9]*';",
        ])
        print("Batch migration executed successfully!")

        # Post-checks
        remaining_jobs = client.execute("SELECT count(1) FROM jobs WHERE id GLOB '[0-9]*'").rows[0][0]
        remaining_skills = client.execute("SELECT count(1) FROM skills_extracted WHERE job_id GLOB '[0-9]*'").rows[0][0]
        fk_check = client.execute("PRAGMA foreign_key_check").rows

        print("\n" + "=" * 60)
        print("POST-MIGRATION VERIFICATION")
        print("=" * 60)
        print(f"Remaining numeric jobs:             {remaining_jobs} (expected: 0)")
        print(f"Remaining numeric skills_extracted: {remaining_skills} (expected: 0)")
        print(f"Foreign key violations:             {len(fk_check)} (expected: 0)")
        print("=" * 60)

        if remaining_jobs == 0 and remaining_skills == 0 and len(fk_check) == 0:
            print("\nSUCCESS: All IDs migrated cleanly with 0 foreign key violations.")
            return 0
        else:
            print("\nWARNING: Unexpected post-migration counts detected.")
            return 1

    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
