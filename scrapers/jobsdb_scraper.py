# scrapers/jobsdb_scraper.py
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base_scraper import BaseScraper


class JobsDBScraper(BaseScraper):

    BASE_URL = "https://th.jobsdb.com/jobs/{keyword}"

    # --- Selectors: Update these after your DevTools inspection ---
    SELECTORS = {
        "job_cards": "[data-testid='job-card']",
        "title":     "[data-testid='job-card-title']",
        "company":   "[data-automation='jobCompany']",
        "link":      "[data-testid='job-card-title']",  # same element, it's an <a> tag
    }

    def __init__(self, keywords: list[str], headless: bool = True):
        super().__init__(headless)
        self.keywords = keywords

    def _build_url(self, keyword: str) -> str:
        return self.BASE_URL.format(keyword=keyword.replace(" ", "-").lower())

    def _wait_for_cards(self) -> bool:
        """
        Uses WebDriverWait instead of time.sleep().
        Waits up to 15s for job cards to appear in the DOM.
        Returns False if page times out (e.g., no results).
        """
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, self.SELECTORS["job_cards"])
                )
            )
            return True
        except TimeoutException:
            print("[JobsDB] Timed out waiting for job cards.")
            return False

    def _parse_cards(self) -> list[dict]:
        jobs = []
        cards = self.driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["job_cards"])

        for card in cards:
            try:
                title_el = card.find_element(By.CSS_SELECTOR, self.SELECTORS["title"])
                company_el = card.find_element(By.CSS_SELECTOR, self.SELECTORS["company"])

                job = {
                    "id":      card.get_attribute("data-job-id"),   # ← clean, stable ID
                    "title":   title_el.text.strip(),
                    "company": company_el.text.strip(),
                    "url":     title_el.get_attribute("href"),       # ← title <a> carries the href
                }

                if self._validate_job(job):
                    jobs.append(job)

            except NoSuchElementException:
                continue

        return jobs

    def scrape(self) -> list[dict]:
        """
        Entry point. Iterates over all keywords and returns
        a deduplicated list of jobs.
        """
        all_jobs = []
        seen_ids = set()

        for keyword in self.keywords:
            url = self._build_url(keyword)
            print(f"[JobsDB] Scraping: {url}")

            self.driver.get(url)

            if not self._wait_for_cards():
                continue  # Skip this keyword if page didn't load

            jobs = self._parse_cards()
            print(f"[JobsDB] Found {len(jobs)} jobs for '{keyword}'")

            for job in jobs:
                if job["id"] not in seen_ids:
                    seen_ids.add(job["id"])
                    all_jobs.append(job)

        self.close()
        return all_jobs


if __name__ == "__main__":
    scraper = JobsDBScraper(keywords=["python developer", "data engineer"], headless=False)
    results = scraper.scrape()
    for job in results:
        print(job)