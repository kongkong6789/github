export type ReferenceProject =
  | "governance"
  | "workflow"
  | "simulation"
  | "demo"
  | "a2a";

export type CapabilityLane = {
  id: string;
  title: string;
  source: ReferenceProject;
  inspiration: string;
  currentLanding: string;
  nextActions: string[];
  evidence: string[];
};

export type WorkflowStage = {
  id: string;
  label: string;
  owner: string;
  status: "landed" | "ready" | "next";
  inputs: string[];
  outputs: string[];
  gates: string[];
};

export type ScenarioTemplate = {
  id: string;
  label: string;
  source: ReferenceProject;
  description: string;
  objective: string;
  requiredEvidence: string[];
  simulationSteps: string[];
  guardrails: string[];
  defaultAssumptions: string;
};

export type DemoScript = {
  id: string;
  label: string;
  audience: string;
  openingPrompt: string;
  successEvidence: string[];
};

export type PlatformControlCenterInput = {
  dataHealth?: {
    counts?: {
      datasets?: number;
      warnings?: number;
      [key: string]: unknown;
    };
    warnings?: string[];
  };
  governance?: {
    skill_count?: number;
    mcp_policy_count?: number;
    high_risk_count?: number;
    [key: string]: unknown;
  };
  sources?: {
    active_sources?: number;
    stale_sources?: number;
    failed_sources?: number;
    [key: string]: unknown;
  };
  runs?: {
    total?: number;
    queued?: number;
    completed?: number;
    failed?: number;
    [key: string]: unknown;
  };
};

export type PlatformControlCenterSection = {
  id: string;
  label: string;
  source: ReferenceProject;
  status: "ok" | "warning" | "critical";
  value: string;
  detail: string;
  href: string;
};

export type PlatformControlCenter = {
  generated_at: string;
  summary: Array<{ label: string; value: string; status: string }>;
  sections: PlatformControlCenterSection[];
};

export const capabilityLanes: CapabilityLane[] = [
  {
    id: "control-center",
    title: "统一配置中心",
    source: "governance",
    inspiration: "集中管理模型、知识库、工具、工作流和权限策略。",
    currentLanding:
      "对应到工具权限、资料体检、导入资料、SkillHub 和系统连接规则。",
    nextActions: [
      "把模型、知识库、外部系统、技能和连接规则聚合成同一张运行配置地图",
      "给每个配置项绑定健康状态、负责人、风险和跳转入口",
      "把写入类能力继续放在人工确认和操作记录之后",
    ],
    evidence: [
      "/governance?tab=skills",
      "/governance?tab=mcp",
      "/data-health",
      "/data-sources",
    ],
  },
  {
    id: "workflow-map",
    title: "经营流程图",
    source: "workflow",
    inspiration: "把经营分析流程沉淀为可审计、可保存、可复用的流程地图。",
    currentLanding:
      "把导入资料、数据表、知识库、智能分析、审批和报告串成可扫描链路。",
    nextActions: [
      "先展示标准经营分析流程，再逐步支持保存流程模板",
      "每个节点都要求有输入、输出、质量检查和依据链接",
      "后续再考虑拖拽编排，避免先引入过重的流程运行时",
    ],
    evidence: [
      "data/source_registry/snapshots.jsonl",
      "data/warehouse/dataset_registry.json",
      "wiki/index.md",
      "data/audit/events.jsonl",
    ],
  },
  {
    id: "simulation-sandbox",
    title: "经营假设推演",
    source: "simulation",
    inspiration: "把假设变量、证据引用、风险边界和三档方案放进同一个经营沙盘。",
    currentLanding:
      "输入经营假设后，要求系统基于数据底座和依据来源输出保守、平衡、激进三档方案。",
    nextActions: [
      "限定在库存、渠道、广告、供应商和现金流等可落地场景",
      "每个推演必须引用数据表、知识库、ERP 只读快照或明确数据缺口",
      "输出必须包含可人工确认的动作，而不是直接执行外部写入",
    ],
    evidence: [
      "本地数据表",
      "知识库结论与依据",
      "ERP live_read_only_fallback",
      "人工确认收件箱",
    ],
  },
  {
    id: "demo-playbooks",
    title: "演示任务剧本",
    source: "demo",
    inspiration: "把复杂经营能力包装成可复现、可追踪的产品化演示剧本。",
    currentLanding:
      "沉淀库存风险、渠道利润、新品补货、广告预算、供应商异常五类演示剧本。",
    nextActions: [
      "每个演示任务固定输入材料、成功依据和报告结构",
      "让运营同学能一键复现，而不是靠口头说明系统能做什么",
      "把演示运行结果进入工作进度和依据来源",
    ],
    evidence: ["/tasks", "/evidence-graph", "/logs", "/data-health"],
  },
];

