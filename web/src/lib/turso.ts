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
    const [jobsRes, blueprintsRes, skillStatsRes] = await Promise.allSettled([
      turso.execute("SELECT COUNT(*) AS total FROM jobs"),
      turso.execute("SELECT COUNT(DISTINCT title) AS total FROM generated_projects"),
      turso.execute(
        "SELECT skill, category, job_count, salary_count, avg_salary_thb FROM skill_stats ORDER BY job_count DESC"
      ),
    ]);

    const totalJobsCount =
      jobsRes.status === "fulfilled" && jobsRes.value.rows[0]?.total
        ? Number(jobsRes.value.rows[0].total)
        : 0;

    const totalBlueprintsCount =
      blueprintsRes.status === "fulfilled" && blueprintsRes.value.rows[0]?.total
        ? Number(blueprintsRes.value.rows[0].total)
        : 0;

    // Fast path: If pre-aggregated skill_stats has data, serve directly without scanning raw skills
    if (skillStatsRes.status === "fulfilled" && skillStatsRes.value.rows.length > 0) {
      const statsRows = skillStatsRes.value.rows;
      let totalSkillMentions = 0;
      for (const r of statsRows) {
        totalSkillMentions += Number(r.job_count ?? 0);
      }

      const partitionCategory = (cat: string): MarketMetricItem[] => {
        return statsRows
          .filter((r) => r.category === cat)
          .map((r) => ({
            name: String(r.skill ?? ""),
            count: Number(r.job_count ?? 0),
            percentage:
              totalJobsCount > 0 ? Math.round((Number(r.job_count ?? 0) / totalJobsCount) * 100) : 0,
          }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 8);
      };

      const topCompensatedSkills: CompensatedSkillItem[] = statsRows
        .filter((r) => Number(r.salary_count ?? 0) >= 5 && Number(r.avg_salary_thb ?? 0) > 0)
        .map((r) => ({
          skill: String(r.skill ?? ""),
          avg_salary: Number(r.avg_salary_thb ?? 0),
          sample_count: Number(r.salary_count ?? 0),
        }))
        .sort((a, b) => b.avg_salary - a.avg_salary)
        .slice(0, 10);

      console.log(
        `[Turso] getMarketAnalytics: Loaded pre-aggregated skill_stats with ${statsRows.length} skills (${totalSkillMentions} total mentions across ${totalJobsCount} jobs).`
      );

      return {
        totalJobs: totalJobsCount,
        totalSkills: totalSkillMentions,
        totalBlueprints: totalBlueprintsCount,
        languages: partitionCategory("language"),
        clouds: partitionCategory("cloud"),
        databases: partitionCategory("database"),
        frameworks: partitionCategory("framework"),
        top_compensated_skills: topCompensatedSkills,
      };
    }

    // Fallback path: Query raw skills_extracted table if skill_stats is not populated
    console.warn("[Turso] getMarketAnalytics: skill_stats is empty or unavailable; falling back to raw skills_extracted scan.");
    const [skillsRes, compRes] = await Promise.allSettled([
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
          AND j.currency = 'THB'
          AND s.skill_name IS NOT NULL
          AND (s.experience_level IS NULL OR s.experience_level != 'Non-Tech')
        GROUP BY s.skill_name
        HAVING sample_count >= 5
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

export * from "./skill-gap-types";
import type {
  SkillGapResponse,
  RecommendedSkill,
  MatchedBlueprint,
} from "./skill-gap-types";

export function canonicalizeSkill(raw: string): { canonical: string; lower: string } {
  const trimmed = raw.trim();
  const lower = trimmed.toLowerCase();

  if (lower === "golang" || lower === "go") return { canonical: "Go", lower: "go" };
  if (lower === "nodejs" || lower === "node.js" || lower === "node") return { canonical: "Node.js", lower: "node.js" };
  if (lower === "postgres" || lower === "postgresql" || lower.startsWith("postgres ") || lower.startsWith("postgresql ") || /^postgresql?\s*\d+/i.test(lower)) return { canonical: "PostgreSQL", lower: "postgresql" };
  if (lower === "k8s" || lower === "kubernetes") return { canonical: "Kubernetes", lower: "kubernetes" };
  if (lower === "ts" || lower === "typescript") return { canonical: "TypeScript", lower: "typescript" };
  if (lower === "js" || lower === "javascript") return { canonical: "JavaScript", lower: "javascript" };
  if (lower === "py" || lower === "python" || lower === "python3" || lower.startsWith("python ") || /^python\s*\d+/i.test(lower)) return { canonical: "Python", lower: "python" };
  if (lower === "react" || lower === "react.js" || lower === "reactjs") return { canonical: "React", lower: "react" };
  if (lower === "nextjs" || lower === "next.js") return { canonical: "Next.js", lower: "next.js" };
  if (lower === "vue" || lower === "vue.js" || lower === "vuejs") return { canonical: "Vue.js", lower: "vue.js" };
  if (lower === "fastapi" || lower === "fast api") return { canonical: "FastAPI", lower: "fastapi" };
  if (lower === "aws" || lower === "amazon web services") return { canonical: "AWS", lower: "aws" };
  if (lower === "gcp" || lower === "google cloud" || lower === "google cloud platform") return { canonical: "GCP", lower: "gcp" };
  if (lower === "docker") return { canonical: "Docker", lower: "docker" };
  if (lower === "sql") return { canonical: "SQL", lower: "sql" };
  if (lower === "mongodb" || lower === "mongo") return { canonical: "MongoDB", lower: "mongodb" };
  if (lower === "tailwind" || lower === "tailwindcss" || lower === "tailwind css") return { canonical: "Tailwind CSS", lower: "tailwind css" };

  const stripped = trimmed.replace(/\s+v?\d+(?:\.\d+)*$/i, "").trim();
  let canonical = stripped || trimmed;
  if (/^[a-z0-9\s\.\-#+]+$/i.test(canonical) && canonical.length > 1) {
    canonical = canonical.charAt(0).toUpperCase() + canonical.slice(1);
  }
  return { canonical, lower: canonical.toLowerCase() };
}

export interface SkillGapBaseData {
  jobSkillsMap: Map<string, Set<string>>;
  canonicalMap: Map<string, string>;
  overallFrequency: Map<string, number>;
  salaryMap: Map<string, { avgSalary: number; sampleCount: number }>;
  allProjects: GeneratedProject[];
  timestamp: number;
}

const SKILL_GAP_CACHE_TTL_MS = 10 * 60 * 1000;
let cachedBaseData: SkillGapBaseData | null = null;
let baseDataPromise: Promise<SkillGapBaseData> | null = null;

export function clearSkillGapCache(): void {
  cachedBaseData = null;
  baseDataPromise = null;
  console.log("[Turso] In-memory skill-gap cache cleared.");
}

export async function getSkillGapBaseData(): Promise<SkillGapBaseData> {
  const now = Date.now();
  if (cachedBaseData && now - cachedBaseData.timestamp < SKILL_GAP_CACHE_TTL_MS) {
    return cachedBaseData;
  }

  if (baseDataPromise) {
    return baseDataPromise;
  }

  baseDataPromise = (async () => {
    try {
      if (!turso) {
        return {
          jobSkillsMap: new Map(),
          canonicalMap: new Map(),
          overallFrequency: new Map(),
          salaryMap: new Map(),
          allProjects: [],
          timestamp: Date.now(),
        };
      }

      const [skillsRes, blueprintsRes, compRes] = await Promise.allSettled([
        turso.execute(
          "SELECT job_id, skill_name, skill, must_have_skills, nice_to_have_skills, frameworks, databases, cloud_infra, tools FROM skills_extracted WHERE (experience_level IS NULL OR experience_level != 'Non-Tech')"
        ),
        getAllProjects(),
        turso.execute(`
          SELECT 
            s.skill_name,
            COUNT(DISTINCT j.id) as sample_count,
            ROUND(AVG((j.min_salary + j.max_salary) / 2)) as avg_salary
          FROM skills_extracted s
          JOIN jobs j ON s.job_id = j.id
          WHERE j.min_salary IS NOT NULL 
            AND j.max_salary IS NOT NULL 
            AND j.currency = 'THB'
            AND s.skill_name IS NOT NULL
          GROUP BY s.skill_name
          HAVING sample_count >= 5
        `),
      ]);

      let skillsRows = skillsRes.status === "fulfilled" ? skillsRes.value.rows : [];
      if (skillsRes.status === "rejected" || skillsRows.length === 0) {
        try {
          const fallbackRes = await turso.execute("SELECT * FROM skills_extracted");
          skillsRows = fallbackRes.rows;
        } catch (err) {
          console.error("[Turso] getSkillGapBaseData: Fallback skills query failed:", err);
        }
      }

      const allProjects = blueprintsRes.status === "fulfilled" ? blueprintsRes.value : [];
      const salaryMap = new Map<string, { avgSalary: number; sampleCount: number }>();
      if (compRes.status === "fulfilled") {
        for (const row of compRes.value.rows) {
          if (row.skill_name && row.avg_salary) {
            const { lower } = canonicalizeSkill(String(row.skill_name));
            salaryMap.set(lower, {
              avgSalary: Number(row.avg_salary),
              sampleCount: Number(row.sample_count ?? 0),
            });
          }
        }
      }

      const jobSkillsMap = new Map<string, Set<string>>();
      const canonicalMap = new Map<string, string>();
      const overallFrequency = new Map<string, number>();

      for (const row of skillsRows) {
        const jobId = String(row.job_id ?? row.id ?? "");
        if (!jobId) continue;

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

        const jobSkillSet = jobSkillsMap.get(jobId) ?? new Set<string>();

        for (const f of fields) {
          if (!f) continue;
          const tokens = parseTechStack(String(f));
          for (const tok of tokens) {
            const { canonical, lower } = canonicalizeSkill(tok);
            if (!lower) continue;
            if (!jobSkillSet.has(lower)) {
              jobSkillSet.add(lower);
              canonicalMap.set(lower, canonical);
              overallFrequency.set(lower, (overallFrequency.get(lower) || 0) + 1);
            }
          }
        }

        if (jobSkillSet.size > 0) {
          jobSkillsMap.set(jobId, jobSkillSet);
        }
      }

      const baseData: SkillGapBaseData = {
        jobSkillsMap,
        canonicalMap,
        overallFrequency,
        salaryMap,
        allProjects,
        timestamp: Date.now(),
      };

      cachedBaseData = baseData;
      return baseData;
    } catch (err) {
      if (cachedBaseData) {
        console.warn("[Turso] getSkillGapBaseData query failed, serving stale cache:", err);
        return cachedBaseData;
      }
      throw err;
    } finally {
      baseDataPromise = null;
    }
  })();

  return baseDataPromise;
}

export async function calculateSkillGap(userSkills: string[] = []): Promise<SkillGapResponse> {
  const fallbackSuggestions = [
    "Python", "TypeScript", "React", "Docker", "PostgreSQL", "FastAPI",
    "AWS", "Go", "Kubernetes", "Next.js", "Redis", "Node.js"
  ];

  if (!turso) {
    return {
      userSkills,
      totalTechJobs: 0,
      matchedJobsCount: 0,
      coverageRate: 0,
      recommendedSkills: [],
      relevantBlueprints: [],
      popularSuggestions: fallbackSuggestions,
    };
  }

  const { jobSkillsMap, canonicalMap, overallFrequency, salaryMap, allProjects } =
    await getSkillGapBaseData();

  const totalTechJobs = Math.max(jobSkillsMap.size, 1);

    const userLowerSet = new Set(
      userSkills
        .map((s) => canonicalizeSkill(s).lower)
        .filter(Boolean)
    );

    const matchedJobIds = new Set<string>();
    if (userLowerSet.size > 0) {
      for (const [jobId, skills] of jobSkillsMap.entries()) {
        for (const s of skills) {
          if (userLowerSet.has(s)) {
            matchedJobIds.add(jobId);
            break;
          }
        }
      }
    }

    const matchedJobsCount = matchedJobIds.size;
    const coverageRate = userLowerSet.size > 0
      ? Math.round((matchedJobsCount / totalTechJobs) * 100)
      : 0;

    // Calculate companion synergies and unlock potential
    const companionStats = new Map<string, { lower: string; coOccurCount: number; unlockCount: number }>();

    for (const [jobId, skills] of jobSkillsMap.entries()) {
      const isJobMatched = matchedJobIds.has(jobId);

      for (const skill of skills) {
        if (userLowerSet.has(skill)) continue;

        let stat = companionStats.get(skill);
        if (!stat) {
          stat = { lower: skill, coOccurCount: 0, unlockCount: 0 };
          companionStats.set(skill, stat);
        }

        if (isJobMatched) {
          stat.coOccurCount += 1;
        } else {
          stat.unlockCount += 1;
        }
      }
    }

    const rankedCandidates = Array.from(companionStats.values())
      .map((c) => {
        const score = matchedJobsCount > 0
          ? c.unlockCount * 2.0 + c.coOccurCount * 1.5
          : c.unlockCount * 2.0;
        return { ...c, score };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 6);

    const recommendedSkills: RecommendedSkill[] = rankedCandidates.map((c) => {
      const coOccurRate = matchedJobsCount > 0
        ? Math.round((c.coOccurCount / matchedJobsCount) * 100)
        : 0;
      const unlockPct = totalTechJobs > 0
        ? Math.round((c.unlockCount / totalTechJobs) * 100)
        : 0;

      const salaryInfo = salaryMap.get(c.lower);

      return {
        name: canonicalMap.get(c.lower) || c.lower,
        coOccurrenceCount: c.coOccurCount,
        coOccurrenceRate: coOccurRate,
        unlockJobsCount: c.unlockCount,
        unlockPercentage: unlockPct,
        avgSalary: salaryInfo?.avgSalary,
        salarySampleCount: salaryInfo?.sampleCount,
      };
    });

    // Score & match generated blueprints
    const scoredBlueprints: MatchedBlueprint[] = allProjects.map((p) => {
      const stack = parseTechStack(p.tech_stack);
      const matchedSkills: string[] = [];
      const missingSkills: string[] = [];

      for (const s of stack) {
        const { canonical, lower } = canonicalizeSkill(s);
        if (userLowerSet.has(lower)) {
          matchedSkills.push(canonical);
        } else {
          missingSkills.push(canonical);
        }
      }

      const matchPercentage = stack.length > 0
        ? Math.round((matchedSkills.length / stack.length) * 100)
        : 0;

      return {
        id: p.id,
        title: p.title,
        role: p.role,
        difficulty: p.difficulty,
        domain: p.domain,
        techStack: stack,
        matchedSkills,
        missingSkills,
        matchPercentage,
      };
    });

    scoredBlueprints.sort((a, b) => {
      if (b.matchPercentage !== a.matchPercentage) {
        return b.matchPercentage - a.matchPercentage;
      }
      return b.id - a.id;
    });

    const relevantBlueprints = scoredBlueprints.slice(0, 3);

    const popularSuggestions = Array.from(overallFrequency.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 16)
      .map(([lower]) => canonicalMap.get(lower) || lower);

    return {
      userSkills,
      totalTechJobs,
      matchedJobsCount,
      coverageRate,
      recommendedSkills,
      relevantBlueprints,
      popularSuggestions: popularSuggestions.length > 0 ? popularSuggestions : fallbackSuggestions,
    };
}

