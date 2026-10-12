# src/scrapers/base.py
"""
Base Scraper Interface for JHunt.
Implements the Adapter Pattern for heterogeneous job boards (JobsDB, Blognone, JobThai).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.models import RawJob

logger = logging.getLogger("JHunt.Scraper")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 15


class BaseScraper(ABC):
    """
    Abstract base class defining the uniform contract for all job portal scrapers.
    Concrete scrapers adapt external platform responses (REST APIs, GraphQL, SSR HTML)
    into normalized RawJob instances.
    """

    USER_AGENT: str = DEFAULT_USER_AGENT
    TIMEOUT: int = DEFAULT_TIMEOUT

    def _build_session(self, retries: int = 3, backoff_factor: float = 1.0) -> requests.Session:
        """Constructs an instrumented requests Session with transport-level retries."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/html, */*",
        })
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @abstractmethod
    def scrape(
        self,
        keywords: Optional[List[str]] = None,
        limit: int = 50,
        known_ids: Optional[set[str]] = None,
    ) -> List[RawJob]:
        """
        Scrapes and returns normalized RawJob instances matching the requested keywords.
        
        Args:
            keywords: List of target search queries (e.g. ['python developer', 'data engineer']).
            limit: Maximum number of jobs to retrieve per keyword.
            known_ids: Optional set of already-known job IDs to optimize or skip detail fetches.

        Returns:
            List of normalized RawJob instances.
        """
        pass
