# scrapers/jobsdb_scraper.py
import time
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base_scraper import BaseScraper


class JobsDBScraper(BaseScraper):

    BASE_URL = "https://th.jobsdb.com/th/{keyword}-jobs"

    # --- Selectors: Update these after your DevTools inspection ---
    SELECTORS = {
        "job_cards":          "[data-testid='job-card']",
        "title":              "[data-testid='job-card-title']",
        "company":            "[data-automation='jobCompany']",
        "link":               "[data-testid='job-card-title']",  # same element, it's an <a> tag
        # Detail page selectors
        "detail_location":    "[data-automation='job-detail-location']",
        "detail_salary":         "[data-automation='job-detail-salary']",        # when shown
        "detail_salary_hidden":  "[data-automation='job-detail-add-expected-salary']",  # placeholder
        "detail_work_type":   "[data-automation='job-detail-work-type']",
    }

    def __init__(self, keywords: list[str], headless: bool = True):
        super().__init__(headless)
        self.keywords = keywords

    def _build_url(self, keyword: str) -> str:
        """
        Encodes the keyword and targets Thailand specifically via query params.
        """
        slug = keyword.strip().lower().replace(" ", "-")
        return self.BASE_URL.format(keyword=slug)

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

    def _get_job_details(self, url: str) -> dict:
        """
        Opens a job detail page and extracts location, salary, and work type.
        Returns empty strings for fields that aren't found — never crashes.
        """
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.SELECTORS["detail_location"])
                )
            )
        except TimeoutException:
            print(f"[JobsDB] Detail page timed out: {url}")
            return {"location": "", "salary": "", "work_type": ""}

        def safe_get(selector: str) -> str:
            try:
                return self.driver.find_element(
                    By.CSS_SELECTOR, selector
                ).text.strip()
            except NoSuchElementException:
                return ""

        # Get salary — return empty if it's just the placeholder text
        raw_salary = safe_get(self.SELECTORS["detail_salary"])
        salary = raw_salary if raw_salary and "Add expected salary" not in raw_salary else ""

        return {
            "location":  safe_get(self.SELECTORS["detail_location"]),
            "salary":    salary,
            "work_type": safe_get(self.SELECTORS["detail_work_type"]),
        }

    def _parse_cards(self) -> list[dict]:
        jobs = []
        cards = self.driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["job_cards"])

        # Collect basic info first from all cards on this page
        basic_jobs = []
        for card in cards:
            try:
                title_el  = card.find_element(By.CSS_SELECTOR, self.SELECTORS["title"])
                company_el = card.find_element(By.CSS_SELECTOR, self.SELECTORS["company"])
                job = {
                    "id":      card.get_attribute("data-job-id"),
                    "title":   title_el.text.strip(),
                    "company": company_el.text.strip(),
                    "url":     title_el.get_attribute("href"),
                }
                
                # Assuming _validate_job is a method inherited from BaseScraper 
                # or you plan to add it. If not, you might need to remove this check.
                if self._validate_job(job):
                    basic_jobs.append(job)
            except NoSuchElementException:
                continue

        # Now click into each job for full details
        for i, job in enumerate(basic_jobs):
            print(f"[JobsDB] Fetching details {i+1}/{len(basic_jobs)}: {job['title']}")
            details = self._get_job_details(job["url"])
            job.update(details)
            jobs.append(job)

        return jobs

    def scrape(self) -> list[dict]:
        all_jobs = []
        seen_ids = set()
        for keyword in self.keywords:
            url = self._build_url(keyword)
            print(f"[JobsDB] Scraping: {url}")
            self.driver.get(url)

            if not self._wait_for_cards():
                continue

            # Collect basic info first without clicking
            cards = self.driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["job_cards"])
            new_cards_data = []

            for card in cards:
                try:
                    job_id = card.get_attribute("data-job-id")
                    if job_id and job_id not in seen_ids:
                        seen_ids.add(job_id)
                        title_el = card.find_element(By.CSS_SELECTOR, self.SELECTORS["title"])
                        company_el = card.find_element(By.CSS_SELECTOR, self.SELECTORS["company"])
                        new_cards_data.append({
                            "id":      job_id,
                            "title":   title_el.text.strip(),
                            "company": company_el.text.strip(),
                            "url":     title_el.get_attribute("href"),
                        })
                except NoSuchElementException:
                    continue

            print(f"[JobsDB] {len(new_cards_data)} new unique jobs for '{keyword}', fetching details...")

        # Now only click into jobs we haven't seen before
            for i, job in enumerate(new_cards_data):
                print(f"[JobsDB] Fetching details {i+1}/{len(new_cards_data)}: {job['title']}")
                details = self._get_job_details(job["url"])
                job.update(details)
                if self._validate_job(job):
                    all_jobs.append(job)

        self.close()
        return all_jobs


if __name__ == "__main__":
    scraper = JobsDBScraper(keywords=["python developer", "data engineer"], headless=False)
    results = scraper.scrape()
    for job in results:
        print(job)