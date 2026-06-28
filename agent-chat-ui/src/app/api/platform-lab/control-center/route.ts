import { NextResponse } from "next/server";
import path from "node:path";

import { workbenchAuthResponse } from "@/lib/api-route-auth";
import { loadDataHealthState } from "@/lib/data-health-state";
import { loadDataSourcesState } from "@/lib/data-sources";
import {
  loadGovernanceState,
  resolveGovernancePaths,
} from "@/lib/governance";
import { buildPlatformControlCenter } from "@/lib/platform-lab";
import { listPlatformLabRuns } from "@/lib/platform-lab-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

const DATA_DIR = process.env.A2A_DATA_DIR
  ? path.resolve(process.env.A2A_DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");
const RUN_LOG = process.env.A2A_PLATFORM_LAB_RUN_LOG
  ? path.resolve(process.env.A2A_PLATFORM_LAB_RUN_LOG)
  : path.join(DATA_DIR, "platform_lab", "runs.jsonl");

export async function GET(request: Request) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  const [dataHealth, governance, sources, runs] = await Promise.all([
    loadDataHealthState(),
    loadGovernanceState(resolveGovernancePaths()),
    loadDataSourcesState(),
    listPlatformLabRuns({ runLogPath: RUN_LOG }),
  ]);

  return NextResponse.json(
    buildPlatformControlCenter({
      dataHealth: {
        counts: {
          datasets: dataHealth.registry.dataset_count,
          warnings: dataHealth.warnings.length,
        },
        warnings: dataHealth.warnings,
      },
      governance: {
        skill_count: governance.skills.skill_count,
        mcp_policy_count: governance.mcp.tool_count,
        high_risk_count:
          governance.mcp.high_risk_count +
          governance.tool_registry.high_risk_count,
      },
      sources: {
        active_sources: sources.counts.active_sources,
        stale_sources: sources.counts.stale_sources,
        failed_sources: sources.counts.failed_sources,
      },
      runs: runs.counts,
    }),
  );
}
