import type { ComponentType } from "react";
import {
  Activity,
  Bot,
  DatabaseZap,
  FlaskConical,
  GitBranch,
  History,
  LayoutDashboard,
  PlugZap,
  ScrollText,
  ShieldCheck,
} from "lucide-react";

export type WorkbenchNavItem = {
  href: string;
  label: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
};

export const workbenchNavItems: WorkbenchNavItem[] = [
  {
    href: "/",
    label: "开始工作",
    description: "直接告诉我想做什么",
    icon: Bot,
  },
  {
    href: "/?chatHistoryOpen=true",
    label: "历史记录",
    description: "找回以前聊过的内容和结果",
    icon: History,
  },
  {
    href: "/tasks",
    label: "工作进度",
    description: "查看任务跑到哪一步",
    icon: LayoutDashboard,
  },
  {
    href: "/data-sources",
    label: "导入资料",
    description: "导入表格、文件、店铺和业务数据",
    icon: DatabaseZap,
  },
  {
    href: "/data-health",
    label: "资料体检",
    description: "检查数据能不能放心用",
    icon: Activity,
  },
  {
    href: "/evidence-graph",
    label: "依据来源",
    description: "每个结论从哪里来",
    icon: GitBranch,
  },
  {
    href: "/platform-lab",
    label: "经营推演",
    description: "做假设、看方案、演练决策",
    icon: FlaskConical,
  },
  {
    href: "/governance?tab=skills",
    label: "工具权限",
    description: "管哪些工具能用、哪些要审批",
    icon: ShieldCheck,
  },
  {
    href: "/governance?tab=mcp",
    label: "系统连接",
    description: "管理外部系统、接口和调用规则",
    icon: PlugZap,
  },
  {
    href: "/logs",
    label: "问题排查",
    description: "查看出错原因和后台记录",
    icon: ScrollText,
  },
];

function normalizeSearch(value: string) {
  return value.startsWith("?") ? value.slice(1) : value;
}

function splitHref(href: string) {
  const [path, search = ""] = href.split("?");
  return { path, search };
}

function searchIncludes(currentSearch: string, expectedSearch: string) {
  const current = new URLSearchParams(normalizeSearch(currentSearch));
  const expected = new URLSearchParams(expectedSearch);
  for (const [key, value] of expected.entries()) {
    if (current.get(key) !== value) return false;
  }
  return true;
}

export function isActiveWorkbenchPath(
  pathname: string,
  href: string,
  currentSearch = "",
) {
  const target = splitHref(href);
  if (target.path === "/") {
    if (pathname !== "/") return false;
    if (target.search) return searchIncludes(currentSearch, target.search);
    const current = new URLSearchParams(normalizeSearch(currentSearch));
    return current.get("chatHistoryOpen") !== "true";
  }

  const pathMatches =
    pathname === target.path || pathname.startsWith(`${target.path}/`);
  if (!pathMatches) return false;

  if (target.search) {
    const current = new URLSearchParams(normalizeSearch(currentSearch));
    const expected = new URLSearchParams(target.search);
    if (
      target.path === "/governance" &&
      expected.get("tab") === "skills" &&
      !current.has("tab")
    ) {
      return true;
    }
    return searchIncludes(currentSearch, target.search);
  }
  if (target.path === "/governance") {
    return !new URLSearchParams(normalizeSearch(currentSearch)).has("tab");
  }
  return true;
}
