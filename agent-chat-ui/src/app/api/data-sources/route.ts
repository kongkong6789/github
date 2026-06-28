import { NextRequest, NextResponse } from "next/server";

import { checkWorkbenchAuth } from "@/lib/api-auth";
import {
  loadDataSourcesState,
  rebindDataSourcePath,
  registerDataSource,
  setDataSourceStatus,
  syncDataSourceNow,
  type RegisterSourceInput,
} from "@/lib/data-sources";
import { workbenchAuthResponse } from "@/lib/api-route-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function textArray(value: unknown) {
  if (Array.isArray(value)) return value.map(safeText).filter(Boolean);
  const text = safeText(value);
  return text ? [text] : [];
}

function toRegisterInput(value: unknown): RegisterSourceInput {
  const record = safeRecord(value);
  return {
    source_id: safeText(record.source_id) || safeText(record.sourceId),
    display_name: safeText(record.display_name) || safeText(record.displayName),
    source_type: safeText(record.source_type) || safeText(record.sourceType),
    uri: safeText(record.uri),
    allowed_root: safeText(record.allowed_root) || safeText(record.allowedRoot),
    sync_mode:
      safeText(record.sync_mode) || safeText(record.syncMode) || "on_demand",
    owner: safeText(record.owner),
    sensitivity_level:
      safeText(record.sensitivity_level) ||
      safeText(record.sensitivityLevel) ||
      "internal",
    freshness_sla:
      safeText(record.freshness_sla) || safeText(record.freshnessSla),
    status: safeText(record.status) || "active",
    credential_env_keys: textArray(
      record.credential_env_keys ?? record.credentialEnvKeys,
    ),
    metadata: safeRecord(record.metadata),
  };
}

export async function GET(request: NextRequest) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  return NextResponse.json(await loadDataSourcesState());
}

export async function POST(request: NextRequest) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      { ok: false, error: auth.error },
      { status: auth.status },
    );
  }

  const body = safeRecord(await request.json().catch(() => ({})));
  const action = safeText(body.action);

  try {
    if (action === "sync") {
      const sourceId = safeText(body.source_id) || safeText(body.sourceId);
      if (!sourceId) {
        return NextResponse.json(
          { ok: false, error: "缺少 source_id" },
          { status: 400 },
        );
      }
      const result = await syncDataSourceNow({
        sourceId,
        requestedBy: "frontend",
      });
      return NextResponse.json({
        ok: result.status !== "failed",
        result,
        state: await loadDataSourcesState(),
      });
    }

    if (action === "register") {
      const input = toRegisterInput(body.source ?? body);
      if (!input.source_id || !input.display_name || !input.source_type) {
        return NextResponse.json(
          {
            ok: false,
            error: "缺少 source_id、display_name 或 source_type",
          },
          { status: 400 },
        );
      }
      const result = await registerDataSource({ input });
      return NextResponse.json({
        ok: safeText(result.status) !== "error",
        result,
        state: await loadDataSourcesState(),
      });
    }

    if (action === "status") {
      const sourceId = safeText(body.source_id) || safeText(body.sourceId);
      const status = safeText(body.status);
      if (!sourceId || !status) {
        return NextResponse.json(
          { ok: false, error: "缺少 source_id 或 status" },
          { status: 400 },
        );
      }
      const result = await setDataSourceStatus({ sourceId, status });
      return NextResponse.json({
        ok: safeText(result.status) !== "error",
        result,
        state: await loadDataSourcesState(),
      });
    }

    if (action === "rebind") {
      const sourceId = safeText(body.source_id) || safeText(body.sourceId);
      const uri = safeText(body.uri);
      const allowedRoot =
        safeText(body.allowed_root) || safeText(body.allowedRoot);
      if (!sourceId || !uri) {
        return NextResponse.json(
          { ok: false, error: "缺少 source_id 或 uri" },
          { status: 400 },
        );
      }
      const result = await rebindDataSourcePath({
        sourceId,
        uri,
        allowedRoot,
        metadata: safeRecord(body.metadata),
      });
      return NextResponse.json({
        ok: safeText(result.status) !== "error",
        result,
        state: await loadDataSourcesState(),
      });
    }

    return NextResponse.json(
      { ok: false, error: "不支持的资料来源操作" },
      { status: 400 },
    );
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error:
          error instanceof Error ? error.message : "资料来源操作失败",
      },
      { status: 500 },
    );
  }
}
