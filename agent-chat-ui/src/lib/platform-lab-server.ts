import { randomUUID } from "node:crypto";
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  buildScenarioPrompt,
  demoScripts,
  scenarioTemplates,
  type DemoScript,
  type ScenarioTemplate,
} from "./platform-lab";

export type PlatformLabRunKind = "scenario" | "demo";

export type PlatformLabRunInput = {
  kind: PlatformLabRunKind;
  templateId: string;
  assumptions?: string;
  requestedBy?: string;
  now?: string;
};

export type PlatformLabPaths = {
  taskDir: string;
  auditPath: string;
  runLogPath: string;
  reportsDir: string;
};

export type PlatformLabRunRecord = {
  run_id: string;
  kind: PlatformLabRunKind;
  template_id: string;
  label: string;
  status: "queued" | "running" | "completed" | "failed";
  task_id: string;
  task_path: string;
  report_path: string;
  prompt: string;
  assumptions: string;
  requested_by: string;
  created_at: string;
  updated_at: string;
  source_project: string;
  evidence_paths: string[];
  links: {
    task: string;
    evidence_graph: string;
    logs: string;
  };
};

export type PlatformLabRunList = {
  run_log_path: string;
  counts: {
    total: number;
    queued: number;
    running: number;
    completed: number;
    failed: number;
  };
  runs: PlatformLabRunRecord[];
};

type TaskSeed = {
  task_id: string;
  goal: string;
  original_user_text: string;
  requested_by: string;
  status: string;
  created_at: string;
  updated_at: string;
  background_running: boolean;
  recoverable: boolean;
  platform_lab_run_id: string;
  source: string;
  steps: Array<Record<string, unknown>>;
  final_report: {
    saved_to: string;
    evidence_chain: {
      registry_path: string;
      wiki_pages: string[];
      report_paths: string[];
      duckdb_marts: Array<{ mart: string; fields: string[] }>;
      data_gaps: string[];
    };
  };
};

const CANONICAL_EVIDENCE_PATHS = [
  "data/warehouse/dataset_registry.json",
  "wiki/index.md",
  "data/audit/events.jsonl",
];

function safeText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function slug(value: string) {
  return (
    value
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9\u4e00-\u9fff._-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 72) || "run"
  );
}

function compactTimestamp(value: string) {
  const parsed = new Date(value);
  const date = Number.isFinite(parsed.getTime()) ? parsed : new Date();
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function taskLinks(taskId: string) {
  const encoded = encodeURIComponent(taskId);
  return {
    task: `/tasks/${encoded}`,
    evidence_graph: `/evidence-graph?taskId=${encoded}`,
    logs: `/logs?task_id=${encoded}`,
  };
}

function findScenario(templateId: string): ScenarioTemplate {
  const template = scenarioTemplates.find((item) => item.id === templateId);
  if (!template) throw new Error(`未知沙盘场景：${templateId}`);
  return template;
}

function findDemo(templateId: string): DemoScript {
  const script = demoScripts.find((item) => item.id === templateId);
  if (!script) throw new Error(`未知演示剧本：${templateId}`);
  return script;
}

function demoPrompt(script: DemoScript) {
  return [
    script.openingPrompt,
    "",
    "执行要求：",
    "- 使用本地数据表、知识库、ERP 只读快照或明确说明数据缺口。",
    "- 输出依据来源、风险等级、人工确认动作和下一步任务。",
    "- 不得直接修改广告预算、采购单、供应商消息或任何外部系统。",
    "",
    "成功证据：",
    ...script.successEvidence.map((item) => `- ${item}`),
  ].join("\n");
}

function reportMarkdown(run: PlatformLabRunRecord) {
  return [
    `# ${run.label}`,
    "",
    `- run_id: \`${run.run_id}\``,
    `- task_id: \`${run.task_id}\``,
    `- kind: \`${run.kind}\``,
    `- status: \`${run.status}\``,
    `- requested_by: \`${run.requested_by}\``,
    `- created_at: \`${run.created_at}\``,
    "",
    "## 假设变量",
    "",
    run.assumptions || "无额外假设。",
    "",
    "## 可执行 Prompt",
    "",
    "```text",
    run.prompt,
    "```",
    "",
    "## 依据来源",
    "",
    ...run.evidence_paths.map((item) => `- \`${item}\``),
    "",
    "## 数据缺口",
    "",
    "- 需要在正式外部写入前确认实时 ERP 查询时间、过滤条件和关键财务口径。",
    "- 需要确认采购价、供应商交期、广告归因和平台活动口径。",
    "",
    "## 人工确认",
    "",
    "- 任何采购、广告预算、供应商外发、真实订单或财务写入动作必须进入人工确认。",
  ].join("\n");
}

function buildTaskSeed(run: PlatformLabRunRecord): TaskSeed {
  const dataGaps = [
    "ERP 查询时间与过滤条件",
    "采购价 / 供应商交期 / 广告归因口径",
    "外部写入前的人工确认动作",
  ];
  return {
    task_id: run.task_id,
    goal: `经营推演执行：${run.label}\n\n用户原话：${run.prompt}`,
    original_user_text: run.prompt,
    requested_by: run.requested_by,
    status: "queued",
    created_at: run.created_at,
    updated_at: run.updated_at,
    background_running: false,
    recoverable: true,
    platform_lab_run_id: run.run_id,
    source: "platform_lab",
    steps: [
      {
        task: "platform_lab.run_created",
        status: "queued",
        summary:
          "经营推演已创建可执行任务种子，可从任务详情继续让智能体执行。",
        completed_at: run.created_at,
        evidence: run.evidence_paths,
        risks: ["外部写入前必须人工确认"],
        missing_data: dataGaps,
        next_actions: [
          "打开任务详情继续执行该 prompt。",
          "查看依据来源确认任务、报告、数据集和风险节点。",
        ],
        data: {
          event_type: "platform_lab.run_created",
          run_id: run.run_id,
          kind: run.kind,
          template_id: run.template_id,
          source_project: run.source_project,
        },
      },
      {
        task: "qa.escalated",
        status: "warning",
        summary:
          "该沙盘可能导向采购、广告或供应商动作，所有外部写入必须先经过人工确认。",
        completed_at: run.created_at,
        evidence: run.evidence_paths,
        risks: ["不得直接执行外部写入", "人工确认"],
        missing_data: dataGaps,
        next_actions: ["在人工确认收件箱中审批或改写外部动作。"],
        data: {
          event_type: "qa.escalated",
          verdict: "ESCALATED",
          checked_by: "platform_lab",
          retry_count: 0,
          evidence_paths: run.evidence_paths,
        },
      },
    ],
    final_report: {
      saved_to: run.report_path,
      evidence_chain: {
        registry_path: "data/warehouse/dataset_registry.json",
        wiki_pages: ["wiki/index.md"],
        report_paths: [run.report_path],
        duckdb_marts: [
          {
            mart: "本地数据表",
            fields: ["sales", "inventory", "channel", "supplier", "finance"],
          },
        ],
        data_gaps: dataGaps,
      },
    },
  };
}

async function appendJsonLine(filePath: string, payload: unknown) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await appendFile(filePath, `${JSON.stringify(payload)}\n`, "utf8");
}

