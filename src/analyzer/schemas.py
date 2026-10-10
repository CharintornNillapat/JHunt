# src/analyzer/schemas.py
"""
Pydantic schemas for market intelligence aggregation and tech stack clustering.
"""
from typing import Dict, List
from pydantic import BaseModel, Field, ConfigDict


class SkillFrequencyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(..., description="Canonical technology name")
    count: int = Field(..., description="Absolute occurrence count")
    percentage: float = Field(..., description="Percentage of analyzed jobs mentioning this skill")


class CooccurrenceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tech_a: str = Field(..., description="First technology in the pair")
    tech_b: str = Field(..., description="Second technology in the pair")
    count: int = Field(..., description="Number of job postings containing both technologies")


class RoleCluster(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str = Field(..., description="Standardized engineering role title")
    sample_size: int = Field(..., description="Number of job listings matching this role")
    top_skills: List[SkillFrequencyItem] = Field(default_factory=list, description="Top individual technologies for this role")
    dominant_stack: List[str] = Field(default_factory=list, description="Consensus 3-5 tech stack components for project blueprint synthesis")


class MarketReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_jobs_analyzed: int = Field(..., description="Total job postings analyzed")
    top_must_have_skills: List[SkillFrequencyItem] = Field(default_factory=list)
    top_nice_to_have_skills: List[SkillFrequencyItem] = Field(default_factory=list)
    top_frameworks: List[SkillFrequencyItem] = Field(default_factory=list)
    top_databases: List[SkillFrequencyItem] = Field(default_factory=list)
    top_cloud_infra: List[SkillFrequencyItem] = Field(default_factory=list)
    top_tools: List[SkillFrequencyItem] = Field(default_factory=list)
    top_cooccurrences: List[CooccurrenceItem] = Field(default_factory=list)
    role_clusters: Dict[str, RoleCluster] = Field(default_factory=dict)
    experience_distribution: Dict[str, int] = Field(default_factory=dict)
