import { NextRequest, NextResponse } from "next/server";

import { workbenchAuthResponse } from "@/lib/api-route-auth";
import { loadEvidenceGraphState } from "@/lib/evidence-graph";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

function listParam(value: string | null) {
  return value
    ? value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
    : [];
}

export async function GET(request: NextRequest) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  try {
    const params = request.nextUrl.searchParams;
    const graph = await loadEvidenceGraphState({
      scope: params.get("scope") || "global",
      taskId: params.get("taskId") || params.get("task_id") || "",
      reportPath: params.get("reportPath") || params.get("report_path") || "",
      nodeTypes: listParam(params.get("nodeTypes") || params.get("node_types")),
      edgeTypes: listParam(params.get("edgeTypes") || params.get("edge_types")),
      limit: Number(params.get("limit") || 300),
    });
    return NextResponse.json(graph);
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 400 },
    );
  }
}