export const workflowStages: WorkflowStage[] = [
  {
    id: "source",
    label: "导入资料",
    owner: "资料治理",
    status: "landed",
    inputs: ["平台导出", "企业微信智能表", "ERP 只读快照", "本地 raw/"],
    outputs: ["资料登记", "原始快照", "字段变化"],
    gates: ["来源可追溯", "敏感字段识别", "过期源预警"],
  },
  {
    id: "fact-layer",
    label: "数据底座登记",
    owner: "本地数据仓库",
    status: "landed",
    inputs: ["清洗后表格", "Parquet", "数据清单"],
    outputs: ["分析视图", "经营宽表", "资料说明页"],
    gates: ["行数校验", "字段口径", "质量报告"],
  },
  {
    id: "knowledge",
    label: "知识与依据",
    owner: "知识库服务",
    status: "landed",
    inputs: ["资料说明页", "历史决策", "结论与依据"],
    outputs: ["可检索上下文", "依据来源节点", "复盘问题"],
    gates: ["缺少依据的结论", "过期结论", "冲突结论"],
  },
  {
    id: "agent-work",
    label: "智能分析",
    owner: "智能体 / 技能",
    status: "ready",
    inputs: ["任务目标", "工具权限清单", "可用技能"],
    outputs: ["经营报告", "风险清单", "下一步动作"],
    gates: ["工具权限", "操作记录可审计", "人工确认边界"],
  },
  {
    id: "simulation",
    label: "假设推演",
    owner: "经营沙盘",
    status: "next",
    inputs: ["假设变量", "基准口径", "风险偏好"],
    outputs: ["保守/平衡/激进三档结果", "待确认数据缺口"],
    gates: ["不能替代事实", "不能直接外部写入", "必须引用依据"],
  },
];

