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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        target_role TEXT GENERATED ALWAYS AS (role) VIRTUAL
    )
"""

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_skills_name ON skills_extracted(skill_name)",
    "CREATE INDEX IF NOT EXISTS idx_skills_experience ON skills_extracted(experience_level)",
    "CREATE INDEX IF NOT EXISTS idx_skills_job_id ON skills_extracted(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)",
    "CREATE INDEX IF NOT EXISTS idx_projects_created_at ON generated_projects(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_projects_role ON generated_projects(target_role)",
)

EXPECTED_INDEXES = (
    "idx_skills_name",
    "idx_skills_experience",
    "idx_skills_job_id",
    "idx_jobs_posted_at",
    "idx_jobs_source",
    "idx_projects_created_at",
    "idx_projects_role",
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
