import { NextResponse } from "next/server";

import { loadLightRAGStatus } from "@/lib/lightrag-status";

export const runtime = "nodejs";

const DEFAULT_TIMEOUT_MS = 3500;

export async function GET() {
  const apiUrl = (
    process.env.LIGHTRAG_API_URL ?? "http://127.0.0.1:9621"
  ).replace(/\/$/, "");
  const timeoutMs = Number(
    process.env.LIGHTRAG_STATUS_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS,
  );
  const status = await loadLightRAGStatus({ apiUrl, timeoutMs });
  return NextResponse.json(status);
}
