# scrapers/jobsdb_api.py
"""
JobsDB Thailand scraper backed by SEEK's public JSON search API.
Maintained as an adapter / alias to src.scrapers.jobsdb.JobsDBScraper.
"""
from typing import List, Optional
from src.scrapers.jobsdb import JobsDBScraper
from src.models import RawJob


class JobsDBAPIScraper(JobsDBScraper):
    """
    Backwards-compatible wrapper around JobsDBScraper for legacy pipelines.
    """
    def __init__(self, keywords: Optional[List[str]] = None):
        super().__init__(keywords=keywords)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    keywords = [
        kw.strip()
        for kw in os.getenv("SEARCH_KEYWORDS", "python developer,data engineer").split(",")
    ]

    scraper = JobsDBAPIScraper(keywords=keywords)
    results = scraper.scrape(limit=10)

    print(f"\n--- {len(results)} job(s) ---")
    for job in results[:10]:
        print(f"\n[{job.id}] {job.title}")
        print(f"  company   : {job.company}")
        print(f"  location  : {job.location}")
        print(f"  salary    : {job.salary or '(not advertised)'}")
        print(f"  work_type : {job.work_type or '(unspecified)'}")
        print(f"  url       : {job.url}")
