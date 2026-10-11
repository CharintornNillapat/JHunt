import "server-only";
import { cache } from "react";
import { createClient, type Client } from "@libsql/client";
import { formatDate, parseTechStack } from "./format";

export { formatDate, parseTechStack };

// Mirrors the generated_projects columns in src/storage/schema.py (shared by SQLite and Turso).
export interface GeneratedProject {
  id: number;
  title: string;
  role: string;
  difficulty: string;
  domain: string;
  tech_stack: string;
  spec_markdown: string;
  created_at: string;
}

export type ProjectSummary = Omit<GeneratedProject, "spec_markdown">;

let rawUrl = process.env.TURSO_DATABASE_URL?.trim();
const authToken = process.env.TURSO_AUTH_TOKEN?.trim();

if (rawUrl?.startsWith("libsql://")) {
  rawUrl = "https://" + rawUrl.slice("libsql://".length);
}
const url = rawUrl;

export const turso: Client | null = url
  ? createClient({
      url,
      authToken: authToken || undefined,
    })
  : null;

export const isTursoConfigured = Boolean(turso);

if (!turso) {
  console.warn(
    "[Turso] TURSO_DATABASE_URL environment variable is not defined or empty. LibSQL client is disabled."
  );
} else {
  console.log(
    `[Turso] LibSQL client configured for endpoint: ${url?.replace(/\/\/.*@/, "//***@")}`
  );
}

export async function getAllProjects(): Promise<GeneratedProject[]> {
  if (!turso) {
    console.warn("[Turso] getAllProjects: Client not configured (missing TURSO_DATABASE_URL).");
    return [];
  }
  try {
    const result = await turso.execute(
      "SELECT id, title, role, difficulty, domain, tech_stack, spec_markdown, created_at FROM generated_projects WHERE id IN (SELECT MAX(id) FROM generated_projects GROUP BY title) ORDER BY created_at DESC"
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      title: String(row.title ?? ""),
      role: String(row.role ?? ""),
      difficulty: String(row.difficulty ?? "Intermediate"),
      domain: String(row.domain ?? ""),
      tech_stack: String(row.tech_stack ?? ""),
      spec_markdown: String(row.spec_markdown ?? ""),
      created_at: String(row.created_at ?? ""),
    }));
  } catch (err) {
    console.error("[Turso] Could not fetch projects:", err);
    return [];
  }
}

export const getProjectById = cache(async (id: string | number): Promise<GeneratedProject | null> => {
  if (!turso) {
    console.warn(`[Turso] getProjectById(${id}): Client not configured (missing TURSO_DATABASE_URL).`);
    return null;
  }
  if (!/^\d+$/.test(String(id))) {
    return null;
  }
  try {
    const result = await turso.execute({
      sql: "SELECT id, title, role, difficulty, domain, tech_stack, spec_markdown, created_at FROM generated_projects WHERE id = ? LIMIT 1",
      args: [id],
    });
    if (result.rows.length === 0) {
      return null;
    }
    const row = result.rows[0];
    return {
      id: Number(row.id),
      title: String(row.title ?? ""),
      role: String(row.role ?? ""),
      difficulty: String(row.difficulty ?? "Intermediate"),
      domain: String(row.domain ?? ""),
      tech_stack: String(row.tech_stack ?? ""),
      spec_markdown: String(row.spec_markdown ?? ""),
      created_at: String(row.created_at ?? ""),
    };
  } catch (err) {
    console.error(`[Turso] Could not fetch project ${id}:`, err);
    return null;
  }
});

export interface MarketMetricItem {
  name: string;
  count: number;
  percentage?: number;
}

export interface CompensatedSkillItem {
  skill: string;
  avg_salary: number;
  sample_count: number;
}

