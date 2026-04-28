# scrapers/base_scraper.py
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.
    Every scraper must implement the `scrape()` method
    and return a list of job dicts in a consistent schema.
    """

    JOB_SCHEMA = {"id", "title", "company", "url"}  # Enforced contract

    def __init__(self, headless: bool = True):
        self.driver = self._init_driver(headless)

    def _init_driver(self, headless: bool) -> webdriver.Chrome:
        """
        Initializes a Chrome WebDriver with sane defaults.
        Headless=True is required for GitHub Actions (no display).
        """
        options = Options()

        if headless:
            options.add_argument("--headless=new")  # 'new' headless is more stable than legacy

        # These flags are essential for running inside Docker/CI containers
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Mimic a real browser to reduce bot detection
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

        # Let Selenium 4 manage ChromeDriver automatically
        service = Service()
        return webdriver.Chrome(service=service, options=options)

    def _validate_job(self, job: dict) -> bool:
        """Ensures every scraped job has the required fields."""
        return self.JOB_SCHEMA.issubset(job.keys()) and all(job.values())

    @abstractmethod
    def scrape(self) -> list[dict]:
        """
        Must be implemented by every subclass.
        Must return a list of dicts matching JOB_SCHEMA.
        """
        pass

    def close(self):
        """Always call this after scraping to release the WebDriver."""
        if self.driver:
            self.driver.quit()