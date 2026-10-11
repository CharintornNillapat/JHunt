// web/src/app/api/skill-gap/route.ts
import { NextResponse } from "next/server";
import { calculateSkillGap } from "@/lib/turso";
import type { SkillGapRequest } from "@/lib/skill-gap-types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function POST(req: Request) {
  try {
    const body: SkillGapRequest = await req.json().catch(() => ({ userSkills: [] }));
    const rawSkills = Array.isArray(body?.userSkills) ? body.userSkills : [];
    const sanitizedSkills = rawSkills
      .map((s) => String(s).trim())
      .filter((s) => s.length > 0 && s.length <= 50)
      .slice(0, 30);

    const result = await calculateSkillGap(sanitizedSkills);
    return NextResponse.json(result);
  } catch (err) {
    console.error("[API] /api/skill-gap POST error:", err);
    return NextResponse.json(
      { error: "Internal server error calculating skill gap" },
      { status: 500 }
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

    const result = await calculateSkillGap(parsedSkills);
    return NextResponse.json(result);
  } catch (err) {
    console.error("[API] /api/skill-gap GET error:", err);
    return NextResponse.json(
      { error: "Internal server error calculating skill gap" },
      { status: 500 }
    );
  }
}
