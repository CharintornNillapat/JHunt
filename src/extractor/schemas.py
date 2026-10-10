# src/extractor/schemas.py
"""
Pydantic schemas for structured job market extraction and portfolio ideation.
Built with Pydantic v2 for strict type safety and Gemini structured output compliance.
"""
from typing import List
from pydantic import BaseModel, Field, ConfigDict


class ExtractedJob(BaseModel):
    """
    Normalized, structured data contract for parsed Job Descriptions (JDs).
    Extracted by LLM from raw job postings.
    """
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    job_title: str = Field(
        ...,
        description="Clean canonical job title (e.g. 'Backend Engineer', 'Data Engineer')",
    )
    company: str = Field(
        ...,
        description="Hiring company or organization name",
    )
    experience_level: str = Field(
        default="Unknown",
        description="Standardized experience tier: 'Entry', 'Junior', 'Mid', 'Senior', 'Lead', or 'Unknown'",
    )
    must_have_skills: List[str] = Field(
        default_factory=list,
        description="Mandatory programming languages, frameworks, or core technical proficiencies",
    )
    nice_to_have_skills: List[str] = Field(
        default_factory=list,
        description="Preferred, bonus, or secondary technical competencies",
    )
    frameworks: List[str] = Field(
        default_factory=list,
        description="Application libraries & frameworks (e.g. FastAPI, Django, React, Spring Boot, PyTorch)",
    )
    databases: List[str] = Field(
        default_factory=list,
        description="Databases, data warehouses, or storage engines (e.g. PostgreSQL, Redis, MongoDB, BigQuery)",
    )
    cloud_infra: List[str] = Field(
        default_factory=list,
        description="Cloud providers and DevOps/infrastructure tools (e.g. AWS, GCP, Azure, Docker, Kubernetes)",
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Developer utilities, CI/CD, message brokers, or pipelines (e.g. Git, Kafka, Airflow, Terraform)",
    )

    @property
    def all_tech_stack(self) -> List[str]:
        """Returns a deduplicated, case-normalized list of all recognized technologies."""
        combined = set()
        for group in (
            self.must_have_skills,
            self.nice_to_have_skills,
            self.frameworks,
            self.databases,
            self.cloud_infra,
            self.tools,
        ):
            for item in group:
                cleaned = item.strip()
                if cleaned:
                    combined.add(cleaned)
        return sorted(combined)


class ProjectIdeaSpec(BaseModel):
    """
    Architectural specification for an enterprise-grade portfolio project,
    synthesized from trending market skill clusters and real-world business domains.
    """
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(
        ...,
        description="Production-grade project title (e.g. 'Event-Driven Real-time Fraud Detection Engine')",
    )
    domain_industry: str = Field(
        ...,
        description="Target business domain in Thailand (e.g. 'FinTech / Payment Gateway', 'E-commerce Logistics', 'Healthcare IT')",
    )
    target_tech_stack: List[str] = Field(
        default_factory=list,
        description="Curated tech stack directly matching market co-occurrence clusters",
    )
    architecture_overview: str = Field(
        ...,
        description="High-level architectural design, system boundaries, and data flow patterns",
    )
    core_features: List[str] = Field(
        default_factory=list,
        description="Key MVP and production-grade capabilities required in implementation",
    )
    database_schema: str = Field(
        ...,
        description="Entity-relationship overview, primary data models, and storage strategies",
    )
    engineering_challenges: List[str] = Field(
        default_factory=list,
        description="Non-trivial engineering challenges addressed (concurrency, distributed transactions, idempotency, rate-limiting)",
    )
    difficulty: str = Field(
        default="Intermediate",
        description="Target implementation difficulty tier: 'Junior', 'Intermediate', or 'Advanced'",
    )
