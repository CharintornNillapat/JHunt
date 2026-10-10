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

export async function getAllProjects(): Promise<GeneratedProject[]> {
  if (!url && !clientInstance) {
    return [];
  }
  try {
    const result = await turso.execute(
      "SELECT id, title, role, difficulty, domain, tech_stack, spec_markdown, created_at FROM generated_projects ORDER BY created_at DESC"
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
