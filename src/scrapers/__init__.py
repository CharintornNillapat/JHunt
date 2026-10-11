# src/scrapers/__init__.py
"""
Scraper adapters package for JHunt.
Exposes uniform BaseScraper interface and factory function for active scrapers.
"""
from typing import List

from src.scrapers.base import BaseScraper
from src.scrapers.blognone import BlognoneScraper
from src.scrapers.jobsdb import JobsDBScraper
from src.scrapers.jobthai import JobThaiScraper


def get_active_scrapers() -> List[BaseScraper]:
    """
    Factory function returning instances of all active scraper adapters.
    Currently includes JobsDB, Blognone, and JobThai.
    """
    return [
        JobsDBScraper(),
        BlognoneScraper(),
        JobThaiScraper(),
    ]


__all__ = [
    "BaseScraper",
    "JobsDBScraper",
    "BlognoneScraper",
    "JobThaiScraper",
    "get_active_scrapers",
]