export interface MarketAnalytics {
  totalJobs: number;
  totalSkills: number;
  totalBlueprints: number;
  languages: MarketMetricItem[];
  clouds: MarketMetricItem[];
  databases: MarketMetricItem[];
  frameworks: MarketMetricItem[];
  top_compensated_skills: CompensatedSkillItem[];
}

export async function getMarketAnalytics(): Promise<MarketAnalytics | null> {
  if (!turso) {
    console.warn("[Turso] getMarketAnalytics: Client is not configured. Missing TURSO_DATABASE_URL.");
    return null;
  }

  try {
    const [jobsRes, blueprintsRes, skillsRes, compRes] = await Promise.allSettled([
      turso.execute("SELECT COUNT(*) AS total FROM jobs"),
      turso.execute("SELECT COUNT(DISTINCT title) AS total FROM generated_projects"),
      turso.execute(
        "SELECT * FROM skills_extracted WHERE (experience_level IS NULL OR experience_level != 'Non-Tech')"
      ),
      turso.execute(`
        SELECT 
          s.skill_name,
          COUNT(DISTINCT j.id) as sample_count,
          ROUND(AVG((j.min_salary + j.max_salary) / 2)) as avg_salary
        FROM skills_extracted s
        JOIN jobs j ON s.job_id = j.id
        WHERE j.min_salary IS NOT NULL 
          AND j.max_salary IS NOT NULL 
          AND s.skill_name IS NOT NULL
          AND (s.experience_level IS NULL OR s.experience_level != 'Non-Tech')
        GROUP BY s.skill_name
        HAVING sample_count >= 1
        ORDER BY avg_salary DESC
        LIMIT 10;
      `),
    ]);

    if (jobsRes.status === "rejected") {
      console.error("[Turso] getMarketAnalytics: Failed to query total jobs:", jobsRes.reason);
    }
    if (blueprintsRes.status === "rejected") {
      console.error("[Turso] getMarketAnalytics: Failed to query total blueprints:", blueprintsRes.reason);
    }
    if (skillsRes.status === "rejected") {
      console.warn("[Turso] getMarketAnalytics: Filtered skills query rejected:", skillsRes.reason);
    }
    if (compRes.status === "rejected") {
      console.warn("[Turso] getMarketAnalytics: Compensation aggregation query rejected:", compRes.reason);
    }

    const totalJobsCount =
      jobsRes.status === "fulfilled" && jobsRes.value.rows[0]?.total
        ? Number(jobsRes.value.rows[0].total)
        : 0;

    const totalBlueprintsCount =
      blueprintsRes.status === "fulfilled" && blueprintsRes.value.rows[0]?.total
        ? Number(blueprintsRes.value.rows[0].total)
        : 0;

    let skillsRows =
      skillsRes.status === "fulfilled" ? skillsRes.value.rows : [];

    // Resilient fallback: If the filtered query failed, attempt an unfiltered SELECT *
    if (skillsRes.status === "rejected") {
      try {
        console.warn("[Turso] getMarketAnalytics: Attempting fallback unfiltered SELECT * FROM skills_extracted...");
        const fallbackSkillsRes = await turso.execute("SELECT * FROM skills_extracted");
        skillsRows = fallbackSkillsRes.rows;
        console.log(`[Turso] getMarketAnalytics: Fallback query succeeded with ${skillsRows.length} rows.`);
      } catch (fallbackErr) {
        console.error("[Turso] getMarketAnalytics: Fallback query also failed:", fallbackErr);
      }
    }

    if (skillsRows.length === 0) {
      console.warn(
        `[Turso] getMarketAnalytics: No skills found (jobsCount=${totalJobsCount}, blueprintsCount=${totalBlueprintsCount}). Returning null to trigger empty state.`
      );
      return null;
    }

    const langCounter = new Map<string, number>();
    const cloudCounter = new Map<string, number>();
    const dbCounter = new Map<string, number>();
    const fwCounter = new Map<string, number>();
    let totalSkillMentions = 0;

    const KNOWN_LANGUAGES = new Set([
      "python", "typescript", "javascript", "go", "golang", "java", "c++", "c#", "rust", "php", "sql", "kotlin", "swift"
    ]);

    const KNOWN_CLOUDS = new Set([
      "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "cloudflare", "linux"
    ]);

    const KNOWN_DBS = new Set([
      "postgresql", "redis", "mongodb", "mysql", "kafka", "elasticsearch", "sqlite", "dynamodb", "rabbitmq"
    ]);

    const KNOWN_FWS = new Set([
      "fastapi", "react", "next.js", "django", "spring boot", "express", "vue", "tailwind css", "pytorch", "nodejs", "node.js"
    ]);

    for (const row of skillsRows) {
      const allTokens: string[] = [];
      const fields = [
        row.skill_name,
        row.skill,
        row.must_have_skills,
        row.nice_to_have_skills,
        row.frameworks,
        row.databases,
        row.cloud_infra,
        row.tools,
      ];

      for (const f of fields) {
        if (!f) continue;
        const parsed = parseTechStack(String(f));
        allTokens.push(...parsed);
      }

      const dedupeRow = new Set(allTokens.map((t) => t.trim()));
      totalSkillMentions += dedupeRow.size;

      for (const rawToken of dedupeRow) {
        const lower = rawToken.toLowerCase();
        // Canonicalize naming
        let canonical = rawToken;
        if (lower === "golang") canonical = "Go";
        else if (lower === "nodejs" || lower === "node.js") canonical = "Node.js";
        else if (lower === "postgres" || lower === "postgresql") canonical = "PostgreSQL";
        else if (lower === "k8s") canonical = "Kubernetes";

        if (KNOWN_LANGUAGES.has(lower)) {
          langCounter.set(canonical, (langCounter.get(canonical) || 0) + 1);
        }
        if (KNOWN_CLOUDS.has(lower)) {
          cloudCounter.set(canonical, (cloudCounter.get(canonical) || 0) + 1);
        }
        if (KNOWN_DBS.has(lower)) {
          dbCounter.set(canonical, (dbCounter.get(canonical) || 0) + 1);
        }
        if (KNOWN_FWS.has(lower)) {
          fwCounter.set(canonical, (fwCounter.get(canonical) || 0) + 1);
        }
      }
    }

    const toSortedItems = (counter: Map<string, number>): MarketMetricItem[] => {
      const items = Array.from(counter.entries()).map(([name, count]) => ({
        name,
        count,
        percentage:
          skillsRows.length > 0 ? Math.round((count / skillsRows.length) * 100) : 0,
      }));
      return items.sort((a, b) => b.count - a.count).slice(0, 8);
    };

    console.log(
      `[Turso] getMarketAnalytics: Aggregated metrics across ${skillsRows.length} skill records (${totalSkillMentions} total mentions across ${totalJobsCount} jobs).`
    );

    let topCompensatedSkills: CompensatedSkillItem[] = [];
    if (compRes.status === "fulfilled" && compRes.value.rows.length > 0) {
      topCompensatedSkills = compRes.value.rows
        .map((row) => ({
          skill: String(row.skill_name ?? ""),
          avg_salary: Number(row.avg_salary ?? 0),
          sample_count: Number(row.sample_count ?? 0),
        }))
        .filter((item) => item.skill && item.avg_salary > 0);
    }

    return {
      totalJobs: totalJobsCount || skillsRows.length,
      totalSkills: totalSkillMentions,
      totalBlueprints: totalBlueprintsCount,
      languages: toSortedItems(langCounter),
      clouds: toSortedItems(cloudCounter),
      databases: toSortedItems(dbCounter),
      frameworks: toSortedItems(fwCounter),
      top_compensated_skills: topCompensatedSkills,
    };
  } catch (err) {
    console.error("[Turso] Market analytics query failed:", err);
    return null;
  }
}

export const getAnalyticsData = getMarketAnalytics;

