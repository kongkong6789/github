from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = [
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "config",
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "agent-chat-ui" / "src",
    PROJECT_ROOT / ".env.example",
]

ALLOWED_SUFFIXES = {".py", ".md", ".json", ".example", ".ts", ".tsx"}

BLOCKED_LITERALS = [
    "37811901",
    "6be140cc09f441978a1ff6727367dda2",
    "159.75.104.61",
    "65405d0ec432ee",
    "token-plan-cn.xiaomimimo.com",
    "KINGDEE_USERNAME=Administrator",
]

INLINE_SECRET_PATTERNS = [
    re.compile(
        r"https://qyapi\.weixin\.qq\.com/mcp/robot-doc\?apikey=(?!secret-key)[^&\s\"']{8,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"https://doc\.weixin\.qq\.com/smartsheet/[^\s\"']*scode=(?!secret-code)[^&\s\"']{8,}",
        re.IGNORECASE,
    ),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _should_scan(path: Path) -> bool:
    if path.is_file() and path.name == ".env.example":
        return True
    if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    if path.name.startswith("test_") or path.name.endswith(".test.ts"):
        return False
    if path.name in {"doctor.py", "test_p7_engineering_guardrails.py"}:
        return False
    return True


class CredentialDesensitizationTests(unittest.TestCase):
    def test_non_test_sources_do_not_contain_known_live_literals(self) -> None:
        violations: list[str] = []
        paths = [PROJECT_ROOT / ".env.example"] if (PROJECT_ROOT / ".env.example").exists() else []
        for root in SCAN_ROOTS:
            if root.is_file():
                paths.append(root)
                continue
            if not root.exists():
                continue
            paths.extend(sorted(root.rglob("*")))
        for path in paths:
            if not _should_scan(path):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for literal in BLOCKED_LITERALS:
                if literal in text:
                    violations.append(f"{_relative(path)} contains {literal!r}")
            for pattern in INLINE_SECRET_PATTERNS:
                match = pattern.search(text)
                if match:
                    violations.append(f"{_relative(path)} matched inline secret URL: {match.group(0)!r}")
        self.assertEqual([], violations)

    def test_git_does_not_track_local_skill_config_or_env(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", ".env", "skills/*/config.py", "config/wecom_smartsheet_sources.json"],
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual([], tracked, msg=f"Tracked secret-bearing files: {tracked}")


if __name__ == "__main__":
    unittest.main()
