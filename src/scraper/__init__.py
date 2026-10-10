# src/scraper/__init__.py
from scrapers.base_scraper import BaseScraper
from scrapers.jobsdb_api import JobsDBAPIScraper

__all__ = ["BaseScraper", "JobsDBAPIScraper"]
