# src/models/job.py
"""
Normalized data model for job listings scraped across all supported portals
(JobsDB, Blognone, JobThai).
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class RawJob(BaseModel):
    """
    Standardized job model adhering to the scraper contract.
    Guarantees consistent schema fields across disparate job boards while
    providing backward-compatible dict-like access for downstream pipeline stages.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(description="Deterministic string with source prefix (e.g. jobsdb_{id}, blognone_{id}, jobthai_{id})")
    title: str = Field(description="Job posting position title")
    company: str = Field(description="Hiring company or organization name")
    location: Optional[str] = Field(default=None, description="Job location / province / district")
    description: Optional[str] = Field(default=None, description="Detailed job description and responsibilities")
    url: Optional[str] = Field(default=None, description="Original canonical job URL")
    source: Literal["jobsdb", "blognone", "jobthai"] = Field(description="Origin job portal platform")
    posted_at: Optional[str] = Field(default=None, description="Timestamp or date string of job listing")
    salary: Optional[str] = Field(default=None, description="Advertised salary or compensation range")
    work_type: Optional[str] = Field(default=None, description="Employment contract or work arrangement")
    raw_content: Optional[str] = Field(default=None, description="Raw serialized payload for historical audit")
    teaser: Optional[str] = Field(default=None, description="Short summary snippet")
    bullet_points: Optional[List[str]] = Field(default=None, description="Bullet points or key highlights")
    tags: Optional[List[str]] = Field(default=None, description="Category or skill tags")
    listing_date: Optional[str] = Field(default=None, description="Listing date representation")

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if self.__pydantic_extra__ and key in self.__pydantic_extra__:
            return self.__pydantic_extra__[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            if self.__pydantic_extra__ is None:
                self.__pydantic_extra__ = {}
            self.__pydantic_extra__[key] = value

    def __contains__(self, key: str) -> bool:
        if hasattr(self, key) and getattr(self, key) is not None:
            return True
        if self.__pydantic_extra__ and key in self.__pydantic_extra__:
            return True
        return False

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            return val if val is not None else default
        if self.__pydantic_extra__ and key in self.__pydantic_extra__:
            val = self.__pydantic_extra__[key]
            return val if val is not None else default
        return default

    def to_dict(self) -> Dict[str, Any]:
        """Returns standard dictionary serialization."""
        return self.model_dump()
