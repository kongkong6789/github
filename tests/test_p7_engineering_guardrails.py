from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class P7EngineeringGuardrailTests(unittest.TestCase):
    def test_root_env_is_gitignored_and_not_tracked(self) -> None:
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".env", gitignore)
        self.assertIn(".env.*", gitignore)
        self.assertIn("!.env.example", gitignore)

        result = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual("", result.stdout.strip())

    def test_sensitive_examples_do_not_contain_known_live_values(self) -> None:
        checked_files = [
            PROJECT_ROOT / ".env.example",
            PROJECT_ROOT / "tests" / "test_connector_registry.py",
            *sorted((PROJECT_ROOT / "skills" / "jackyun_erp_readonly_connector_skill").rglob("*.md")),
            *sorted((PROJECT_ROOT / "skills" / "jackyun_erp_readonly_connector_skill" / "tests").rglob("*.py")),
            PROJECT_ROOT / "skills" / "kingdee_erp_readonly_connector_skill" / "README.md",
        ]
        blocked_literals = [
            "37811901",
            "6be140cc09f441978a1ff6727367dda2",
            "159.75.104.61",
            "65405d0ec432ee",
            "KINGDEE_USERNAME=Administrator",
        ]

        violations: list[str] = []
        for path in checked_files:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for literal in blocked_literals:
                if literal in text:
                    violations.append(f"{_relative(path)} contains {literal}")

        self.assertEqual([], violations)

    def test_skill_library_runtime_dirs_exclude_transient_and_write_artifacts(self) -> None:
        banned_names = {".env", "config.py", ".pytest_cache", "__pycache__", "data", "dist", "output"}
        banned_suffixes = {".zip", ".pyc", ".pyo"}
        banned_prefixes = {"_tmp", "tmp_"}

        violations: list[str] = []
        skills_dir = PROJECT_ROOT / "skills"
        if skills_dir.exists():
            for path in sorted(skills_dir.rglob("*")):
                name = path.name
                if name in banned_names:
                    violations.append(_relative(path))
                    continue
                if path.is_file() and path.suffix.lower() in banned_suffixes:
                    violations.append(_relative(path))
                    continue
                if any(name.startswith(prefix) for prefix in banned_prefixes):
                    violations.append(_relative(path))

        self.assertEqual([], violations)

    def test_skill_library_files_are_not_world_writable(self) -> None:
        violations: list[str] = []
        skills_dir = PROJECT_ROOT / "skills"
        if skills_dir.exists():
            for path in sorted(skills_dir.rglob("*")):
                try:
                    mode = path.stat().st_mode
                except OSError:
                    continue
                if mode & 0o002:
                    violations.append(_relative(path))

        self.assertEqual([], violations)

    def test_operational_scripts_have_windows_and_macos_wrappers(self) -> None:
        sh_stems = {path.stem for path in SCRIPTS_DIR.glob("*.sh")}
        ps1_stems = {path.stem for path in SCRIPTS_DIR.glob("*.ps1")}

        self.assertEqual([], sorted(sh_stems - ps1_stems))
        self.assertEqual([], sorted(ps1_stems - sh_stems))

    def test_markdown_docs_do_not_keep_machine_specific_windows_path_examples(self) -> None:
        markdown_files = [
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "TODO.md",
            *sorted((PROJECT_ROOT / "docs").rglob("*.md")),
        ]
        blocked_literals = [
            "D:\\A2A",
            "C:\\Users",
            "C:\\Program Files\\nodejs",
            ".venv\\Scripts",
            "powershell.exe",
        ]

        violations: list[str] = []
        for path in markdown_files:
            text = path.read_text(encoding="utf-8")
            for literal in blocked_literals:
                if literal in text:
                    violations.append(f"{_relative(path)} contains {literal}")

        self.assertEqual([], violations)

    def test_frontend_verification_has_a_single_dynamic_test_entrypoint(self) -> None:
        verify_script = SCRIPTS_DIR / "verify_frontend.sh"
        verify_ps1_script = SCRIPTS_DIR / "verify_frontend.ps1"
        verify_all_script = SCRIPTS_DIR / "verify_all.sh"
        package_json = PROJECT_ROOT / "agent-chat-ui" / "package.json"

        self.assertTrue(verify_script.exists())
        self.assertTrue(verify_ps1_script.exists())
        self.assertTrue(verify_all_script.exists())

        verify_text = verify_script.read_text(encoding="utf-8")
        verify_ps1_text = verify_ps1_script.read_text(encoding="utf-8")
        self.assertIn("find", verify_text)
        self.assertIn("*.test.ts", verify_text)
        self.assertIn("*.test.tsx", verify_text)
        self.assertIn("node --test", verify_text)
        self.assertIn("tsc --noEmit", verify_text)
        self.assertIn("npm run build", verify_text)
        self.assertNotIn("mapfile", verify_text)
        self.assertNotIn("pnpm run build", verify_text)
        self.assertIn("npm run build", verify_ps1_text)
        self.assertNotIn("pnpm run build", verify_ps1_text)

        package = json.loads(package_json.read_text(encoding="utf-8"))
        self.assertEqual("../scripts/verify_frontend.sh --unit-only", package["scripts"]["test"])
        self.assertEqual("../scripts/verify_frontend.sh", package["scripts"]["verify"])

    def test_common_sh_dotenv_loader_does_not_execute_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "pwned"
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        f"MALICIOUS=$(touch {marker})",
                        "BASE_VALUE=hello",
                        "EXPANDED=${BASE_VALUE}-world",
                    ],
                ),
                encoding="utf-8",
            )
            script = (
                "source scripts/common.sh; "
                f"load_dotenv {env_path}; "
                "printf '%s\\n' \"$MALICIOUS\" \"$EXPANDED\""
            )
            result = subprocess.run(
                ["bash", "-c", script],
                cwd=PROJECT_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertFalse(marker.exists())
            self.assertIn("$(touch", result.stdout)
            self.assertIn("hello-world", result.stdout)

    def test_query_fact_layer_script_rejects_non_integer_limit_without_executing_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "pwned"
            env = os.environ.copy()
            env["A2A_DATA_DIR"] = temp_dir
            env["A2A_WAREHOUSE_DIR"] = str(Path(temp_dir) / "warehouse")
            result = subprocess.run(
                [
                    "bash",
                    "scripts/query_fact_layer.sh",
                    "--sql",
                    "SELECT 1 AS ok",
                    "--limit",
                    f"1; touch {marker}",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
