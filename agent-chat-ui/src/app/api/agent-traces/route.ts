import { NextRequest, NextResponse } from "next/server";

import { workbenchAuthResponse } from "@/lib/api-route-auth";
import { loadAgentTraceState } from "@/lib/agent-traces";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: NextRequest) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  const searchParams = request.nextUrl.searchParams;
  return NextResponse.json(
    await loadAgentTraceState({
      limit: Number(searchParams.get("limit") || 80),
      taskId: searchParams.get("taskId") || undefined,
      threadId: searchParams.get("threadId") || undefined,
      scope: searchParams.get("scope") || "",
    }),
  );
}
