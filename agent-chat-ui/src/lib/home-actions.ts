export type TaskTemplate = {
  label: string;
  icon: "book" | "table" | "chart" | "briefcase" | "database";
  prompt: string;
};

export type ManagementLink = {
  label: string;
  href: string;
  icon: "activity" | "shield";
};

export const taskTemplates: TaskTemplate[] = [
  {
    label: "整理资料",
    icon: "book",
    prompt:
      "我已经把资料放到 raw 目录了，帮我整理进知识库，并同步到完整 LightRAG。完成后告诉我用了哪些文件、生成了哪些页面、有没有需要人工确认的问题。",
  },
  {
    label: "清洗表格",
    icon: "table",
    prompt:
      "我放了一些表格，帮我检查并清洗成后续能分析的数据。如果有大文件或表头不清楚，请告诉我怎么处理。",
  },
  {
    label: "库存风险",
    icon: "chart",
    prompt:
      "帮我看看库存有没有风险，哪些商品可能断货或积压，并给出保守、平衡、激进三个建议。",
  },
  {
    label: "经营分析",
    icon: "briefcase",
    prompt:
      "帮我基于现有公司资料和数据做一次经营分析，告诉我现在最应该关注什么、有哪些风险、下一步怎么做。",
  },
  {
    label: "同步知识库",
    icon: "database",
    prompt:
      "我更新了知识库或数据，请帮我同步到完整 LightRAG，并告诉我同步是否成功。",
  },
  {
    label: "广告诊断",
    icon: "chart",
    prompt:
      "帮我做一次国内多平台电商广告诊断，覆盖天猫、京东、抖音、拼多多等渠道。请结合 DuckDB 里的投放、转化、商品和库存数据，以及 wiki/LightRAG 中的活动、品牌和运营口径，找出预算浪费、转化异常、素材或人群问题，并标出需要人工确认口径的数据缺口。",
  },
  {
    label: "商品内容优化",
    icon: "book",
    prompt:
      "帮我优化国内多平台电商的商品内容，覆盖天猫、京东、抖音、小红书、拼多多等场景。请先用 DuckDB 核对商品表现、转化、评价和售后数据，再参考 wiki/LightRAG 里的品牌卖点、禁用词和历史素材，给出标题、卖点、详情页和短视频脚本建议，并列出需要人工确认口径的表述。",
  },
  {
    label: "供应商风险",
    icon: "briefcase",
    prompt:
      "帮我分析国内多平台电商供应商风险。请结合 DuckDB 中的采购、入库、退货、质检、履约和商品销售数据，以及 wiki/LightRAG 里的供应商档案、合同约定和历史问题，识别交付、质量、价格、账期和平台合规风险，并把需要人工确认口径的结论单独列出。",
  },
  {
    label: "财务分析",
    icon: "table",
    prompt:
      "帮我做一次国内多平台电商财务分析，覆盖天猫、京东、抖音、拼多多等渠道。请基于 DuckDB 中的订单、退款、广告费、平台费用、库存和采购数据，结合 wiki/LightRAG 的会计口径、经营假设和历史报告，拆解收入、毛利、费用、现金流和异常波动，并提示需要人工确认口径的科目或数据。",
  },
  {
    label: "老板报告",
    icon: "briefcase",
    prompt:
      "帮我生成一份面向老板的国内多平台电商经营报告。请整合 DuckDB 的销售、广告、库存、财务和履约数据，并引用 wiki/LightRAG 中的业务背景、策略目标和历史决策，输出本周关键结论、风险、机会和下一步动作；凡是口径、归因或数据不确定的地方，请明确标注需要人工确认口径。",
  },
];

export const managementLinks: ManagementLink[] = [
  {
    label: "工作进度",
    href: "/tasks",
    icon: "activity",
  },
  {
    label: "问题排查",
    href: "/logs",
    icon: "activity",
  },
  {
    label: "资料体检",
    href: "/data-health",
    icon: "activity",
  },
  {
    label: "工具权限",
    href: "/governance?tab=skills",
    icon: "shield",
  },
];
