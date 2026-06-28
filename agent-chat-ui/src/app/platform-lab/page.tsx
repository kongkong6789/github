"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  BadgeCheck,
  ClipboardCopy,
  ExternalLink,
  GitBranch,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  WorkbenchCard,
  WorkbenchPanel,
  WorkbenchShell,
} from "@/components/workbench/shell";
import {
  buildPlatformControlCenter,
  buildScenarioPrompt,
  capabilityLanes,
  demoScripts,
  scenarioTemplates,
  workflowStages,
  type PlatformControlCenter,
  type ScenarioTemplate,
} from "@/lib/platform-lab";
import { cn } from "@/lib/utils";

const stageClass = {
  landed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  ready: "border-blue-200 bg-blue-50 text-blue-700",
  next: "border-amber-200 bg-amber-50 text-amber-700",
};

const runStatusLabel = {
  queued: "待执行",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
};

type PlatformLabRunRecord = {
  run_id: string;
  kind: "scenario" | "demo";
  template_id: string;
  label: string;
  status: keyof typeof runStatusLabel;
  task_id: string;
  created_at: string;
  requested_by: string;
  links: {
    task: string;
    evidence_graph: string;
    logs: string;
  };
};

type PlatformLabRunList = {
  counts: {
    total: number;
    queued: number;
    running: number;
    completed: number;
    failed: number;
  };
  runs: PlatformLabRunRecord[];
};

