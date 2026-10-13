import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";

export async function POST(request: NextRequest) {
  const secret = process.env.REVALIDATE_TOKEN;
  if (!secret) {
    return NextResponse.json(
      { message: "Server misconfiguration" },
      { status: 500 }
    );
  }

  const token = request.headers.get("x-revalidate-token");
  if (!token || token !== secret) {
    return NextResponse.json(
      { message: "Unauthorized" },
      { status: 401 }
    );
  }

  try {
    revalidatePath("/");
    revalidatePath("/analytics");

    return NextResponse.json({
      revalidated: true,
      paths: ["/", "/analytics"],
      now: Date.now(),
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { message: "Failed to revalidate paths", error: errorMsg },
      { status: 500 }
    );
  }
}
