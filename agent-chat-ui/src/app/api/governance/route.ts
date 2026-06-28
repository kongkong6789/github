import { randomUUID } from "node:crypto";
import { mkdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import { NextResponse } from "next/server";

import { checkWorkbenchAuth } from "@/lib/api-auth";
import { workbenchAuthResponse } from "@/lib/api-route-auth";
import {
  createDraftSkillFromSource,
  deleteSkillRegistration,
  loadGovernanceState,
  resolveGovernancePaths,
  restoreSkillSourceFromManagedCopy,
  rollbackSkillVersion,
  setSkillStatus,
  upsertMcpToolPolicy,
  type GovernancePaths,
} from "@/lib/governance";

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

function safeBoolean(value: unknown): boolean {
  return value === true || value === "true";
}

function safeNumber(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function asTextArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(safeText).filter(Boolean);
  }
  return safeText(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
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

const MAX_SKILL_UPLOAD_FILES = 500;
const MAX_SKILL_UPLOAD_BYTES = 50 * 1024 * 1024;

function safeUploadRelativeParts(fileName: string) {
  const normalized = fileName.replace(/\\/g, "/");
  const parts = normalized
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length === 0) throw new Error("上传文件缺少文件名");
  if (
    parts.some(
      (part) =>
        part === "." ||
        part === ".." ||
        part.includes("\0") ||
        path.isAbsolute(part),
    )
  ) {
    throw new Error(`上传文件路径不安全：${fileName}`);
  }
  return parts;
}

async function directoryHasSkillFile(directoryPath: string) {
  try {
    return (await stat(path.join(directoryPath, "SKILL.md"))).isFile();
  } catch {
    return false;
  }
}

async function resolveUploadedSkillRoot(
  tempRoot: string,
  relativeParts: string[][],
) {
  const topLevels = Array.from(new Set(relativeParts.map((parts) => parts[0])));
  if (
    topLevels.length === 1 &&
    relativeParts.some((parts) => parts.length > 1)
  ) {
    const nestedRoot = path.join(tempRoot, topLevels[0]);
    if (await directoryHasSkillFile(nestedRoot)) return nestedRoot;
  }
  return tempRoot;
}

async function handleSkillFolderUpload(
  request: Request,
  paths: GovernancePaths,
) {
  const formData = await request.formData();
  const action = safeText(formData.get("action"));
  if (action !== "import_skill") {
    return errorResponse(`不支持的治理操作：${action || "空"}`);
  }

  const files = formData
    .getAll("skillFiles")
    .filter((value): value is File => value instanceof File);
  const uploadedPaths = formData.getAll("skillFilePaths").map(safeText);
  if (files.length === 0)
    throw new Error("请选择一个包含 SKILL.md 的技能文件夹");
  if (files.length > MAX_SKILL_UPLOAD_FILES) {
    throw new Error(`技能文件夹文件过多：${files.length}`);
  }

  const tempRoot = path.join(paths.skillRegistryDir, "uploads", randomUUID());
  const relativeParts: string[][] = [];
  let totalBytes = 0;
  try {
    for (const [index, file] of files.entries()) {
      totalBytes += file.size;
      if (totalBytes > MAX_SKILL_UPLOAD_BYTES) {
        throw new Error("技能文件夹上传大小超过 50 MB");
      }
      const parts = safeUploadRelativeParts(uploadedPaths[index] || file.name);
      relativeParts.push(parts);
      const targetPath = path.join(tempRoot, ...parts);
      await mkdir(path.dirname(targetPath), { recursive: true });
      await writeFile(targetPath, new Uint8Array(await file.arrayBuffer()));
    }

    const uploadedSkillRoot = await resolveUploadedSkillRoot(
      tempRoot,
      relativeParts,
    );
    const result = await createDraftSkillFromSource({
      sourcePath: uploadedSkillRoot,
      workspaceDir: paths.workspaceDir,
      wikiDir: paths.wikiDir,
      skillRegistryDir: paths.skillRegistryDir,
      templateDir: paths.templateDir,
      skillId: safeText(formData.get("skillId")),
      name: safeText(formData.get("name")),
      scenarios: asTextArray(formData.get("scenarios")),
      toolAllowlist: asTextArray(formData.get("toolAllowlist")),
      outputSchema: asTextArray(formData.get("outputSchema")),
      createdBy: safeText(formData.get("createdBy")) || "frontend",
    });
    return NextResponse.json(result);
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }
}

export async function GET(request: Request) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  try {
    return NextResponse.json(await loadGovernanceState());
  } catch (error) {
    return errorResponse(error, 500);
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

  const paths = resolveGovernancePaths();

  try {
    if (
      request.headers
        .get("content-type")
        ?.toLowerCase()
        .includes("multipart/form-data")
    ) {
      return await handleSkillFolderUpload(request, paths);
    }

    const body = safeRecord(await request.json().catch(() => ({})));
    const action = safeText(body.action);

    if (action === "import_skill") {
      const result = await createDraftSkillFromSource({
        sourcePath: safeText(body.sourcePath),
        workspaceDir: paths.workspaceDir,
        wikiDir: paths.wikiDir,
        skillRegistryDir: paths.skillRegistryDir,
        templateDir: paths.templateDir,
        skillId: safeText(body.skillId),
        name: safeText(body.name),
        scenarios: asTextArray(body.scenarios),
        toolAllowlist: asTextArray(body.toolAllowlist),
        outputSchema: asTextArray(body.outputSchema),
        createdBy: safeText(body.createdBy) || "frontend",
      });
      return NextResponse.json(result);
    }

    if (action === "upsert_mcp_policy") {
      const result = await upsertMcpToolPolicy({
        policyPath: paths.mcpPolicyPath,
        auditPath: paths.auditPath,
        toolName: safeText(body.toolName),
        description: safeText(body.description),
        action: safeText(body.toolAction),
        readOnly: safeBoolean(body.readOnly),
        requiresHumanConfirmation: safeBoolean(body.requiresHumanConfirmation),
        riskLevel: safeText(body.riskLevel),
        dataSources: asTextArray(body.dataSources),
        allowedCallers: asTextArray(body.allowedCallers),
        destructiveEffects: asTextArray(body.destructiveEffects),
      });
      return NextResponse.json(result);
    }

    return errorResponse(`不支持的治理操作：${action || "空"}`);
  } catch (error) {
    return errorResponse(error);
  }
}

export async function PATCH(request: Request) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      { status: "error", error: auth.error },
      { status: auth.status },
    );
  }

  const paths = resolveGovernancePaths();
  const body = safeRecord(await request.json().catch(() => ({})));
  const action = safeText(body.action);

  try {
    if (action === "set_skill_status") {
      return NextResponse.json(
        await setSkillStatus({
          paths,
          skillId: safeText(body.skillId),
          status: safeText(body.status),
          changedBy: safeText(body.changedBy) || "frontend",
        }),
      );
    }

    if (action === "rollback_skill") {
      return NextResponse.json(
        await rollbackSkillVersion({
          paths,
          skillId: safeText(body.skillId),
          targetVersion: safeNumber(body.targetVersion),
          changedBy: safeText(body.changedBy) || "frontend",
        }),
      );
    }

    if (action === "restore_skill_source") {
      return NextResponse.json(
        await restoreSkillSourceFromManagedCopy({
          paths,
          skillId: safeText(body.skillId),
          changedBy: safeText(body.changedBy) || "frontend",
        }),
      );
    }

    return errorResponse(`不支持的治理操作：${action || "空"}`);
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(request: Request) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      { status: "error", error: auth.error },
      { status: auth.status },
    );
  }

  const paths = resolveGovernancePaths();
  const body = safeRecord(await request.json().catch(() => ({})));

  try {
    return NextResponse.json(
      await deleteSkillRegistration({
        paths,
        skillId: safeText(body.skillId),
        deleteManagedFiles: body.deleteManagedFiles !== false,
        changedBy: safeText(body.changedBy) || "frontend",
      }),
    );
  } catch (error) {
    return errorResponse(error);
  }
}
