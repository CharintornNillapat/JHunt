# main.py
import os
from dotenv import load_dotenv

from scrapers.jobsdb_scraper import JobsDBScraper
from notifier import TelegramNotifier
from state_manager import StateManager

load_dotenv()


def get_config() -> dict:
    return {
        "keywords": [
            kw.strip()
            for kw in os.getenv("SEARCH_KEYWORDS", "python developer,data engineer").split(",")
        ],
        "title_filter": [
            kw.strip()
            for kw in os.getenv(
                "TITLE_FILTER",
                "python,django,fastapi,data,software,backend,programmer,developer,"
                "engineer,analyst,devops,cloud,fullstack,full stack,นักพัฒนา,"
                "โปรแกรมเมอร์,วิศวกร,นักวิเคราะห์"
            ).split(",")
        ],
        "headless": os.getenv("HEADLESS", "true").lower() == "true",
    }


def run_scrapers(config: dict) -> list[dict]:
    """
    Instantiates and runs all active scrapers.
    To add a new site later: import it, instantiate it here, extend all_jobs.
    """
    all_jobs = []

    print("[Main] Running JobsDB scraper...")
    jobsdb = JobsDBScraper(
        keywords=config["keywords"],
        headless=config["headless"]
    )
    all_jobs.extend(jobsdb.scrape())

    # Future scrapers slot in cleanly here:
    # print("[Main] Running Indeed scraper...")
    # indeed = IndeedScraper(keywords=config["keywords"], headless=config["headless"])
    # all_jobs.extend(indeed.scrape())

    return all_jobs


def notify_jobs(jobs: list[dict], notifier: TelegramNotifier) -> int:
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
            print(f"[Main] Failed to send alert for job ID: {job['id']}")
    return sent


def main():
    config = get_config()
    notifier = TelegramNotifier()
    state = StateManager()

    # --- Step 1: Scrape ---
    raw_jobs = run_scrapers(config)
    print(f"[Main] Total raw jobs scraped: {len(raw_jobs)}")

    # --- Step 2: Deduplicate ---
    new_jobs = state.filter_new_jobs(raw_jobs)
    print(f"[Main] New jobs (unseen): {len(new_jobs)}")

    # --- Step 3: Relevance filter (title keywords) ---
    relevant_jobs = state.filter_relevant_jobs(new_jobs, config["title_filter"])
    print(f"[Main] After relevance filter: {len(relevant_jobs)}")

    # --- Step 4: Seniority filter ---
    junior_jobs = state.filter_by_seniority(relevant_jobs)
    print(f"[Main] After seniority filter: {len(junior_jobs)}")

    # --- Step 5: Location filter ---
    local_jobs = state.filter_by_location(junior_jobs)
    print(f"[Main] After location filter: {len(local_jobs)}")

    if not local_jobs:
        print("[Main] No matching jobs found. Exiting.")
        return

    # --- Step 6: Notify ---
    sent_count = notify_jobs(local_jobs, notifier)

    # --- Step 7: Persist ---
    state.save()

    print(f"[Main] Run complete. Sent {sent_count}/{len(local_jobs)} alerts.")


if __name__ == "__main__":
    main()