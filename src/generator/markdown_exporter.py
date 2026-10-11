# src/generator/markdown_exporter.py
"""
Markdown Exporter for Portfolio Project Blueprints.
Renders ProjectIdeaSpec models into Markdown with YAML Frontmatter via native formatting
and safely exports them to the target ideas repository directory.
"""
from __future__ import annotations

import json
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


def _yaml_str(value: str) -> str:
    """A JSON string is a valid YAML double-quoted scalar, so quotes and colons in LLM output stay safe."""
    return json.dumps(value, ensure_ascii=False)


def render_spec_markdown(
    spec: ProjectIdeaSpec,
    target_role: str,
    generated_date: str,
) -> str:
    """Renders ProjectIdeaSpec into Markdown with YAML frontmatter. Every line comes from the spec."""
    stack_yaml = "\n".join(f"  - {_yaml_str(t)}" for t in spec.target_tech_stack)
    skeleton_md = "\n".join(f"{i}. {step}" for i, step in enumerate(spec.walking_skeleton, 1))
    failures_md = "\n".join(f"- **{fm.failure}.** {fm.recovery}" for fm in spec.failure_modes)
    verification_md = "\n".join(f"- [ ] {check}" for check in spec.verification)
    out_of_scope_md = "\n".join(f"- {item}" for item in spec.out_of_scope)

    return f"""---
title: {_yaml_str(spec.title)}
role: {_yaml_str(target_role)}
date: {_yaml_str(generated_date)}
difficulty: {_yaml_str(spec.difficulty)}
domain_industry: {_yaml_str(spec.domain_industry)}
tech_stack:
{stack_yaml}
tags:
  - portfolio-project
  - thailand-tech-market
  - {_slugify(target_role)}
---

# {spec.title}

> **Role:** {target_role}
> **Domain:** {spec.domain_industry}
> **Difficulty:** {spec.difficulty}
> **Stack:** {", ".join(spec.target_tech_stack)}

## Core Problem

{spec.core_problem}

## System Boundary

{spec.system_boundary}

## Walking Skeleton

{skeleton_md}

## Contracts

{spec.contracts}

## Data Model

{spec.database_schema}

## Failure Modes & Recovery

{failures_md}

## Local Verification

{verification_md}

## Out of Scope

{out_of_scope_md}
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

    def is_saved(self, title: str) -> bool:
        """True when a blueprint with this title is already recorded locally or in Turso."""
        if self.db.has_generated_project(title):
            return True
        return bool(self.turso is not None and self.turso.is_available and self.turso.has_blueprint(title))

    def export(
        self,
        spec: ProjectIdeaSpec,
        target_role: str,
        custom_date: Optional[str] = None,
        skip_if_saved: bool = False,
    ) -> Optional[Path]:
        """
        Renders, writes, and records the project blueprint.
        With skip_if_saved, a spec whose title is already recorded is not written
        again and None is returned (used for curated fallbacks on quota-exhausted days).
        """
        if skip_if_saved and self.is_saved(spec.title):
            return None

        self.export_dir.mkdir(parents=True, exist_ok=True)

        today_str = custom_date or date.today().isoformat()
        filename = f"{today_str}_{_slugify(target_role)}_{_slugify(spec.title)}.md"
        destination_path = self.export_dir / filename

        markdown_content = self.render_spec(
            spec=spec,
            target_role=target_role,
            generated_date=today_str,
        )
        destination_path.write_text(markdown_content, encoding="utf-8")

        record = {
            "title": spec.title,
            "role": target_role,
            "difficulty": spec.difficulty,
            "domain": spec.domain_industry,
            "tech_stack": spec.target_tech_stack,
            "spec_markdown": markdown_content,
        }
        self.db.record_generated_project(**record)
        if self.turso:
            self.turso.sync_blueprint(**record)

        return destination_path