export const scenarioTemplates: ScenarioTemplate[] = [
  {
    id: "inventory-shock",
    label: "库存冲击推演",
    source: "simulation",
    description: "模拟断货、积压、调拨和清仓组合动作对经营结果的影响。",
    objective:
      "判断未来 14-30 天哪些 SKU 可能缺货或积压，并生成三档补货/调拨/清仓方案。",
    requiredEvidence: [
      "库存与销量数据表",
      "ERP 实时只读库存快照",
      "SKU / 仓库 / 渠道知识库页面",
      "历史促销或断货结论",
    ],
    simulationSteps: [
      "建立当前库存覆盖天数基线",
      "注入销量上升、补货延迟或渠道促销变量",
      "按保守、平衡、激进三档估算缺口和动作",
      "列出需要人工确认的采购价、供应商交期和平台活动口径",
    ],
    guardrails: [
      "不直接创建采购单",
      "金额口径缺失时只能输出区间或风险等级",
      "ERP 实时结果必须标注查询时间和过滤条件",
    ],
    defaultAssumptions:
      "核心 SKU 销量提升 20%，供应商交期延迟 7 天，平台活动库存安全线提高到 21 天。",
  },
  {
    id: "channel-budget",
    label: "渠道预算推演",
    source: "workflow",
    description: "把工作流式预算诊断落地到广告与渠道经营场景。",
    objective:
      "评估天猫、京东、抖音、拼多多预算调整对 GMV、毛利和库存压力的影响。",
    requiredEvidence: [
      "广告投放与转化数据",
      "订单 / 退款 / 平台费用数据表",
      "渠道策略知识库",
      "库存风险和履约约束",
    ],
    simulationSteps: [
      "拆分各渠道当前 ROI、毛利和库存约束",
      "注入预算上调、下调或迁移变量",
      "输出预算重分配建议和风险阈值",
      "把需人工确认的财务科目和归因口径单独列出",
    ],
    guardrails: [
      "不直接修改广告预算",
      "不使用未登记资料来源做强结论",
      "归因不确定时必须给出数据缺口",
    ],
    defaultAssumptions:
      "将低 ROI 渠道预算下调 15%，把释放预算转向高毛利且库存健康的渠道。",
  },
  {
    id: "supplier-delay",
    label: "供应商延迟推演",
    source: "a2a",
    description: "围绕供应商交付、质量、价格和账期生成经营风险沙盘。",
    objective:
      "识别供应商延迟或质量异常对库存、渠道履约和现金流的连锁影响。",
    requiredEvidence: [
      "采购 / 入库 / 质检数据",
      "供应商知识库档案",
      "历史异常结论",
      "库存与渠道履约数据",
    ],
    simulationSteps: [
      "按供应商和 SKU 建立当前风险基线",
      "注入交期延迟、质量退货或价格上涨变量",
      "输出替代供应、调拨和销售节奏调整方案",
      "列出合同、账期和质量标准的人工确认项",
    ],
    guardrails: [
      "不直接外发供应商消息",
      "合同条款缺失时不能给出确定性法律结论",
      "敏感采购价必须遵守脱敏和审计规则",
    ],
    defaultAssumptions:
      "主力供应商延迟 10 天，次要供应商价格上涨 6%，质检不良率提升 2 个百分点。",
  },
];

export const demoScripts: DemoScript[] = [
  {
    id: "boss-weekly",
    label: "老板周报演示",
    audience: "老板 / 经营负责人",
    openingPrompt:
      "请生成一份老板周报，把销售、库存、广告、财务和履约异常压缩成 5 个结论、3 个风险和下周动作。",
    successEvidence: [
      "引用本地数据表或数据清单",
      "引用知识库背景和历史决策",
      "不确定口径进入人工确认清单",
    ],
  },
  {
    id: "new-product-launch",
    label: "新品上市推演演示",
    audience: "PM / 运营",
    openingPrompt:
      "围绕新品上市做一次假设推演，比较保守、平衡、激进三档铺货和预算策略。",
    successEvidence: [
      "输出库存覆盖天数和渠道预算约束",
      "给出三档策略和触发阈值",
      "所有建议带证据来源或数据缺口",
    ],
  },
  {
    id: "supplier-fire-drill",
    label: "供应商异常演练",
    audience: "供应链 / 财务 / 运营",
    openingPrompt:
      "模拟主力供应商延迟交付，分析对库存、渠道履约、现金流和客户体验的影响。",
    successEvidence: [
      "连接供应商、SKU、仓库、渠道证据节点",
      "识别采购价和账期敏感字段",
      "外部动作进入人工确认",
    ],
  },
];

export function buildScenarioPrompt(
  template: ScenarioTemplate,
  assumptions: string,
) {
  const normalizedAssumptions = assumptions.trim() || template.defaultAssumptions;
  return [
    `请执行「${template.label}」。`,
    "",
    `目标：${template.objective}`,
    "",
    `需要推演的假设：${normalizedAssumptions}`,
    "",
    "必须使用并引用的证据：",
    ...template.requiredEvidence.map((item) => `- ${item}`),
    "",
    "推演步骤：",
    ...template.simulationSteps.map((item, index) => `${index + 1}. ${item}`),
    "",
    "安全边界：",
    ...template.guardrails.map((item) => `- ${item}`),
    "",
    "输出要求：请给出保守、平衡、激进三档方案；每个结论标注证据来源、数据缺口、风险等级、需要人工确认的动作。不得直接执行外部写入。",
  ].join("\n");
}

