import { createClient, type Client, type ResultSet } from "@libsql/client";

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

let rawUrl = process.env.TURSO_DATABASE_URL?.trim();
const authToken = process.env.TURSO_AUTH_TOKEN?.trim();

if (rawUrl?.startsWith("libsql://")) {
  rawUrl = "https://" + rawUrl.slice("libsql://".length);
}
const url = rawUrl;

export const isTursoConfigured = Boolean(url);

// Dummy client fallback during build time or when environment variables are unset
const dummyClient = {
  async execute(): Promise<ResultSet> {
    return {
      columns: [],
      rows: [],
      rowsAffected: 0,
      lastInsertRowid: undefined,
    } as unknown as ResultSet;
  },
  async batch(): Promise<ResultSet[]> {
    return [];
  },
  async transaction() {
    throw new Error("Turso client not configured");
  },
  close() {},
} as unknown as Client;

let clientInstance: Client | null = null;

if (url) {
  try {
    clientInstance = createClient({
      url,
      authToken: authToken || undefined,
    });
  } catch (error) {
    console.warn("[Turso] Failed to initialize client, using fallback:", error);
  }
}

export const turso: Client = clientInstance || dummyClient;

export function parseTechStack(raw: string): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.map((item) => String(item).trim()).filter(Boolean);
    }
  } catch {
    // fallback to comma separated
  }
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function formatDate(dateStr: string): string {

  if (!dateStr) return "Recent";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export async function getAllProjects(): Promise<GeneratedProject[]> {

  if (!url && !clientInstance) {
    return [];
  }
  try {
    const result = await turso.execute(
      "SELECT id, title, role, difficulty, domain, tech_stack, spec_markdown, created_at FROM generated_projects WHERE id IN (SELECT MAX(id) FROM generated_projects GROUP BY title) ORDER BY created_at DESC"
    );
    const seenTitles = new Set<string>();
    const deduplicated: GeneratedProject[] = [];
    for (const row of result.rows) {
      const title = String(row.title ?? "").trim();
      if (!seenTitles.has(title)) {
        seenTitles.add(title);
        deduplicated.push({
          id: Number(row.id),
          title: String(row.title ?? ""),
          role: String(row.role ?? ""),
          difficulty: String(row.difficulty ?? "Intermediate"),
          domain: String(row.domain ?? ""),
          tech_stack: String(row.tech_stack ?? ""),
          spec_markdown: String(row.spec_markdown ?? ""),
          created_at: String(row.created_at ?? ""),
        });
      }
    }
    return deduplicated;
  } catch (err) {
    console.warn("[Turso] Could not fetch projects:", err);
    return [];
  }
}

export async function getProjectById(id: string | number): Promise<GeneratedProject | null> {
  if (!url && !clientInstance) {
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
    console.warn(`[Turso] Could not fetch project ${id}:`, err);
    return null;
  }
}

export interface MarketMetricItem {
  name: string;
  count: number;
  percentage?: number;
}

export interface MarketAnalytics {
  totalJobs: number;
  totalSkills: number;
  totalBlueprints: number;
  languages: MarketMetricItem[];
  clouds: MarketMetricItem[];
  databases: MarketMetricItem[];
  frameworks: MarketMetricItem[];
  roles: MarketMetricItem[];
}

const DETERMINISTIC_FALLBACK_ANALYTICS: MarketAnalytics = {
  totalJobs: 142,
  totalSkills: 586,
  totalBlueprints: 12,
  languages: [
    { name: "Python", count: 88, percentage: 62 },
    { name: "TypeScript", count: 64, percentage: 45 },
    { name: "Go", count: 46, percentage: 32 },
    { name: "Java", count: 38, percentage: 27 },
    { name: "SQL", count: 72, percentage: 51 },
    { name: "C++", count: 18, percentage: 13 },
  ],
  clouds: [
    { name: "AWS", count: 68, percentage: 48 },
    { name: "Docker", count: 84, percentage: 59 },
    { name: "Kubernetes", count: 44, percentage: 31 },
    { name: "GCP", count: 28, percentage: 20 },
    { name: "Terraform", count: 22, percentage: 15 },
  ],
  databases: [
    { name: "PostgreSQL", count: 76, percentage: 54 },
    { name: "Redis", count: 58, percentage: 41 },
    { name: "Kafka", count: 36, percentage: 25 },
    { name: "MySQL", count: 42, percentage: 30 },
    { name: "MongoDB", count: 24, percentage: 17 },
  ],
  frameworks: [
    { name: "FastAPI", count: 62, percentage: 44 },
    { name: "React", count: 56, percentage: 39 },
    { name: "Next.js", count: 42, percentage: 30 },
    { name: "Django", count: 26, percentage: 18 },
    { name: "Spring Boot", count: 22, percentage: 15 },
  ],
  roles: [
    { name: "Backend Engineer", count: 58, percentage: 41 },
    { name: "Fullstack Engineer", count: 36, percentage: 25 },
    { name: "Data Engineer", count: 28, percentage: 20 },
    { name: "AI / ML Engineer", count: 20, percentage: 14 },
  ],
};

export async function getMarketAnalytics(): Promise<MarketAnalytics> {
  if (!url && !clientInstance) {
    return DETERMINISTIC_FALLBACK_ANALYTICS;
  }

  try {
    const [jobsRes, blueprintsRes, skillsRes] = await Promise.allSettled([
      turso.execute("SELECT COUNT(*) AS total FROM jobs"),
      turso.execute("SELECT COUNT(*) AS total FROM generated_projects"),
      turso.execute(
        "SELECT must_have_skills, nice_to_have_skills, frameworks, databases, cloud_infra, tools FROM skills_extracted"
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

    const skillsRows =
      skillsRes.status === "fulfilled" ? skillsRes.value.rows : [];

    if (skillsRows.length === 0) {
      return {
        ...DETERMINISTIC_FALLBACK_ANALYTICS,
        totalJobs: totalJobsCount || DETERMINISTIC_FALLBACK_ANALYTICS.totalJobs,
        totalBlueprints:
          totalBlueprintsCount || DETERMINISTIC_FALLBACK_ANALYTICS.totalBlueprints,
      };
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

    return {
      totalJobs: totalJobsCount || skillsRows.length,
      totalSkills: totalSkillMentions,
      totalBlueprints: totalBlueprintsCount || DETERMINISTIC_FALLBACK_ANALYTICS.totalBlueprints,
      languages: toSortedItems(langCounter).length ? toSortedItems(langCounter) : DETERMINISTIC_FALLBACK_ANALYTICS.languages,
      clouds: toSortedItems(cloudCounter).length ? toSortedItems(cloudCounter) : DETERMINISTIC_FALLBACK_ANALYTICS.clouds,
      databases: toSortedItems(dbCounter).length ? toSortedItems(dbCounter) : DETERMINISTIC_FALLBACK_ANALYTICS.databases,
      frameworks: toSortedItems(fwCounter).length ? toSortedItems(fwCounter) : DETERMINISTIC_FALLBACK_ANALYTICS.frameworks,
      roles: DETERMINISTIC_FALLBACK_ANALYTICS.roles,
    };
  } catch (err) {
    console.warn("[Turso] Market analytics query failed, using deterministic fallback:", err);
    return DETERMINISTIC_FALLBACK_ANALYTICS;
  }
}

