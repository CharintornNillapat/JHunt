# scripts/backfill_salaries.py
"""
Standalone CLI tool for one-time historical salary backfill.
Parses unstructured salary data for historical listings and updates Turso / SQLite.
"""
from __future__ import annotations

import argparse
import logging
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

load_dotenv()

from src.extractor.salary_backfill import backfill_salaries
from src.storage import get_storage

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_salaries")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill historical job posting salaries using deterministic parser"
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
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of candidate jobs to process",
    )

    args = parser.parse_args(argv)

    storage = get_storage()
    try:
        storage_type = type(storage).__name__
        print(f"Connecting to storage: {storage_type}...")

        results = backfill_salaries(storage=storage, limit=args.limit, dry_run=args.dry_run)

        print("\n" + "=" * 50)
        print("SALARY BACKFILL REPORT")
        print("=" * 50)
        print(f"Mode:              {'DRY RUN (preview only)' if args.dry_run else 'APPLIED TO DATABASE'}")
        print(f"Storage Engine:    {storage_type}")
        print(f"Candidates Found:  {results['total_candidates']}")
        print(f"Newly Parsed:      {results['parsed_count']}")
        print(f"Rows Updated:      {results['applied_count']}")
        print(f"Currencies:        {results['currencies']}")
        print("=" * 50 + "\n")

        return 0
    finally:
        if hasattr(storage, "close"):
            storage.close()


if __name__ == "__main__":
    sys.exit(main())
