# src/extractor/__init__.py
from .schemas import ExtractedJob, ProjectIdeaSpec
from .text_sanitizer import clean_html, strip_boilerplate, build_sanitized_job_prompt
from .llm_extractor import GeminiExtractor, process_unprocessed_jobs

__all__ = [
    "ExtractedJob",
    "ProjectIdeaSpec",
    "clean_html",
    "strip_boilerplate",
    "build_sanitized_job_prompt",
    "GeminiExtractor",
    "process_unprocessed_jobs",
]