function safeNumber(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function sectionStatus({
  critical = 0,
  warning = 0,
}: {
  critical?: number;
  warning?: number;
}): PlatformControlCenterSection["status"] {
  if (critical > 0) return "critical";
  if (warning > 0) return "warning";
  return "ok";
}

export function buildPlatformControlCenter(
  input: PlatformControlCenterInput = {},
): PlatformControlCenter {
  const datasetCount = safeNumber(input.dataHealth?.counts?.datasets);
  const dataWarnings =
    safeNumber(input.dataHealth?.counts?.warnings) +
    (input.dataHealth?.warnings?.length ?? 0);
  const skillCount = safeNumber(input.governance?.skill_count);
  const mcpPolicyCount = safeNumber(input.governance?.mcp_policy_count);
  const highRiskCount = safeNumber(input.governance?.high_risk_count);
  const activeSources = safeNumber(input.sources?.active_sources);
  const staleSources = safeNumber(input.sources?.stale_sources);
  const failedSources = safeNumber(input.sources?.failed_sources);
  const runTotal = safeNumber(input.runs?.total);
  const queuedRuns = safeNumber(input.runs?.queued);
  const completedRuns = safeNumber(input.runs?.completed);
  const failedRuns = safeNumber(input.runs?.failed);

  const sections: PlatformControlCenterSection[] = [
    {
      id: "model-tool-governance",
      label: "工具权限配置",
      source: "governance",
      status: sectionStatus({ warning: highRiskCount }),
      value: `${skillCount} 技能 / ${mcpPolicyCount} 策略`,
      detail:
        highRiskCount > 0
          ? `${highRiskCount} 个高风险能力需要保持人审。`
          : "技能、系统连接和高风险动作已纳入工具权限面板。",
      href: "/governance?tab=skills",
    },
    {
      id: "data-readiness",
      label: "数据底座与知识库",
      source: "a2a",
      status: sectionStatus({ warning: dataWarnings }),
      value: `${datasetCount} 数据集`,
      detail:
        dataWarnings > 0
          ? `${dataWarnings} 条资料体检预警需要补依据或口径。`
          : "本地数据仓库和知识库依据可供推演引用。",
      href: "/data-health",
    },
    {
      id: "source-operations",
      label: "资料来源运行状态",
      source: "workflow",
      status: sectionStatus({ critical: failedSources, warning: staleSources }),
      value: `${activeSources} 活跃来源`,
      detail:
        failedSources > 0
          ? `${failedSources} 个资料来源同步失败。`
          : staleSources > 0
            ? `${staleSources} 个资料来源接近或超过更新要求。`
            : "本地和只读外部资料可用于经营分析。",
      href: "/data-sources",
    },
    {
      id: "platform-lab-runs",
      label: "经营推演运行",
      source: "simulation",
      status: sectionStatus({ critical: failedRuns, warning: queuedRuns }),
      value: `${runTotal} 次运行`,
      detail:
        runTotal > 0
          ? `${queuedRuns} 个待执行，${completedRuns} 个已完成。`
          : "还没有推演或演示运行记录。",
      href: "/platform-lab",
    },
  ];

  return {
    generated_at: new Date().toISOString(),
    summary: [
      { label: "工具能力", value: String(skillCount + mcpPolicyCount), status: sections[0].status },
      { label: "数据集", value: String(datasetCount), status: sections[1].status },
      { label: "资料来源", value: String(activeSources), status: sections[2].status },
      { label: "推演运行", value: String(runTotal), status: sections[3].status },
    ],
    sections,
  };
}
