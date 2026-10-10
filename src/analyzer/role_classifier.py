# src/analyzer/role_classifier.py
"""
Role classification engine for tech job postings.
Categorizes jobs into standard engineering disciplines using title heuristics
and extracted technology profiles with robust English and Thai support.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional, Set, Tuple

from src.extractor.schemas import ExtractedJob


class StandardRole(str, Enum):
    BACKEND = "Backend Engineer"
    FRONTEND = "Frontend Engineer"
    FULLSTACK = "Fullstack Engineer"
    DATA_ENGINEER = "Data Engineer / Data Analyst"
    DEVOPS_CLOUD = "DevOps / Cloud / Platform Engineer"
    AI_ML = "AI / ML / Computer Vision Engineer"
    OTHER = "Other / General Tech"


# Thai terms matched as unanchored substrings (Thai script does not use spaces between words)
THAI_ROLE_KEYWORDS: List[Tuple[StandardRole, List[str]]] = [
    (
        StandardRole.FULLSTACK,
        ["ฟูลสแต็ก", "เต็มรูปแบบ"],
    ),
    (
        StandardRole.DATA_ENGINEER,
        ["วิศวกรข้อมูล", "นักวิเคราะห์ข้อมูล", "นักวิทยาศาสตร์ข้อมูล", "ข้อมูลขนาดใหญ่"],
    ),
    (
        StandardRole.AI_ML,
        ["วิศวกรปัญญาประดิษฐ์", "วิศวกร ai", "วิศวกรเอไอ", "ปัญญาประดิษฐ์", "การเรียนรู้ของเครื่อง"],
    ),
    (
        StandardRole.DEVOPS_CLOUD,
        ["วิศวกรคลาวด์", "วิศวกรระบบ"],
    ),
    (
        StandardRole.FRONTEND,
        ["นักพัฒนาฟรอนต์เอนด์", "ฟรอนต์เอนด์", "ส่วนหน้า"],
    ),
    (
        StandardRole.BACKEND,
        ["นักพัฒนาแบ็กเอนด์", "แบ็กเอนด์", "ส่วนหลัง"],
    ),
]

# English patterns matched with word boundaries
ENGLISH_ROLE_TITLE_PATTERNS = [
    (
        StandardRole.FULLSTACK,
        re.compile(r"(?i)\b(?:full[-\s]?stack|fullstack)\b"),
    ),
    (
        StandardRole.DATA_ENGINEER,
        re.compile(
            r"(?i)\b(?:data\s+(?:engineer|analyst|scientist|architect)|bi\s+developer|business\s+intelligence|etl\s+developer|big\s+data|analytics\s+engineer)\b"
        ),
    ),
    (
        StandardRole.AI_ML,
        re.compile(
            r"(?i)\b(?:ai\s+engineer|machine\s+learning|ml\s+engineer|deep\s+learning|computer\s+vision|nlp\s+engineer|llm\s+engineer|ai\s+researcher)\b"
        ),
    ),
    (
        StandardRole.DEVOPS_CLOUD,
        re.compile(
            r"(?i)\b(?:devops|sre|site\s+reliability|cloud\s+engineer|cloud\s+architect|platform\s+engineer|infrastructure\s+engineer|sysadmin)\b"
        ),
    ),
    (
        StandardRole.FRONTEND,
        re.compile(
            r"(?i)\b(?:front[-\s]?end|frontend|ui/ux\s+developer|client[-\s]?side|react\s+developer|vue\s+developer|angular\s+developer)\b"
        ),
    ),
    (
        StandardRole.BACKEND,
        re.compile(
            r"(?i)\b(?:back[-\s]?end|backend|server[-\s]?side|api\s+developer|golang\s+developer|go\s+developer|python\s+developer|java\s+developer|\.net\s+developer|c#\s+developer|node(?:\.js)?\s+developer|php\s+developer)\b"
        ),
    ),
]

# Signature technology keywords per domain for fallback classification
FRONTEND_SIGNATURES: Set[str] = {
    "react", "vue", "vue.js", "angular", "next.js", "nuxt", "svelte", "typescript",
    "javascript", "html", "css", "tailwind", "redux", "webpack",
}

BACKEND_SIGNATURES: Set[str] = {
    "go", "golang", "java", "python", "fastapi", "django", "flask", "spring",
    "spring boot", "node.js", "express", "nest.js", "c#", ".net", "php", "laravel",
    "postgresql", "mysql", "mongodb", "redis", "rest api", "grpc", "graphql",
}

DATA_SIGNATURES: Set[str] = {
    "spark", "apache spark", "airflow", "apache airflow", "dbt", "sql", "bigquery",
    "snowflake", "hadoop", "databricks", "kafka", "apache kafka", "pandas",
}

AI_SIGNATURES: Set[str] = {
    "pytorch", "tensorflow", "keras", "opencv", "scikit-learn", "huggingface",
    "transformers", "langchain", "llama", "deep learning", "nlp", "llm",
}

DEVOPS_SIGNATURES: Set[str] = {
    "kubernetes", "k8s", "docker", "terraform", "ansible", "ci/cd", "aws", "gcp",
    "azure", "helm", "prometheus", "grafana", "jenkins",
}

GENERIC_DEV_THAI_KEYWORDS = [
    "โปรแกรมเมอร์", "นักพัฒนาซอฟต์แวร์", "วิศวกรซอฟต์แวร์", "นักพัฒนา",
]

GENERIC_DEV_ENGLISH_PATTERN = re.compile(
    r"(?i)\b(?:software\s+(?:engineer|developer)|developer|programmer|coder)\b"
)


def classify_role(title: str, extracted_job: Optional[ExtractedJob] = None) -> StandardRole:
    """
    Classifies a job into a StandardRole based on its title and extracted tech stack.
    Handles English and Thai phrasing accurately.
    """
    title_clean = (title or "").strip()
    title_lower = title_clean.lower()

    # Step 1: Check specific Thai keywords (unanchored substrings)
    for role, keywords in THAI_ROLE_KEYWORDS:
        for kw in keywords:
            if kw.lower() in title_lower:
                return role

    # Step 2: Check English regex patterns with word boundaries
    for role, pattern in ENGLISH_ROLE_TITLE_PATTERNS:
        if pattern.search(title_clean):
            return role

    # Step 3: If title is generic, inspect tech stack if available
    if extracted_job is not None:
        all_tech = {t.lower().strip() for t in extracted_job.all_tech_stack}

        has_fe = bool(all_tech & FRONTEND_SIGNATURES)
        has_be = bool(all_tech & BACKEND_SIGNATURES)
        has_data = bool(all_tech & DATA_SIGNATURES)
        has_ai = bool(all_tech & AI_SIGNATURES)
        has_devops = bool(all_tech & DEVOPS_SIGNATURES)

        # Composite fullstack
        if has_fe and has_be:
            return StandardRole.FULLSTACK
        if has_ai:
            return StandardRole.AI_ML
        if has_data:
            return StandardRole.DATA_ENGINEER
        if has_devops and not has_be and not has_fe:
            return StandardRole.DEVOPS_CLOUD
        if has_fe and not has_be:
            return StandardRole.FRONTEND
        if has_be:
            return StandardRole.BACKEND

    # Step 4: Check generic developer terms in Thai and English (default to Backend Engineer)
    if any(kw in title_lower for kw in GENERIC_DEV_THAI_KEYWORDS):
        return StandardRole.BACKEND

    if GENERIC_DEV_ENGLISH_PATTERN.search(title_clean):
        return StandardRole.BACKEND

    return StandardRole.OTHER
