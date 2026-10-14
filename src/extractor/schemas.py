# src/extractor/schemas.py
"""
Pydantic schemas for structured job market extraction and portfolio ideation.
Built with Pydantic v2 for strict type safety and Gemini structured output compliance.
"""
from typing import List
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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


class BatchExtractedJob(ExtractedJob):
    """One entry of a batch extraction response, tied back to its request by `id`."""
    id: int = Field(..., description="The job's id, copied exactly from the input list")


class FailureMode(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    failure: str = Field(..., description="A concrete thing that goes wrong (duplicate delivery, crash mid-write, dependency down)")
    recovery: str = Field(..., description="How the system detects it and recovers without losing or duplicating data")


class ProjectIdeaSpec(BaseModel):
    """
    Buildable portfolio project spec: one core engineering problem, one service,
    one datastore, and checks a single developer can run locally.
    """
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    title: str = Field(..., description="Specific project title naming the core problem")
    domain_industry: str = Field(..., description="Thailand business context (e.g. 'FinTech / PromptPay payments')")
    core_problem: str = Field(
        ...,
        description="The single engineering problem the project exists to solve, in one or two sentences",
    )
    target_tech_stack: List[str] = Field(
        default_factory=list,
        description="Only the technologies the core problem needs, without version numbers",
    )
    system_boundary: str = Field(
        ...,
        description="Exactly one service and one primary datastore (plus at most one cache or queue if the problem needs it). State what is in and out of scope",
    )
    walking_skeleton: List[str] = Field(
        default_factory=list,
        description="Ordered build steps (typically 3 to 7). Step 1 is a thin end-to-end slice that runs locally; each later step adds one capability",
    )
    contracts: str = Field(
        ...,
        description="Typed request, response and event contracts as Pydantic models or OpenAPI paths with status codes",
    )
    database_schema: str = Field(..., description="Tables, keys and constraints that enforce the core invariant")
    failure_modes: List[FailureMode] = Field(default_factory=list)
    acceptance_tests: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("acceptance_tests", "verification"),
        description="3 to 5 falsifiable local checks (pytest, Locust, Playwright) with concrete pass conditions such as counts or invariants. No latency percentiles or throughput targets",
    )
    out_of_scope: List[str] = Field(
        default_factory=list,
        description="Tempting additions deliberately excluded to keep the project buildable by one developer in 2 to 4 weeks",
    )
    difficulty: str = Field(
        default="Intermediate",
        description="'Junior', 'Intermediate', or 'Advanced'",
    )

    @property
    def verification(self) -> List[str]:
        """Backward-compatible alias for acceptance_tests."""
        return self.acceptance_tests

    @verification.setter
    def verification(self, val: List[str]) -> None:
        self.acceptance_tests = val
