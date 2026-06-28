"""
Print JackYun MCP/CLI/HTTP routing diagnostics as JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from helpers.jkyun_cli import CLI_ARCHIVE_DIR
from helpers.mcp_runtime import load_mcp_tools
from helpers.runtime_plan import WORKFLOW_METHODS, workflow_route_plan


def main() -> int:
    archives = []
    if CLI_ARCHIVE_DIR.exists():
        archives = sorted(path.name for path in CLI_ARCHIVE_DIR.glob("*.zip"))

    payload = {
        "call_strategy": config.JACKYUN_CALL_STRATEGY,
        "authorized_app_key": config.JACKYUN_AUTHORIZED_APP_KEY,
        "mcp_url": config.JACKYUN_MCP_URL,
        "mcp_token_configured": bool(config.JACKYUN_MCP_TOKEN),
        "mcp_tool_count": len(load_mcp_tools()),
        "cli_enabled": bool(config.JACKYUN_CLI_ENABLED),
        "cli_archives": archives,
        "workflows": {
            workflow: workflow_route_plan(workflow)
            for workflow in sorted(WORKFLOW_METHODS)
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
