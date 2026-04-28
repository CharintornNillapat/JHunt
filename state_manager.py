# state_manager.py
import json
import os
from urllib.parse import urlparse, urlunparse

STATE_FILE = "data/seen_jobs.json"


class StateManager:
    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        self._seen: set[str] = self._load()

    def _load(self) -> set[str]:
        """Reads seen job IDs from disk. Returns empty set if file doesn't exist."""
        if not os.path.exists(self.state_file):
            return set()
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                return set(data.get("seen_ids", []))
        except (json.JSONDecodeError, KeyError):
            # Corrupted file — start fresh rather than crashing
            print("[StateManager] Warning: state file corrupted, starting fresh.")
            return set()

    def save(self):
        """Persists current seen IDs to disk."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump({"seen_ids": list(self._seen)}, f, indent=2)

    def is_new(self, job_id: str) -> bool:
        """Returns True if this job ID has never been seen before."""
        return job_id not in self._seen

    def mark_seen(self, job_id: str):
        """Adds a job ID to the seen set (in memory only — call save() to persist)."""
        self._seen.add(job_id)
    
    def filter_new_jobs(self, jobs: list[dict]) -> list[dict]:
        """
        Takes a raw job list, returns only unseen jobs.
        Also cleans URLs and marks new jobs as seen in memory.
        Does NOT save to disk — caller must call save() explicitly.
        """
        new_jobs = []
        for job in jobs:
            if self.is_new(job["id"]):
                job["url"] = self._clean_url(job["url"])
                self.mark_seen(job["id"])
                new_jobs.append(job)
        return new_jobs

    def filter_relevant_jobs(self, jobs: list[dict], keywords: list[str]) -> list[dict]:
        """
        Filters jobs whose titles don't contain any of the target keywords.
        Case-insensitive. Runs AFTER filter_new_jobs().
        """
        keywords_lower = [kw.lower() for kw in keywords]
        relevant = []

        for job in jobs:
            title_lower = job["title"].lower()
            if any(kw in title_lower for kw in keywords_lower):
                relevant.append(job)
            else:
                print(f"[Filter] Skipped irrelevant job: '{job['title']}'")

        return relevant
    
    @staticmethod
    def _clean_url(url: str) -> str:
        """
        Strips tracking params and fragments from JobsDB URLs.
        'https://th.jobsdb.com/job/123?type=standard&ref=...#sol=abc'
        becomes 'https://th.jobsdb.com/job/123'
        """
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))