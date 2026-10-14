# src/storage/schema.py
"""
Single source of truth for the relational schema. DatabaseManager (local SQLite)
and TursoClient (LibSQL) both execute SCHEMA_STATEMENTS, and web/src/lib/turso.ts
reads `generated_projects` with these exact column names.
"""

GENERATED_PROJECTS_DDL = """
    CREATE TABLE IF NOT EXISTS generated_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        role TEXT NOT NULL,
        difficulty TEXT,
        domain TEXT,
        tech_stack TEXT,
        spec_markdown TEXT,
        provenance TEXT DEFAULT 'llm',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

SKILL_STATS_DDL = """
    CREATE TABLE IF NOT EXISTS skill_stats (
        skill TEXT PRIMARY KEY,
        category TEXT,
        job_count INTEGER NOT NULL,
        salary_count INTEGER DEFAULT 0,
        avg_salary_thb INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_skills_name ON skills_extracted(skill_name)",
    "CREATE INDEX IF NOT EXISTS idx_skills_job_id ON skills_extracted(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_projects_created_at ON generated_projects(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects(role)",
    "CREATE INDEX IF NOT EXISTS idx_skill_stats_category ON skill_stats(category)",
    "CREATE INDEX IF NOT EXISTS idx_skill_stats_job_count ON skill_stats(job_count DESC)",
)

EXPECTED_INDEXES = (
    "idx_skills_name",
    "idx_skills_job_id",
    "idx_projects_created_at",
    "idx_projects_role",
    "idx_skill_stats_category",
    "idx_skill_stats_job_count",
)

