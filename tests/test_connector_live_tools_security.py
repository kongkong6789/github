from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.a2a_ecommerce_demo.connector_live_tools import _assert_jackyun_skill_dir_trusted


class TestAssertJackyunSkillDirTrusted(unittest.TestCase):
    """Finding P1: constrain jackyun config import to trusted project skills directory."""

    def test_project_skills_dir_is_trusted(self) -> None:
        from src.a2a_ecommerce_demo.connector_registry import PROJECT_JACKYUN_SKILL_DIR

        if PROJECT_JACKYUN_SKILL_DIR.exists():
            _assert_jackyun_skill_dir_trusted(PROJECT_JACKYUN_SKILL_DIR)

    def test_subdirectory_of_project_skills_is_trusted(self) -> None:
        from src.a2a_ecommerce_demo.connector_registry import PROJECT_ROOT

        trusted_child = PROJECT_ROOT / "skills" / "jackyun_erp_readonly_connector_skill" / "helpers"
        if trusted_child.exists():
            _assert_jackyun_skill_dir_trusted(trusted_child)

    def test_arbitrary_temp_dir_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                _assert_jackyun_skill_dir_trusted(Path(tmp))

    def test_symlink_escape_from_skills_is_rejected(self) -> None:
        from src.a2a_ecommerce_demo.connector_registry import PROJECT_ROOT

        with tempfile.TemporaryDirectory() as outside:
            outside_skill = Path(outside) / "malicious_skill"
            outside_skill.mkdir()
            (outside_skill / "config.py").write_text("EVIL = True", encoding="utf-8")

            link = PROJECT_ROOT / "skills" / "_test_symlink_escape"
            try:
                link.symlink_to(outside_skill)
                with self.assertRaises(PermissionError):
                    _assert_jackyun_skill_dir_trusted(link)
            finally:
                if link.exists() or link.is_symlink():
                    link.unlink(missing_ok=True)

    def test_env_allowlisted_dir_is_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("A2A_TRUSTED_SKILL_DIRS")
            try:
                os.environ["A2A_TRUSTED_SKILL_DIRS"] = tmp
                _assert_jackyun_skill_dir_trusted(Path(tmp))
            finally:
                if old is None:
                    os.environ.pop("A2A_TRUSTED_SKILL_DIRS", None)
                else:
                    os.environ["A2A_TRUSTED_SKILL_DIRS"] = old


if __name__ == "__main__":
    unittest.main()
