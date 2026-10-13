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
const responseCache = new Map<string, CacheEntry>();

export function clearSkillGapResponseCache(): void {
  responseCache.clear();
  console.log("[API] /api/skill-gap response cache cleared.");
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
    const cached = responseCache.get(cacheKey);
    const now = Date.now();

    if (cached && now < cached.expiresAt) {
      return NextResponse.json(cached.data);
    }

    const result = await calculateSkillGap(sanitizedSkills);
    responseCache.set(cacheKey, {
      data: result,
      expiresAt: now + RESPONSE_CACHE_TTL_MS,
    });

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
    const cached = responseCache.get(cacheKey);
    const now = Date.now();

    if (cached && now < cached.expiresAt) {
      return NextResponse.json(cached.data);
    }

    const result = await calculateSkillGap(parsedSkills);
    responseCache.set(cacheKey, {
      data: result,
      expiresAt: now + RESPONSE_CACHE_TTL_MS,
    });

    return NextResponse.json(result);
  } catch (err) {
    console.error("[API] /api/skill-gap GET error:", err);
    return NextResponse.json(
      { error: "Service temporarily unavailable" },
      { status: 503 }
    );
  }
}