TABLE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        url TEXT NOT NULL,
        location TEXT,
        salary TEXT,
        work_type TEXT,
        raw_content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        posted_at TIMESTAMP,
        source TEXT,
        min_salary INTEGER,
        max_salary INTEGER,
        currency TEXT DEFAULT 'THB',
        extract_attempts INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS skills_extracted (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT UNIQUE,
        skill_name TEXT,
        category TEXT,
        experience_level TEXT,
        must_have_skills TEXT,
        nice_to_have_skills TEXT,
        frameworks TEXT,
        databases TEXT,
        cloud_infra TEXT,
        tools TEXT,
        extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
    )
    """,
    GENERATED_PROJECTS_DDL,
    SKILL_STATS_DDL,
)

BASE_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_projects_title ON generated_projects (title)",
)

ALL_INDEX_STATEMENTS = (
    *BASE_INDEX_STATEMENTS,
    *INDEX_STATEMENTS,
)

SCHEMA_STATEMENTS = (
    *TABLE_STATEMENTS,
    *ALL_INDEX_STATEMENTS,
)

# Local SQLite files created before the schemas were unified stored
# (domain_industry, file_path, generated_at). Rebuild them into the shared shape.
LEGACY_PROJECTS_MIGRATION = (
    "ALTER TABLE generated_projects RENAME TO generated_projects_legacy",
    GENERATED_PROJECTS_DDL,
    """
    INSERT INTO generated_projects (id, title, role, domain, tech_stack, created_at)
    SELECT id, title, role, domain_industry, tech_stack, generated_at FROM generated_projects_legacy
    """,
    "DROP TABLE generated_projects_legacy",
)

import json
import re
from typing import Any, Dict, List, Optional

KNOWN_LANGUAGES = frozenset([
    "python", "typescript", "javascript", "go", "golang", "java", "c++", "c#", "rust",
    "php", "sql", "kotlin", "swift", "ruby", "scala", "dart", "r", "html", "css"
])
KNOWN_CLOUDS = frozenset([
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "cloudflare", "linux"
])
KNOWN_DBS = frozenset([
    "postgresql", "redis", "mongodb", "mysql", "kafka", "elasticsearch", "sqlite",
    "dynamodb", "rabbitmq"
])
KNOWN_FWS = frozenset([
    "fastapi", "react", "next.js", "django", "spring boot", "express", "vue",
    "tailwind css", "pytorch", "nodejs", "node.js"
])


def canonicalize_skill_name(raw: str) -> str:
    """Canonicalize a skill name with version suffix stripping."""
    cleaned = re.sub(r"\s+v?\d+(?:\.\d+)*$", "", raw.strip()).strip()
    lower = cleaned.lower()
    if lower in ("golang", "go"):
        return "Go"
    if lower in ("nodejs", "node.js", "node"):
        return "Node.js"
    if lower in ("postgres", "postgresql") or lower.startswith("postgres ") or lower.startswith("postgresql "):
        return "PostgreSQL"
    if lower in ("k8s", "kubernetes"):
        return "Kubernetes"
    if lower in ("ts", "typescript"):
        return "TypeScript"
    if lower in ("js", "javascript"):
        return "JavaScript"
    if lower in ("py", "python", "python3") or lower.startswith("python "):
        return "Python"
    if lower in ("react", "react.js", "reactjs"):
        return "React"
    if lower in ("nextjs", "next.js"):
        return "Next.js"
    if lower in ("vue", "vue.js", "vuejs"):
        return "Vue.js"
    if lower in ("fastapi", "fast api"):
        return "FastAPI"
    if lower in ("aws", "amazon web services"):
        return "AWS"
    if lower in ("gcp", "google cloud", "google cloud platform"):
        return "GCP"
    if lower == "docker":
        return "Docker"
    if lower == "sql":
        return "SQL"
    if lower in ("mongodb", "mongo"):
        return "MongoDB"
    if lower in ("tailwind", "tailwindcss", "tailwind css"):
        return "Tailwind CSS"
    if len(cleaned) > 1:
        return cleaned[0].upper() + cleaned[1:]
    return cleaned


def classify_skill_category(canon: str, default_category: Optional[str] = None) -> str:
    """Classifies a skill into language, framework, database, cloud, tool, or other."""
    lower = canon.lower()
    if lower in KNOWN_LANGUAGES:
        return "language"
    if lower in KNOWN_CLOUDS:
        return "cloud"
    if lower in KNOWN_DBS:
        return "database"
    if lower in KNOWN_FWS:
        return "framework"
    if default_category in ("language", "cloud", "database", "framework", "tool"):
        return default_category
    return "other"


def _parse_tokens(val: Any) -> List[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x) for x in val if x]
    if isinstance(val, str):
        v = val.strip()
        if not v:
            return []
        if v.startswith("[") and v.endswith("]"):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if x]
            except Exception:
                pass
        return [x.strip() for x in v.split(",") if x.strip()]
    return []


def aggregate_skill_stats(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Computes pre-aggregated skill_stats rows from extracted skill records joined with job salaries.
    Each distinct skill in a job counts towards job_count once.
    THB salaries with min_salary and max_salary contribute to salary_count and avg_salary_thb.
    """
    from collections import defaultdict

    job_counts = defaultdict(int)
    salary_midpoints = defaultdict(list)
    skill_categories = {}

    for row in records:
        job_skills: Dict[str, str] = {}  # canonical_name -> category

        def add_tokens(tokens: List[str], default_cat: Optional[str] = None):
            for tok in tokens:
                canon = canonicalize_skill_name(tok)
                if canon:
                    cat = classify_skill_category(canon, default_cat)
                    if canon not in job_skills or (job_skills[canon] == "other" and cat != "other"):
                        job_skills[canon] = cat

        add_tokens(_parse_tokens(row.get("must_have_skills")), "language")
        add_tokens(_parse_tokens(row.get("nice_to_have_skills")), None)
        add_tokens(_parse_tokens(row.get("frameworks")), "framework")
        add_tokens(_parse_tokens(row.get("databases")), "database")
        add_tokens(_parse_tokens(row.get("cloud_infra")), "cloud")
        add_tokens(_parse_tokens(row.get("tools")), "tool")
        if row.get("skill_name"):
            add_tokens([str(row["skill_name"])], str(row.get("category") or ""))

        min_sal = row.get("min_salary")
        max_sal = row.get("max_salary")
        curr = str(row.get("currency") or "THB").strip().upper()
        has_thb_salary = (min_sal is not None and max_sal is not None and curr == "THB")
        midpoint = (float(min_sal) + float(max_sal)) / 2.0 if has_thb_salary else None

        for canon, cat in job_skills.items():
            job_counts[canon] += 1
            if canon not in skill_categories or (skill_categories[canon] == "other" and cat != "other"):
                skill_categories[canon] = cat
            if midpoint is not None:
                salary_midpoints[canon].append(midpoint)

    results = []
    for skill, count in job_counts.items():
        mids = salary_midpoints.get(skill, [])
        sal_count = len(mids)
        avg_sal = round(sum(mids) / sal_count) if sal_count > 0 else None
        results.append({
            "skill": skill,
            "category": skill_categories.get(skill, "other"),
            "job_count": count,
            "salary_count": sal_count,
            "avg_salary_thb": avg_sal,
        })

    results.sort(key=lambda s: (-s["job_count"], s["skill"]))
    return results
