# src/analyzer/cluster_analyzer.py
"""
Cluster Analyzer Module for Thailand Tech Job Market Intelligence.
Aggregates skill distributions, computes tech stack co-occurrences,
and extracts dominant technology clusters per engineering role.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from src.analyzer.role_classifier import StandardRole, classify_role
from src.analyzer.schemas import (
    CooccurrenceItem,
    MarketReport,
    RoleCluster,
    SkillFrequencyItem,
)
from src.extractor.schemas import ExtractedJob
from src.storage.db import DatabaseManager


def compute_pairwise_cooccurrences(
    jobs: List[ExtractedJob],
) -> Counter[Tuple[str, str]]:
    """Computes pairwise co-occurrences of tech stack components across jobs."""
    counter: Counter[Tuple[str, str]] = Counter()
    for job in jobs:
        all_tech = sorted(set(t.strip() for t in job.all_tech_stack if t.strip()))
        if len(all_tech) >= 2:
            for pair in combinations(all_tech, 2):
                counter[pair] += 1
    return counter


class ClusterAnalyzer:
    """
    Analyzes historical and extracted job records in SQLite database to uncover
    trending tech stacks, co-occurrence pairs, and role-based clusters.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def _normalize_tag(self, tag: str) -> str:
        """Standardizes casing and whitespace for clean aggregation."""
        return tag.strip()

    def _compute_frequency_list(
        self,
        counter: Counter[str],
        total: int,
        limit: int = 15,
    ) -> List[SkillFrequencyItem]:
        """Converts a Counter into sorted SkillFrequencyItem models with percentages."""
        if total == 0:
            return []
        items = []
        for name, count in counter.most_common(limit):
            pct = round((count / total) * 100.0, 1)
            items.append(SkillFrequencyItem(name=name, count=count, percentage=pct))
        return items

    def generate_market_report(self, limit_top: int = 15) -> MarketReport:
        """
        Runs comprehensive analysis over all extracted jobs in the database.
        Returns a complete MarketReport.
        """
        all_jobs = self.db.get_all_extracted_skills()
        total_jobs = len(all_jobs)

        if total_jobs == 0:
            return MarketReport(total_jobs_analyzed=0)

        must_have_counter: Counter[str] = Counter()
        nice_to_have_counter: Counter[str] = Counter()
        frameworks_counter: Counter[str] = Counter()
        databases_counter: Counter[str] = Counter()
        cloud_counter: Counter[str] = Counter()
        tools_counter: Counter[str] = Counter()
        experience_counter: Counter[str] = Counter()

        # Co-occurrence tracking across all jobs using unified helper
        cooccurrence_counter = compute_pairwise_cooccurrences(all_jobs)

        # Grouping jobs by role
        role_jobs: Dict[StandardRole, List[ExtractedJob]] = defaultdict(list)

        for job in all_jobs:
            experience_counter[job.experience_level or "Unknown"] += 1

            for s in job.must_have_skills:
                norm = self._normalize_tag(s)
                if norm:
                    must_have_counter[norm] += 1
            for s in job.nice_to_have_skills:
                norm = self._normalize_tag(s)
                if norm:
                    nice_to_have_counter[norm] += 1
            for f in job.frameworks:
                norm = self._normalize_tag(f)
                if norm:
                    frameworks_counter[norm] += 1
            for d in job.databases:
                norm = self._normalize_tag(d)
                if norm:
                    databases_counter[norm] += 1
            for c in job.cloud_infra:
                norm = self._normalize_tag(c)
                if norm:
                    cloud_counter[norm] += 1
            for t in job.tools:
                norm = self._normalize_tag(t)
                if norm:
                    tools_counter[norm] += 1

            # Classify role
            role = classify_role(job.job_title, job)
            role_jobs[role].append(job)

        # Assemble top co-occurrence list
        top_cooccurrences = [
            CooccurrenceItem(tech_a=pair[0], tech_b=pair[1], count=count)
            for pair, count in cooccurrence_counter.most_common(limit_top)
        ]


        # Analyze role clusters
        role_clusters: Dict[str, RoleCluster] = {}
        for role_enum, jobs in role_jobs.items():
            role_name = role_enum.value
            role_sample_size = len(jobs)
            role_tech_counter: Counter[str] = Counter()

            for j in jobs:
                for t in j.all_tech_stack:
                    norm = self._normalize_tag(t)
                    if norm:
                        role_tech_counter[norm] += 1

            top_role_skills = self._compute_frequency_list(
                role_tech_counter,
                role_sample_size,
                limit=10,
            )
            # Dominant stack: top 4-6 most prevalent technologies for this role
            dominant_stack = [item.name for item in top_role_skills[:5]]

            role_clusters[role_name] = RoleCluster(
                role=role_name,
                sample_size=role_sample_size,
                top_skills=top_role_skills,
                dominant_stack=dominant_stack,
            )

        return MarketReport(
            total_jobs_analyzed=total_jobs,
            top_must_have_skills=self._compute_frequency_list(must_have_counter, total_jobs, limit_top),
            top_nice_to_have_skills=self._compute_frequency_list(nice_to_have_counter, total_jobs, limit_top),
            top_frameworks=self._compute_frequency_list(frameworks_counter, total_jobs, limit_top),
            top_databases=self._compute_frequency_list(databases_counter, total_jobs, limit_top),
            top_cloud_infra=self._compute_frequency_list(cloud_counter, total_jobs, limit_top),
            top_tools=self._compute_frequency_list(tools_counter, total_jobs, limit_top),
            top_cooccurrences=top_cooccurrences,
            role_clusters=role_clusters,
            experience_distribution=dict(experience_counter.most_common()),
        )

    def get_dominant_stack_for_role(self, role: str) -> List[str]:
        """
        Returns the top consensus tech stack list for a given role title.
        Falls back to a default high-value Thailand stack if sample data is insufficient.
        """
        report = self.generate_market_report()
        cluster = report.role_clusters.get(role)
        if cluster and cluster.dominant_stack:
            return cluster.dominant_stack

        # Sensible defaults for Thailand tech market
        defaults = {
            StandardRole.BACKEND.value: ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
            StandardRole.FRONTEND.value: ["TypeScript", "React", "Next.js", "Tailwind CSS"],
            StandardRole.FULLSTACK.value: ["TypeScript", "React", "Node.js", "PostgreSQL", "Docker"],
            StandardRole.DATA_ENGINEER.value: ["Python", "Apache Spark", "Airflow", "PostgreSQL", "BigQuery"],
            StandardRole.AI_ML.value: ["Python", "PyTorch", "FastAPI", "Docker", "OpenCV"],
            StandardRole.DEVOPS_CLOUD.value: ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD"],
        }
        return defaults.get(role, ["Python", "PostgreSQL", "Docker"])
