# src/generator/markdown_exporter.py
"""
Markdown Exporter for Portfolio Project Blueprints.
Renders ProjectIdeaSpec models into Markdown with YAML Frontmatter via Jinja2
and safely exports them to the target Windows ideas repository directory.
"""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader

from src.extractor.schemas import ProjectIdeaSpec
from src.storage.db import DatabaseManager

# Default export path defined by project operational guardrails
DEFAULT_EXPORT_DIR = Path(
    r"C:\Users\MRmar\Desktop\Mid years projects\Ideas\Real-world-tech-industrial-insight-for-building-project"
)
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_FILE = "project_spec.md.jinja"


def _slugify(text: str) -> str:
    """Creates a filesystem-safe lowercase slug from arbitrary text."""
    # Remove characters forbidden on Windows: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', "", text)
    # Replace non-alphanumeric (except dashes and underscores) with hyphens
    slug = re.sub(r"[^\w\s-]", "", cleaned).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "untitled-project"


class MarkdownExporter:
    """
    Renders ProjectIdeaSpec instances into markdown using Jinja2 templates
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
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._template = self._jinja_env.get_template(TEMPLATE_FILE)

    def render_spec(
        self,
        spec: ProjectIdeaSpec,
        target_role: str,
        generated_date: Optional[str] = None,
    ) -> str:
        """Renders the ProjectIdeaSpec into a Markdown string with YAML frontmatter."""
        today_str = generated_date or date.today().isoformat()
        return self._template.render(
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
        # Ensure destination directory exists
        self.export_dir.mkdir(parents=True, exist_ok=True)

        today_str = custom_date or date.today().isoformat()
        role_slug = _slugify(target_role)
        project_slug = _slugify(spec.title)

        filename = f"{today_str}_{role_slug}_{project_slug}.md"
        destination_path = self.export_dir / filename

        # Render content
        markdown_content = self.render_spec(
            spec=spec,
            target_role=target_role,
            generated_date=today_str,
        )

        # Write safely with utf-8 encoding
        with open(destination_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Record into database
        self.db.record_generated_project(
            title=spec.title,
            role=target_role,
            tech_stack=spec.target_tech_stack,
            file_path=str(destination_path),
            domain_industry=spec.domain_industry,
        )

        # Sync to Turso cloud database if available
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
