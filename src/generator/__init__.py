# src/generator/__init__.py
from pathlib import Path
from typing import List, Optional

from src.generator.ideation_engine import IdeationEngine
from src.generator.markdown_exporter import MarkdownExporter, DEFAULT_EXPORT_DIR


def generate_and_export_role_blueprint(
    target_role: str,
    tech_stack: List[str],
    domain_hint: Optional[str] = None,
    engine: Optional[IdeationEngine] = None,
    exporter: Optional[MarkdownExporter] = None,
) -> Optional[Path]:
    """
    Convenience orchestrator: prompts the IdeationEngine for an enterprise spec
    and exports it to Markdown with YAML frontmatter.
    """
    if engine is None:
        engine = IdeationEngine()
    if exporter is None:
        exporter = MarkdownExporter()

    spec = engine.generate_project_spec(
        target_role=target_role,
        tech_stack=tech_stack,
        domain_hint=domain_hint,
    )
    if not spec:
        return None

    return exporter.export(spec=spec, target_role=target_role)


__all__ = [
    "IdeationEngine",
    "MarkdownExporter",
    "DEFAULT_EXPORT_DIR",
    "generate_and_export_role_blueprint",
]
