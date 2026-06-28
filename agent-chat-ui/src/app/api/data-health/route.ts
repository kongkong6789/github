import { NextResponse } from "next/server";

import { workbenchAuthResponse } from "@/lib/api-route-auth";
import { loadDataHealthState } from "@/lib/data-health-state";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  return NextResponse.json(await loadDataHealthState());
}
