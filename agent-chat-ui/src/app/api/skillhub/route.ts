import { NextResponse } from "next/server";

import { checkWorkbenchAuth } from "@/lib/api-auth";
import { workbenchAuthResponse } from "@/lib/api-route-auth";
import {
  checkSkillhubStatus,
  installSkillhubSkill,
  listSkillhubCatalog,
  searchSkillhubSkills,
} from "@/lib/skillhub";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeNumber(value: unknown, fallback = 20) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function errorResponse(error: unknown, status = 400) {
  return NextResponse.json(
    {
      status: "error",
      error: error instanceof Error ? error.message : String(error),
    },
    { status },
  );
}

async function availableSkillhubCommand() {
  const cli = await checkSkillhubStatus();
  if (!cli.available) {
    throw new Error(`SkillHub CLI 不可用。请先执行：${cli.install_command}`);
  }
  return cli.command;
}

export async function GET(request: Request) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  const url = new URL(request.url);
  const query = safeText(url.searchParams.get("q"));
  const mode = safeText(url.searchParams.get("mode"));
  const wantsCatalog =
    mode === "catalog" ||
    url.searchParams.has("category") ||
    url.searchParams.has("source") ||
    url.searchParams.has("sort");

  try {
    if (wantsCatalog) {
      return NextResponse.json(
        await listSkillhubCatalog({
          query,
          category: safeText(url.searchParams.get("category")) || "all",
          source: safeText(url.searchParams.get("source")) || "all",
          sort: safeText(url.searchParams.get("sort")) || "score",
          limit: safeNumber(url.searchParams.get("limit"), 50),
        }),
      );
    }
    if (!query) return NextResponse.json(await checkSkillhubStatus());
    const command = await availableSkillhubCommand();
    return NextResponse.json(
      await searchSkillhubSkills({
        query,
        command,
        limit: safeNumber(url.searchParams.get("limit")),
      }),
    );
  } catch (error) {
    if (!query) {
      return NextResponse.json({
        status: "unavailable",
        available: false,
        command: "skillhub",
        workspace_dir: "",
        skill_library_dir: "",
        install_command: "请手动安装 SkillHub CLI（远程自动安装已禁用）",
        help: "",
        version: "",
        error: error instanceof Error ? error.message : String(error),
      });
    }
    return errorResponse(error);
  }
}

export async function POST(request: Request) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      { status: "error", error: auth.error },
      { status: auth.status },
    );
  }

  const body = safeRecord(await request.json().catch(() => ({})));
  const action = safeText(body.action);

  try {
    if (action === "catalog") {
      return NextResponse.json(
        await listSkillhubCatalog({
          query: safeText(body.query),
          category: safeText(body.category) || "all",
          source: safeText(body.source) || "all",
          sort: safeText(body.sort) || "score",
          limit: safeNumber(body.limit, 50),
        }),
      );
    }
    const command = await availableSkillhubCommand();
    if (action === "search") {
      return NextResponse.json(
        await listSkillhubCatalog({
          query: safeText(body.query),
          category: safeText(body.category) || "all",
          source: safeText(body.source) || "all",
          sort: safeText(body.sort) || "score",
          limit: safeNumber(body.limit, 50),
        }),
      );
    }
    if (action === "install_skill") {
      return NextResponse.json(
        await installSkillhubSkill({
          slug: safeText(body.slug),
          command,
          force: body.force !== false,
        }),
      );
    }
    return errorResponse(`不支持的 SkillHub 操作：${action || "空"}`);
  } catch (error) {
    return errorResponse(error);
  }
}