function runCounts(runs: PlatformLabRunRecord[]): PlatformLabRunList["counts"] {
  return {
    total: runs.length,
    queued: runs.filter((run) => run.status === "queued").length,
    running: runs.filter((run) => run.status === "running").length,
    completed: runs.filter((run) => run.status === "completed").length,
    failed: runs.filter((run) => run.status === "failed").length,
  };
}

export async function listPlatformLabRuns({
  runLogPath,
  limit = 50,
}: {
  runLogPath: string;
  limit?: number;
}): Promise<PlatformLabRunList> {
  let content = "";
  try {
    content = await readFile(runLogPath, "utf8");
  } catch {
    return {
      run_log_path: runLogPath,
      counts: { total: 0, queued: 0, running: 0, completed: 0, failed: 0 },
      runs: [],
    };
  }
  const runs = content
    .split(/\r?\n/)
    .filter(Boolean)
    .flatMap((line): PlatformLabRunRecord[] => {
      try {
        const record = JSON.parse(line) as PlatformLabRunRecord;
        return record.run_id && record.task_id ? [record] : [];
      } catch {
        return [];
      }
    })
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
  const capped = runs.slice(0, Math.max(1, Math.min(limit, 200)));
  return { run_log_path: runLogPath, counts: runCounts(runs), runs: capped };
}

export async function createPlatformLabRun(
  input: PlatformLabRunInput,
  paths: PlatformLabPaths,
): Promise<PlatformLabRunRecord> {
  const now = safeText(input.now) || new Date().toISOString();
  const requestedBy = safeText(input.requestedBy) || "platform_lab";
  const templateId = safeText(input.templateId);
  const timestamp = compactTimestamp(now);
  const evidencePaths = [...CANONICAL_EVIDENCE_PATHS];

  let label = "";
  let prompt = "";
  let assumptions = "";
  let sourceProject = "";
  if (input.kind === "scenario") {
    const template = findScenario(templateId);
    label = template.label;
    assumptions = safeText(input.assumptions) || template.defaultAssumptions;
    prompt = buildScenarioPrompt(template, assumptions);
    sourceProject = template.source;
  } else if (input.kind === "demo") {
    const script = findDemo(templateId);
    label = script.label;
    assumptions = safeText(input.assumptions);
    prompt = demoPrompt(script);
    sourceProject = "demo";
  } else {
    throw new Error(`不支持的经营推演运行类型：${input.kind}`);
  }

  const idStem = `${timestamp}-platform-lab-${slug(templateId)}-${randomUUID().slice(0, 8)}`;
  const runId = `run_${idStem}`;
  const taskId = idStem;
  const reportPath = path.join(paths.reportsDir, "platform-lab", `${runId}.md`);
  const taskPath = path.join(paths.taskDir, `${taskId}.json`);
  const run: PlatformLabRunRecord = {
    run_id: runId,
    kind: input.kind,
    template_id: templateId,
    label,
    status: "queued",
    task_id: taskId,
    task_path: taskPath,
    report_path: reportPath,
    prompt,
    assumptions,
    requested_by: requestedBy,
    created_at: now,
    updated_at: now,
    source_project: sourceProject,
    evidence_paths: evidencePaths,
    links: taskLinks(taskId),
  };

  await mkdir(paths.taskDir, { recursive: true });
  await mkdir(path.dirname(reportPath), { recursive: true });
  await writeFile(reportPath, reportMarkdown(run), "utf8");
  await writeFile(taskPath, JSON.stringify(buildTaskSeed(run), null, 2), "utf8");
  await appendJsonLine(paths.runLogPath, run);
  await appendJsonLine(paths.auditPath, {
    event_type: "platform_lab_run_created",
    actor: requestedBy,
    summary: `经营推演创建运行：${label}`,
    created_at: now,
    timestamp: now,
    task_id: taskId,
    tool_name: "platform_lab",
    risk_level: "medium",
    risks: ["外部写入前必须人工确认"],
    metadata: {
      run_id: runId,
      kind: input.kind,
      template_id: templateId,
      source_project: sourceProject,
      task_id: taskId,
      report_path: reportPath,
    },
  });
  return run;
}
