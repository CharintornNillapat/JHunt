# src/generator/markdown_exporter.py
"""
Markdown Exporter for Portfolio Project Blueprints.
Renders ProjectIdeaSpec models into Markdown with YAML Frontmatter via native formatting
and safely exports them to the target ideas repository directory.
"""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional, Union

from src.extractor.schemas import ProjectIdeaSpec
from src.storage.db import DatabaseManager

# Default export path defined by project operational guardrails
DEFAULT_EXPORT_DIR = Path(
    r"C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project"
)


def _slugify(text: str) -> str:
    """Creates a filesystem-safe lowercase slug from arbitrary text."""
    cleaned = re.sub(r'[\\/:*?"<>|]', "", text)
    slug = re.sub(r"[^\w\s-]", "", cleaned).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "untitled-project"


def render_spec_markdown(
    spec: ProjectIdeaSpec,
    target_role: str,
    generated_date: str,
) -> str:
    """Renders ProjectIdeaSpec into clean Markdown with YAML Frontmatter using native formatting."""
    role_tag = target_role.lower().replace(" ", "-").replace("/", "-")
    tech_stack_yaml = "\n".join(f'  - "{t}"' for t in spec.target_tech_stack)
    tech_stack_joined = ", ".join(spec.target_tech_stack)

    features_lines: list[str] = []
    for i, f in enumerate(spec.core_features, 1):
        features_lines.append(
            f"### Feature {i}: {f}\n"
            f"- **Functional Scope:** Complete implementation of {f}.\n"
            f"- **Acceptance Criteria:** Validated with end-to-end integration tests and load benchmarks."
        )
    features_md = "\n\n".join(features_lines)

    challenges_lines: list[str] = []
    for i, c in enumerate(spec.engineering_challenges, 1):
        challenges_lines.append(
            f"### Challenge {i}: {c}\n"
            f"- **Problem Formulation:** Address edge conditions surrounding {c}.\n"
            f"- **Mitigation Strategy:** Implement idempotency keys, distributed locks, circuit breakers, or tiered caching strategies.\n"
            f"- **Interview Talking Point:** Discuss why this design was chosen over simpler alternatives and quantify performance trade-offs."
        )
    challenges_md = "\n\n".join(challenges_lines)

    return f"""---
title: "{spec.title}"
role: "{target_role}"
date: "{generated_date}"
difficulty: "{spec.difficulty}"
domain_industry: "{spec.domain_industry}"
market_relevance: "High (Derived from Thailand Tech Market Clusters)"
tech_stack:
{tech_stack_yaml}
tags:
  - portfolio-project
  - thailand-tech-market
  - {role_tag}
---

# {spec.title}

> **Target Engineering Role:** {target_role}  
> **Industry Domain:** {spec.domain_industry}  
> **Difficulty Level:** {spec.difficulty}  
> **Target Tech Stack:** {tech_stack_joined}

---

## 1. Executive Summary & Business Context

{spec.domain_industry} represents a critical business vertical in Thailand's digital ecosystem. This system is designed to solve real-world industrial constraints rather than serving as a basic demonstration application.

### Key Business Constraints Addressed:
- High-volume transaction spikes and event processing (e.g. flash sales, payday batch settlements).
- Critical data integrity and financial compliance (e.g. PromptPay webhook deduplication, PDPA data residency and anonymization).
- Resilient asynchronous processing with degraded-network survivability.

---

## 2. System Architecture & Data Flow

{spec.architecture_overview}

### Architecture Highlights:
- **API & Ingestion Tier:** Low-latency HTTP/gRPC endpoints with rate-limiting and authentication middleware.
- **Asynchronous Processing:** Event-driven message broker decoupling ingestion from heavy computation.
- **Data & Caching Tier:** Relational persistence for ACID guarantees coupled with distributed in-memory caching.
- **Observability:** Structured logging, Prometheus metrics endpoints, and health probes.

---

## 3. Core Feature Requirements

{features_md}

---

## 4. Database Schema Proposal & Storage Design

{spec.database_schema}

---

## 5. Key Engineering Challenges (Portfolio Highlights)

These engineering challenges serve as primary discussion points during technical interviews to showcase system design depth and trade-off analysis:

{challenges_md}

---

## 6. Recommended Portfolio Deliverables

To maximize resume and interview impact for the Thailand tech market, deliver the project following production standards:

1. **GitHub Repository Structure:**
   - `src/` (Clean architecture: domain, repository, service, handler layers)
   - `tests/` (Unit tests, integration tests, and concurrency race-condition tests)
   - `docker-compose.yml` (Single-command local environment spinning up all dependencies)
   - `docs/architecture.md` (C4 model diagrams or sequence charts)

2. **README.md Best Practices:**
   - Architecture diagram visual (Mermaid or PNG).
   - Benchmark results (e.g., requests per second, p99 latency via k6 or locust).
   - Setup instructions reproducible in `< 5 minutes`.

3. **Live Demonstration & Observability:**
   - Containerized deployment with public endpoints or interactive API docs (Swagger/OpenAPI).
   - Grafana dashboard snapshot demonstrating request latency and throughput under simulated load.
"""


class MarkdownExporter:
    """
    Renders ProjectIdeaSpec instances into markdown using native formatting
    and writes them with safe Windows pathing to the destination directory.
    """

    def __init__(
        self,
        export_dir: Optional[Union[str, Path]] = None,
        db: Optional[DatabaseManager] = None,
        turso: Optional[Any] = None,
    ):
        env_export_dir = os.getenv("EXPORT_DIR")
        if export_dir is not None:
            self.export_dir = Path(export_dir)
        elif env_export_dir:
            self.export_dir = Path(env_export_dir)
        else:
            self.export_dir = DEFAULT_EXPORT_DIR

        self.db = db or DatabaseManager()
        self.turso = turso

    def render_spec(
        self,
        spec: ProjectIdeaSpec,
        target_role: str,
        generated_date: Optional[str] = None,
    ) -> str:
        """Renders the ProjectIdeaSpec into a Markdown string with YAML frontmatter."""
        today_str = generated_date or date.today().isoformat()
        return render_spec_markdown(
            spec=spec,
            target_role=target_role,
            generated_date=today_str,
        )

    def export(
        self,
        spec: ProjectIdeaSpec,
        target_role: str,
        custom_date: Optional[str] = None,
    ) -> Path:
        """
        Renders, writes, and records the project blueprint to disk.
        Returns the Path to the written file.
        """
        self.export_dir.mkdir(parents=True, exist_ok=True)

        today_str = custom_date or date.today().isoformat()
        role_slug = _slugify(target_role)
        project_slug = _slugify(spec.title)

        filename = f"{today_str}_{role_slug}_{project_slug}.md"
        destination_path = self.export_dir / filename

        markdown_content = self.render_spec(
            spec=spec,
            target_role=target_role,
            generated_date=today_str,
        )

        with open(destination_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        self.db.record_generated_project(
            title=spec.title,
            role=target_role,
            tech_stack=spec.target_tech_stack,
            file_path=str(destination_path),
            domain_industry=spec.domain_industry,
        )

        if self.turso:
            self.turso.sync_blueprint(
                title=spec.title,
                role=target_role,
                difficulty=spec.difficulty,
                domain=spec.domain_industry,
                tech_stack=spec.target_tech_stack,
                spec_markdown=markdown_content,
            )

        return destination_path
