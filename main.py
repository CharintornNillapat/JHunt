# main.py
"""
JHunt: Job Market Intelligence & Portfolio Ideation Platform (Thailand Tech Market).
Unified pipeline runner supporting CLI subcommands:
  - python main.py run --all (Full pipeline: Scrape -> Filter -> Store -> Extract -> Alert -> Analyze -> Export)
  - python main.py alert     (Fast path: Legacy scraping and Telegram alert dispatching only)
  - python main.py analyze   (Offline path: Clustering & project spec generation from existing DB)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Safe UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from gemini_filter import filter_semantically
from scrapers.jobsdb_api import JobsDBAPIScraper
from src.analyzer.cluster_analyzer import ClusterAnalyzer
from src.analyzer.role_classifier import StandardRole
from src.extractor.llm_extractor import GeminiExtractor, process_unprocessed_jobs
from src.generator.ideation_engine import IdeationEngine
from src.generator.markdown_exporter import MarkdownExporter
from src.notifier.telegram_notifier import TelegramNotifier
from src.storage.db import DatabaseManager
from src.storage.turso_client import TursoClient
from state_manager import StateManager

logger = logging.getLogger("JHunt")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")

DEFAULT_KEYWORDS = "python developer,data engineer"
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
DEFAULT_EXTRACTION_LIMIT = 10
DEFAULT_TITLE_FILTER = (
    "python,django,fastapi,data,software,backend,programmer,developer,"
    "engineer,analyst,devops,cloud,fullstack,full stack,นักพัฒนา,"
    "โปรแกรมเมอร์,วิศวกร,นักวิเคราะห์"
)


def _csv_env(name: str, default: str) -> list[str]:
    """Reads a comma-separated env var into a list of non-empty terms."""
    raw = os.getenv(name) or default
    terms = [term.strip() for term in raw.split(",")]
    return [term for term in terms if term] or [t.strip() for t in default.split(",")]


def _bool_env(name: str, default: bool = False) -> bool:
    """Reads a boolean env var. Unset or empty falls back to default."""
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def get_config() -> dict:
    gemini_model = (os.getenv("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL

    return {
        "keywords": _csv_env("SEARCH_KEYWORDS", DEFAULT_KEYWORDS),
        "title_filter": _csv_env("TITLE_FILTER", DEFAULT_TITLE_FILTER),
        "gemini_enabled": _bool_env("GEMINI_ENABLED", False),
        "gemini_api_key": (os.getenv("GEMINI_API_KEY") or "").strip(),
        "gemini_model": gemini_model,
        "export_dir": os.getenv("EXPORT_DIR"),
    }


def run_scrapers(config: dict) -> list[dict]:
    """Instantiates and executes active scrapers."""
    all_jobs = []
    print("[Main] Running JobsDB scraper...")
    jobsdb = JobsDBAPIScraper(keywords=config["keywords"])
    all_jobs.extend(jobsdb.scrape())
    return all_jobs


def notify_jobs(jobs: list[dict], notifier: TelegramNotifier, state: StateManager) -> int:
    """
    Sends Telegram alerts for each job.
    Returns count of successfully sent alerts.
    """
    sent = 0
    for job in jobs:
        success = notifier.send_job_alert(
            title=job["title"],
            company=job["company"],
            url=job["url"],
            location=job.get("location", ""),
            salary=job.get("salary", ""),
            work_type=job.get("work_type", ""),
        )
        if success:
            sent += 1
        else:
            print(f"[Main] Failed to send alert for job ID: {job['id']} — will retry next run")
            state.unmark(job["id"])
    return sent


# ── Subcommand Implementations ────────────────────────────────────────────────


def run_alert_pipeline(
    config: dict,
    state: Optional[StateManager] = None,
    notifier: Optional[TelegramNotifier] = None,
) -> int:
    """
    Fast path: Scrapes jobs, filters them, and sends Telegram alerts.
    Does not run LLM extraction or blueprint generation.
    """
    if state is None:
        state = StateManager()

    if notifier is None:
        try:
            notifier = TelegramNotifier()
        except ValueError as e:
            print(f"[Main] Telegram alert skipped: {e}")
            notifier = None

    try:
        raw_jobs = run_scrapers(config)
        print(f"[Main] Total raw jobs scraped: {len(raw_jobs)}")

        new_jobs = state.filter_new_jobs(raw_jobs)
        print(f"[Main] New jobs (unseen): {len(new_jobs)}")

        relevant_jobs = state.filter_relevant_jobs(new_jobs, config["title_filter"])
        junior_jobs = state.filter_by_seniority(relevant_jobs)
        local_jobs = state.filter_by_location(junior_jobs)

        if not local_jobs:
            print("[Main] No matching jobs found after keyword filters.")
            return 0

        final_jobs = filter_semantically(local_jobs, config)
        print(f"[Main] After semantic filter: {len(final_jobs)}")

        if not final_jobs:
            print("[Main] No matching jobs after semantic filter.")
            return 0

        if notifier is not None:
            sent = notify_jobs(final_jobs, notifier, state)
            print(f"[Main] Run complete. Sent {sent}/{len(final_jobs)} alerts.")
            return sent
        else:
            print(f"[Main] Dry-run: {len(final_jobs)} jobs matched filters (no notifier configured).")
            return len(final_jobs)
    finally:
        state.save()


def run_analyze_pipeline(
    config: dict,
    db: Optional[DatabaseManager] = None,
    target_role: Optional[str] = None,
    limit: Optional[int] = None,
    turso: Optional[TursoClient] = None,
) -> Optional[Path]:
    """
    Offline path: Analyzes stored market data in SQLite and exports
    a portfolio blueprint for the specified or dominant role.
    """
    if db is None:
        db = DatabaseManager()
    if turso is None:
        turso = TursoClient()

    analyzer = ClusterAnalyzer(db=db)
    report = analyzer.generate_market_report()

    print(f"\n================ MARKET INTELLIGENCE REPORT ================")
    print(f"Total Postings Analyzed: {report.total_jobs_analyzed}")
    if report.top_must_have_skills:
        print("\nTop Must-Have Skills:")
        for s in report.top_must_have_skills[:8]:
            print(f"  • {s.name:<18} : {s.count:>3} jobs ({s.percentage}%)")

    if report.top_databases:
        print("\nTop Databases:")
        for d in report.top_databases[:5]:
            print(f"  • {d.name:<18} : {d.count:>3} jobs ({d.percentage}%)")

    if report.top_cooccurrences:
        print("\nTop Tech Co-occurrences:")
        for c in report.top_cooccurrences[:5]:
            print(f"  • {c.tech_a} + {c.tech_b:<15} ({c.count} pairs)")

    # Select role for portfolio ideation
    role = target_role or StandardRole.BACKEND.value
    dominant_stack = analyzer.get_dominant_stack_for_role(role)
    print(f"\nGenerating Blueprint for Role: '{role}'")
    print(f"Dominant Stack: {', '.join(dominant_stack)}")

    engine = IdeationEngine(
        api_key=config.get("gemini_api_key"),
        model=config.get("gemini_model"),
    )
    exporter = MarkdownExporter(export_dir=config.get("export_dir"), db=db, turso=turso)

    spec = engine.generate_project_spec(target_role=role, tech_stack=dominant_stack)
    if not spec:
        print("[Main] Failed to generate project blueprint.")
        return None

    exported_path = exporter.export(spec=spec, target_role=role)
    print(f"\n[Main] Successfully exported portfolio blueprint:\n-> {exported_path}")
    return exported_path


def run_full_pipeline(
    config: dict,
    db: Optional[DatabaseManager] = None,
    state: Optional[StateManager] = None,
    notifier: Optional[TelegramNotifier] = None,
    limit: Optional[int] = DEFAULT_EXTRACTION_LIMIT,
    target_role: Optional[str] = None,
    turso: Optional[TursoClient] = None,
) -> Dict[str, Any]:
    """
    Full end-to-end pipeline:
    1. Scrape jobs.
    2. Store all scraped jobs into SQLite `jobs` table (idempotent) and sync to Turso cloud.
    3. Filter and alert via Telegram.
    4. Extract structured skills via Gemini and sync to Turso cloud.
    5. Aggregate tech clusters.
    6. Generate and export portfolio project blueprints and sync to Turso cloud.
    7. Send Market Intelligence Brief via Telegram.
    """
    if db is None:
        db = DatabaseManager()
    if state is None:
        state = StateManager()
    if turso is None:
        turso = TursoClient()

    if notifier is None:
        try:
            notifier = TelegramNotifier()
        except ValueError as e:
            print(f"[Main] Telegram notifier inactive: {e}")
            notifier = None

    results: Dict[str, Any] = {
        "scraped": 0,
        "new_stored": 0,
        "alerted": 0,
        "extracted": 0,
        "exported_spec": None,
    }

    try:
        # Step 1: Scrape
        raw_jobs = run_scrapers(config)
        results["scraped"] = len(raw_jobs)
        print(f"[Main] Total raw jobs scraped: {len(raw_jobs)}")

        # Step 2: Store in SQLite (All jobs for market intelligence) and Turso cloud
        stored_count = sum(1 for j in raw_jobs if db.save_job(j))
        results["new_stored"] = stored_count
        print(f"[Main] Newly stored in database: {stored_count} jobs.")

        if turso.is_available:
            turso_synced = turso.sync_jobs(raw_jobs)
            print(f"[Main] Synchronized to Turso cloud: {turso_synced} jobs.")

        # Step 3: Filter for immediate alert
        new_jobs = state.filter_new_jobs(raw_jobs)
        relevant_jobs = state.filter_relevant_jobs(new_jobs, config["title_filter"])
        junior_jobs = state.filter_by_seniority(relevant_jobs)
        local_jobs = state.filter_by_location(junior_jobs)
        final_jobs = filter_semantically(local_jobs, config)

        if final_jobs and notifier:
            results["alerted"] = notify_jobs(final_jobs, notifier, state)

        # Step 4: Structured LLM Extraction on unprocessed jobs (enforce default cap)
        extraction_limit = limit if limit is not None else DEFAULT_EXTRACTION_LIMIT
        extractor = GeminiExtractor(
            api_key=config.get("gemini_api_key"),
            model=config.get("gemini_model"),
        )
        extracted_count = process_unprocessed_jobs(
            db=db,
            extractor=extractor,
            limit=extraction_limit,
            turso=turso,
        )
        results["extracted"] = extracted_count

        # Step 5: Market Intelligence & Ideation
        analyzer = ClusterAnalyzer(db=db)
        report = analyzer.generate_market_report()

        role = target_role or StandardRole.BACKEND.value
        dominant_stack = analyzer.get_dominant_stack_for_role(role)

        engine = IdeationEngine(
            api_key=config.get("gemini_api_key"),
            model=config.get("gemini_model"),
        )
        exporter = MarkdownExporter(export_dir=config.get("export_dir"), db=db, turso=turso)

        spec = engine.generate_project_spec(target_role=role, tech_stack=dominant_stack)
        if spec:
            exported_path = exporter.export(spec=spec, target_role=role)
            results["exported_spec"] = str(exported_path)
            print(f"[Main] Portfolio Blueprint exported: {exported_path}")

            # Step 6: Dispatch Market Intelligence Brief via Telegram
            if notifier is not None:
                top_pairs = [(c.tech_a, c.tech_b) for c in report.top_cooccurrences[:4]]
                notifier.send_market_brief(
                    top_pairs=top_pairs,
                    generated_title=spec.title,
                    role=role,
                    total_analyzed=report.total_jobs_analyzed,
                )

    finally:
        state.save()

    return results


# ── CLI Interface ─────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jhunt",
        description="JHunt: Thailand Job Market Intelligence & Portfolio Ideation Platform",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # run subcommand (default)
    run_parser = subparsers.add_parser("run", help="Execute complete intelligence pipeline")
    run_parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="Run all pipeline stages: scrape -> store -> extract -> alert -> analyze -> export",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_EXTRACTION_LIMIT,
        help=f"Limit number of jobs for LLM extraction (default: {DEFAULT_EXTRACTION_LIMIT})",
    )
    run_parser.add_argument("--role", type=str, default=None, help="Target role for portfolio spec")

    # alert subcommand
    alert_parser = subparsers.add_parser("alert", help="Run fast scraper and Telegram alerts only")
    alert_parser.add_argument("--limit", type=int, default=None, help="Limit scraped jobs")

    # analyze subcommand
    analyze_parser = subparsers.add_parser("analyze", help="Analyze market database and generate portfolio blueprint")
    analyze_parser.add_argument("--role", type=str, default="Backend Engineer", help="Role for project blueprint")
    analyze_parser.add_argument("--limit", type=int, default=None, help="Limit jobs for extraction queue")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = get_config()

    try:
        # Default with no arguments is "run --all" for backwards compatibility
        if args.command is None or args.command == "run":
            limit = getattr(args, "limit", DEFAULT_EXTRACTION_LIMIT)
            if limit is None:
                limit = DEFAULT_EXTRACTION_LIMIT
            role = getattr(args, "role", None)
            run_full_pipeline(config=config, limit=limit, target_role=role)
            return 0

        elif args.command == "alert":
            run_alert_pipeline(config=config)
            return 0

        elif args.command == "analyze":
            role = getattr(args, "role", "Backend Engineer")
            limit = getattr(args, "limit", None)
            run_analyze_pipeline(config=config, target_role=role, limit=limit)
            return 0

        else:
            parser.print_help()
            return 1

    except Exception as e:
        logger.error(f"[Main] Fatal pipeline execution error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())