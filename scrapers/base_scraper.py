# scrapers/base_scraper.py
from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.
    Every scraper must implement the `scrape()` method
    and return a list of job dicts in a consistent schema.

    Scrapers are plain HTTP clients — constructing one must not open a browser
    or acquire any resource that needs explicit cleanup.
    """

    JOB_SCHEMA = {"id", "title", "company", "url"}  # Enforced contract

    # Sent on every outbound request; JobsDB serves an error page to obvious bots.
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def _validate_job(self, job: dict) -> bool:
        """
        Ensures every scraped job has the required fields, all non-empty.

        Only the JOB_SCHEMA keys are checked. Optional fields (salary, work_type,
        location, teaser...) are legitimately empty — most JobsDB ads do not
        advertise a salary — and must not disqualify a job.
        """
        return all(job.get(key) for key in self.JOB_SCHEMA)

    @abstractmethod
    def scrape(self) -> list[dict]:
        """
        Must be implemented by every subclass.
        Must return a list of dicts matching JOB_SCHEMA.
        """
        pass
