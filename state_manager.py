# state_manager.py
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from urllib.parse import urlparse, urlunparse

STATE_FILE = "data/seen_jobs.json"
STATE_VERSION = 2

# Job ads are delisted long before this, so a pruned ID cannot resurface as a
# duplicate — this only stops the state file growing without bound.
STATE_TTL_DAYS = 90

EXCLUDE_SENIORITY = [
    "senior", "lead", "principal", "manager", "head of", "director"
]

INCLUDE_LOCATIONS = [
    "กรุงเทพ", "นนทบุรี", "ปทุมธานี", "อยุธยา", "remote", "work from home",
    "bangkok", "nonthaburi", "pathum thani", "ayutthaya"
]


class StateManager:
    """
    Tracks which job IDs have already been notified.

    State file (v2):
        {"version": 2, "seen": {"<job_id>": "YYYY-MM-DD", ...}}

    The date is when the ID was *first seen*, and drives TTL pruning — it is not
    the job's listing date.
    """

    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        self._seen: dict[str, str | None] = self._load()

    def _load(self) -> dict[str, str | None]:
        """
        Reads seen job IDs from disk. Returns an empty dict if the file is absent.
        Accepts both the v2 schema and the legacy v1 {"seen_ids": [...]} shape.
        """
        if not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # Corrupted file — start fresh rather than crashing
            print("[StateManager] Warning: state file corrupted, starting fresh.")
            return {}

        if not isinstance(data, dict):
            print("[StateManager] Warning: unexpected state shape, starting fresh.")
            return {}

        # v2
        if "seen" in data:
            seen = data.get("seen") or {}
            if isinstance(seen, dict):
                return {str(k): v for k, v in seen.items()}
            print("[StateManager] Warning: unexpected 'seen' shape, starting fresh.")
            return {}

        # v1 -> v2 migration. Stamp with today so these IDs get the full TTL from
        # the migration date rather than being pruned on the very next save.
        legacy_ids = data.get("seen_ids") or []
        if legacy_ids:
            today = date.today().isoformat()
            print(f"[StateManager] Migrating {len(legacy_ids)} ID(s) from v1 state schema.")
            return {str(job_id): today for job_id in legacy_ids}

        return {}

    def _prune(self) -> int:
        """Drops entries first seen more than STATE_TTL_DAYS ago. Returns count removed."""
        cutoff = date.today() - timedelta(days=STATE_TTL_DAYS)
        fresh: dict[str, str | None] = {}
        removed = 0

        for job_id, seen_on in self._seen.items():
            if not seen_on:
                # Unknown age — keep it. Never prune what we can't date.
                fresh[job_id] = seen_on
                continue
            try:
                seen_date = datetime.strptime(seen_on, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                fresh[job_id] = seen_on
                continue

            if seen_date < cutoff:
                removed += 1
            else:
                fresh[job_id] = seen_on

        self._seen = fresh
        return removed

    def save(self):
        """
        Prunes expired entries and persists state atomically.

        Writes to a temp file in the same directory, fsyncs it, then os.replace()s
        it over the target. A killed run can therefore never leave a truncated
        state file behind — which the CI cache would otherwise restore forever.
        """
        removed = self._prune()
        if removed:
            print(f"[StateManager] Pruned {removed} entry(ies) older than {STATE_TTL_DAYS} days.")

        target_dir = os.path.dirname(os.path.abspath(self.state_file))
        os.makedirs(target_dir, exist_ok=True)

        payload = {"version": STATE_VERSION, "seen": self._seen}

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target_dir,
                prefix=".seen_jobs.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp_path = tmp.name
                json.dump(payload, tmp, indent=2, sort_keys=True, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())

            os.replace(tmp_path, self.state_file)
            tmp_path = None
        finally:
            # Only reached if the write or the replace failed; leave no litter behind.
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        print(f"[StateManager] Saved {len(self._seen)} seen ID(s) to {self.state_file}")

    def is_new(self, job_id: str) -> bool:
        """Returns True if this job ID has never been seen before."""
        return job_id not in self._seen

    def mark_seen(self, job_id: str):
        """Adds a job ID to the seen set (in memory only — call save() to persist)."""
        self._seen[job_id] = date.today().isoformat()

    def unmark(self, job_id: str):
        """
        Removes a job ID from the seen set so it is reconsidered on the next run.

        Used when a job passed every filter but its notification failed to send —
        without this the alert would be marked seen and lost permanently.
        """
        self._seen.pop(job_id, None)

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

    def filter_by_seniority(self, jobs: list[dict], exclude: list[str] = EXCLUDE_SENIORITY) -> list[dict]:
        """
        Drops jobs whose titles contain seniority/experience keywords.
        """
        exclude_lower = [kw.lower() for kw in exclude]
        filtered = []

        for job in jobs:
            title_lower = job["title"].lower()
            excluded_by = next((kw for kw in exclude_lower if kw in title_lower), None)
            if excluded_by:
                print(f"[Filter] Excluded (seniority: '{excluded_by}'): {job['title']}")
            else:
                filtered.append(job)

        return filtered

    def filter_by_location(self, jobs: list[dict], include: list[str] = INCLUDE_LOCATIONS) -> list[dict]:
        """
        Keeps only jobs whose location matches the include list.
        Also keeps jobs with empty location (detail page may have failed).
        """
        include_lower = [loc.lower() for loc in include]
        filtered = []

        for job in jobs:
            location_lower = job.get("location", "").lower()

            # If location is empty, keep the job (benefit of the doubt)
            if not location_lower:
                filtered.append(job)
                continue

            if any(loc in location_lower for loc in include_lower):
                filtered.append(job)
            else:
                print(f"[Filter] Excluded (location: '{job['location']}'): {job['title']}")

        return filtered

    @staticmethod
    def _clean_url(url: str) -> str:
        """
        Strips tracking params and fragments from JobsDB URLs.
        'https://th.jobsdb.com/job/123?type=standard&ref=...#sol=abc'
        becomes 'https://th.jobsdb.com/job/123'
        """
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