function StageBadge({ status }: { status: keyof typeof stageClass }) {
  const label = status === "landed" ? "已落地" : status === "ready" ? "可运行" : "下一步";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium",
        stageClass[status],
      )}
    >
      {label}
    </span>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 space-y-1.5 text-sm leading-6 text-slate-600">
      {items.map((item) => (
        <li
          key={item}
          className="flex gap-2"
        >
          <span className="mt-2 size-1.5 shrink-0 rounded-full bg-slate-300" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export default function PlatformLabPage() {
  const [selectedId, setSelectedId] = useState(scenarioTemplates[0].id);
  const selectedTemplate =
    scenarioTemplates.find((template) => template.id === selectedId) ??
    scenarioTemplates[0];
  const [assumptions, setAssumptions] = useState(
    selectedTemplate.defaultAssumptions,
  );
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">(
    "idle",
  );
  const [runs, setRuns] = useState<PlatformLabRunList>({
    counts: { total: 0, queued: 0, running: 0, completed: 0, failed: 0 },
    runs: [],
  });
  const [controlCenter, setControlCenter] = useState<PlatformControlCenter>(
    () =>
      buildPlatformControlCenter({
        runs: { total: 0, queued: 0, completed: 0, failed: 0 },
      }),
  );
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [startingId, setStartingId] = useState("");
  const [runError, setRunError] = useState("");
  const [createdRun, setCreatedRun] = useState<PlatformLabRunRecord | null>(
    null,
  );

  const prompt = useMemo(
    () => buildScenarioPrompt(selectedTemplate, assumptions),
    [assumptions, selectedTemplate],
  );

  function selectTemplate(template: ScenarioTemplate) {
    setSelectedId(template.id);
    setAssumptions(template.defaultAssumptions);
    setCopyStatus("idle");
  }

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopyStatus("copied");
    } catch {
      setCopyStatus("failed");
    }
    window.setTimeout(() => setCopyStatus("idle"), 1800);
  }

  async function refreshPlatformState() {
    setLoadingRuns(true);
    try {
      const [runsResponse, controlResponse] = await Promise.all([
        fetch("/api/platform-lab/runs?limit=8", { cache: "no-store" }),
        fetch("/api/platform-lab/control-center", { cache: "no-store" }),
      ]);
      if (runsResponse.ok) {
        setRuns((await runsResponse.json()) as PlatformLabRunList);
      }
      if (controlResponse.ok) {
        setControlCenter((await controlResponse.json()) as PlatformControlCenter);
      }
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    } finally {
      setLoadingRuns(false);
    }
  }

  async function createRun(kind: "scenario" | "demo", templateId: string) {
    setStartingId(`${kind}:${templateId}`);
    setRunError("");
    try {
      const response = await fetch("/api/platform-lab/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          kind,
          templateId,
          assumptions: kind === "scenario" ? assumptions : "",
          requestedBy: "platform_lab_ui",
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.message || "创建经营推演任务失败。");
      }
      setCreatedRun(payload as PlatformLabRunRecord);
      await refreshPlatformState();
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    } finally {
      setStartingId("");
    }
  }

  useEffect(() => {
    void refreshPlatformState();
  }, []);

  return (
    <WorkbenchShell
      title="经营推演"
      description="用已有资料和安全规则做经营假设、方案演练和任务化执行。"
      actions={
        <>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/governance?tab=skills">
              <ShieldCheck className="size-4" />
              工具权限
            </Link>
          </Button>
          <Button
            asChild
            className="bg-blue-700 !text-white hover:bg-blue-800"
          >
            <Link href="/">
              <ArrowLeft className="size-4" />
              返回对话
            </Link>
          </Button>
        </>
      }
    >
      <WorkbenchPanel className="mb-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">
              经营能力总览
            </h2>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={refreshPlatformState}
            disabled={loadingRuns}
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            {loadingRuns ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            刷新
          </Button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          {controlCenter.summary.map((item) => (
            <div
              key={item.label}
              className="rounded-md border border-slate-200 bg-white p-3"
            >
              <div className="text-xs text-slate-500">{item.label}</div>
              <div className="mt-1 text-xl font-semibold text-slate-950">
                {item.value}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-4">
          {controlCenter.sections.map((section) => (
            <Link
              key={section.id}
              href={section.href}
              className="rounded-md border border-slate-200 bg-white p-3 transition hover:border-blue-200 hover:bg-blue-50/40"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-950">
                  {section.label}
                </span>
              </div>
              <div className="mt-2 text-sm font-semibold text-slate-800">
                {section.value}
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {section.detail}
              </p>
            </Link>
          ))}
        </div>
      </WorkbenchPanel>

      {(runError || createdRun) && (
        <div
          className={cn(
            "mb-4 rounded-md border px-3 py-2 text-sm",
            runError
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700",
          )}
        >
          {runError ? (
            <span className="inline-flex items-center gap-2">
              <TriangleAlert className="size-4" />
              {runError}
            </span>
          ) : createdRun ? (
            <span className="inline-flex flex-wrap items-center gap-2">
              <BadgeCheck className="size-4" />
              已创建任务 {createdRun.task_id}
              <Link
                href={createdRun.links.task}
                className="inline-flex items-center gap-1 underline"
              >
                查看任务
                <ExternalLink className="size-3.5" />
              </Link>
            </span>
          ) : null}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <WorkbenchPanel className="p-4">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">
              能力准备地图
            </h2>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {capabilityLanes.map((lane) => (
              <WorkbenchCard
                key={lane.id}
                className="shadow-none"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-slate-950">
                      {lane.title}
                    </h3>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {lane.inspiration}
                    </p>
                  </div>
                </div>
                <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
                  {lane.currentLanding}
                </p>
                <BulletList items={lane.nextActions} />
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {lane.evidence.map((item) => (
                    <span
                      key={item}
                      className="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-500"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </WorkbenchCard>
            ))}
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel className="p-4">
          <div className="flex items-center gap-2">
            <GitBranch className="size-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">
              经营流程图
            </h2>
          </div>
          <div className="mt-4 space-y-3">
            {workflowStages.map((stage, index) => (
              <div
                key={stage.id}
                className="grid gap-3 rounded-md border border-slate-200 bg-white p-3 md:grid-cols-[auto_1fr]"
              >
                <div className="flex size-8 items-center justify-center rounded-md bg-slate-100 text-sm font-semibold text-slate-600">
                  {index + 1}
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold text-slate-950">
                      {stage.label}
                    </h3>
                    <StageBadge status={stage.status} />
                    <span className="text-xs text-slate-500">
                      {stage.owner}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-2 text-xs text-slate-600 md:grid-cols-3">
                    <div>
                      <div className="font-medium text-slate-500">输入</div>
                      {stage.inputs.join(" / ")}
                    </div>
                    <div>
                      <div className="font-medium text-slate-500">输出</div>
                      {stage.outputs.join(" / ")}
                    </div>
                    <div>
                      <div className="font-medium text-slate-500">检查点</div>
                      {stage.gates.join(" / ")}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </WorkbenchPanel>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <WorkbenchPanel className="p-4">
          <div className="flex items-center gap-2">
            <Play className="size-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">
              经营假设推演
            </h2>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {scenarioTemplates.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => selectTemplate(template)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-sm",
                  selectedTemplate.id === template.id
                    ? "border-blue-200 bg-blue-50 text-blue-800"
                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
                )}
              >
                {template.label}
              </button>
            ))}
          </div>
          <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold text-slate-950">
                {selectedTemplate.label}
              </h3>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {selectedTemplate.description}
            </p>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium text-slate-700">
              假设变量
            </span>
            <textarea
              className="mt-1 min-h-28 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 text-slate-950 outline-none focus:border-blue-400 focus:ring-3 focus:ring-blue-100"
              value={assumptions}
              onChange={(event) => setAssumptions(event.currentTarget.value)}
            />
          </label>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div>
              <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
                <BadgeCheck className="size-4 text-emerald-600" />
                必需证据
              </div>
              <BulletList items={selectedTemplate.requiredEvidence} />
            </div>
            <div>
              <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
                <ShieldCheck className="size-4 text-blue-700" />
                安全边界
              </div>
              <BulletList items={selectedTemplate.guardrails} />
            </div>
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">
                可直接执行的任务说明
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                复制后回到“开始工作”执行，结果会进入工作进度、依据来源和工具审计。
              </p>
            </div>
            <Button
              type="button"
              onClick={copyPrompt}
              variant="outline"
              className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            >
              {copyStatus === "copied" ? (
                <BadgeCheck className="size-4" />
              ) : (
                <ClipboardCopy className="size-4" />
              )}
              {copyStatus === "copied"
                ? "已复制"
                : copyStatus === "failed"
                  ? "复制失败"
                : "复制提示词"}
            </Button>
            <Button
              type="button"
              onClick={() => createRun("scenario", selectedTemplate.id)}
              disabled={Boolean(startingId)}
              className="bg-slate-950 !text-white hover:bg-slate-800"
            >
              {startingId === `scenario:${selectedTemplate.id}` ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              创建推演任务
            </Button>
          </div>
          <pre className="mt-4 max-h-[34rem] overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-950 p-4 text-sm leading-6 text-slate-100">
            {prompt}
          </pre>
        </WorkbenchPanel>
      </div>

      <WorkbenchPanel className="mt-4 p-4">
        <div className="flex items-center gap-2">
          <RefreshCw className="size-5 text-blue-700" />
          <h2 className="text-lg font-semibold text-slate-950">
            演示任务剧本
          </h2>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {demoScripts.map((script) => (
            <WorkbenchCard
              key={script.id}
              className="shadow-none"
            >
              <div className="text-sm text-slate-500">{script.audience}</div>
              <h3 className="mt-1 font-semibold text-slate-950">
                {script.label}
              </h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {script.openingPrompt}
              </p>
              <BulletList items={script.successEvidence} />
              <Button
                type="button"
                onClick={() => createRun("demo", script.id)}
                disabled={Boolean(startingId)}
                className="mt-3 bg-slate-950 !text-white hover:bg-slate-800"
              >
                {startingId === `demo:${script.id}` ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Play className="size-4" />
                )}
                创建演示任务
              </Button>
            </WorkbenchCard>
          ))}
        </div>
      </WorkbenchPanel>

      <WorkbenchPanel className="mt-4 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <GitBranch className="size-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">
              推演记录
            </h2>
          </div>
          <span className="text-sm text-slate-500">
            {loadingRuns ? "读取中" : `${runs.counts.total} 次运行`}
          </span>
        </div>
        <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
          <div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500">
            <span>任务</span>
            <span>状态</span>
            <span>入口</span>
          </div>
          {runs.runs.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-slate-500">
              暂无经营推演记录
            </div>
          ) : (
            runs.runs.map((run) => (
              <div
                key={run.run_id}
                className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-slate-100 px-3 py-3 text-sm last:border-b-0"
              >
                <div className="min-w-0">
                  <div className="font-medium text-slate-950">{run.label}</div>
                  <div className="mt-1 truncate font-mono text-xs text-slate-500">
                    {run.task_id}
                  </div>
                </div>
                <span className="self-start rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">
                  {runStatusLabel[run.status] ?? run.status}
                </span>
                <div className="flex items-start gap-2">
                  <Link
                    href={run.links.task}
                    className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    任务
                  </Link>
                  <Link
                    href={run.links.evidence_graph}
                    className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    依据来源
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </WorkbenchPanel>
    </WorkbenchShell>
  );
}
