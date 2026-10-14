// web/src/app/api/skill-gap/route.ts
import { NextResponse } from "next/server";
import { calculateSkillGap } from "@/lib/turso";
import type { SkillGapRequest, SkillGapResponse } from "@/lib/skill-gap-types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

interface CacheEntry {
  data: SkillGapResponse;
  expiresAt: number;
}

const RESPONSE_CACHE_TTL_MS = 10 * 60 * 1000;
const MAX_CACHE_ENTRIES = 200;
const responseCache = new Map<string, CacheEntry>();

export function clearSkillGapResponseCache(): void {
  responseCache.clear();
  console.log("[API] /api/skill-gap response cache cleared.");
}

function getFromCache(key: string, now: number): SkillGapResponse | null {
  const cached = responseCache.get(key);
  if (!cached) return null;
  if (now >= cached.expiresAt) {
    responseCache.delete(key);
    return null;
  }
  // Refresh LRU recency: re-insert at end of Map
  responseCache.delete(key);
  responseCache.set(key, cached);
  return cached.data;
}

function setInCache(key: string, data: SkillGapResponse, now: number): void {
  if (responseCache.has(key)) {
    responseCache.delete(key);
  } else if (responseCache.size >= MAX_CACHE_ENTRIES) {
    // Evict least recently used (first key in Map iterator)
    const oldestKey = responseCache.keys().next().value;
    if (oldestKey !== undefined) {
      responseCache.delete(oldestKey);
    }
  }
  responseCache.set(key, {
    data,
    expiresAt: now + RESPONSE_CACHE_TTL_MS,
  });
}

function makeCacheKey(skills: string[]): string {
  return skills
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
    .sort()
    .join(",");
}

export async function POST(req: Request) {
  try {
    const body: SkillGapRequest = await req.json().catch(() => ({ userSkills: [] }));
    const rawSkills = Array.isArray(body?.userSkills) ? body.userSkills : [];
    const sanitizedSkills = rawSkills
      .map((s) => String(s).trim())
      .filter((s) => s.length > 0 && s.length <= 50)
      .slice(0, 30);

    const cacheKey = makeCacheKey(sanitizedSkills);
    const now = Date.now();
    const cachedData = getFromCache(cacheKey, now);

    if (cachedData) {
      return NextResponse.json(cachedData);
    }

    const result = await calculateSkillGap(sanitizedSkills);
    setInCache(cacheKey, result, now);

    return NextResponse.json(result);
  } catch (err) {
    console.error("[API] /api/skill-gap POST error:", err);
    return NextResponse.json(
      { error: "Service temporarily unavailable" },
      { status: 503 }
    );
  }
}

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const rawParam = searchParams.get("skills") ?? "";
    const parsedSkills = rawParam
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 30);

    const cacheKey = makeCacheKey(parsedSkills);
    const now = Date.now();
    const cachedData = getFromCache(cacheKey, now);

    if (cachedData) {
      return NextResponse.json(cachedData);
    }

    const result = await calculateSkillGap(parsedSkills);
    setInCache(cacheKey, result, now);

    return NextResponse.json(result);
  } catch (err) {
    console.error("[API] /api/skill-gap GET error:", err);
    return NextResponse.json(
      { error: "Service temporarily unavailable" },
      { status: 503 }
    );
  }
}
