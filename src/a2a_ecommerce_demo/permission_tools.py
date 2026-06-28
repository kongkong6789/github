from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = Path(os.getenv("A2A_RAW_DIR", PROJECT_ROOT / "raw")).resolve()
WIKI_DIR = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
CLEANED_DIR = Path(os.getenv("A2A_CLEANED_DIR", DATA_DIR / "cleaned")).resolve()
REPORT_DIR = Path(os.getenv("A2A_REPORT_DIR", DATA_DIR / "reports")).resolve()

POLICY = {
    "raw": {"path": str(RAW_DIR), "read": True, "write": False, "delete": False},
    "wiki": {"path": str(WIKI_DIR), "read": True, "write": True, "delete": False},
    "cleaned_data": {"path": str(CLEANED_DIR), "read": True, "write": True, "delete": False},
    "reports": {"path": str(REPORT_DIR), "read": True, "write": True, "delete": False},
    "env": {"path": str(PROJECT_ROOT / ".env"), "read": False, "write": False, "delete": False},
}


def list_permission_policy() -> str:
    """列出当前本地工具权限策略，用于 Agent 执行前自检。"""
    return json.dumps(
        {
            "policy": POLICY,
            "rules": [
                "raw 原始资料默认只读，避免误覆盖真实数据。",
                "wiki、data/cleaned、data/reports 可写，用于知识库、清洗结果和报告。",
                ".env 和密钥文件禁止读取、写入和展示。",
                "删除文件、外发消息、创建采购单、修改广告预算等动作必须人工确认。",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def check_path_permission(path: str, action: str = "read") -> str:
    """检查某个路径是否符合本地权限策略。action 支持 read/write/delete。"""
    if action not in {"read", "write", "delete"}:
        raise ValueError("action must be one of: read, write, delete")
    target = Path(path).resolve()
    matches = []
    for name, rule in POLICY.items():
        root = Path(rule["path"]).resolve()
        if target == root or root in target.parents:
            matches.append((name, rule))
    if not matches:
        allowed = False
        reason = "路径不在 raw/wiki/data/reports 授权范围内。"
    else:
        name, rule = sorted(matches, key=lambda item: len(item[1]["path"]), reverse=True)[0]
        allowed = bool(rule.get(action, False))
        reason = f"匹配权限域：{name}。"
    return json.dumps(
        {
            "path": str(target),
            "action": action,
            "allowed": allowed,
            "reason": reason,
            "requires_human_confirmation": action == "delete" or not allowed,
        },
        ensure_ascii=False,
        indent=2,
    )
