from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.a2a_ecommerce_demo.state_io import file_lock


class TestFileLockStale(unittest.TestCase):
    """Finding P2: state_io.file_lock should detect stale PID locks and recover."""

    def test_lock_creates_and_removes_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.json"
            target.write_text("{}", encoding="utf-8")
            lock_path = target.with_suffix(target.suffix + ".lock")

            with file_lock(target, timeout_seconds=2.0):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())

    def test_stale_lock_with_dead_pid_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.json"
            target.write_text("{}", encoding="utf-8")
            lock_path = target.with_suffix(target.suffix + ".lock")

            # Write a lock file with a PID that doesn't exist (use 0 which is never alive)
            lock_path.write_text("0", encoding="utf-8")

            # Should recover from stale lock instead of timing out
            with file_lock(target, timeout_seconds=2.0):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())

    def test_stale_lock_with_alive_pid_waits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.json"
            target.write_text("{}", encoding="utf-8")
            lock_path = target.with_suffix(target.suffix + ".lock")

            # Write a lock file with current PID (alive process)
            lock_path.write_text(str(os.getpid()), encoding="utf-8")

            # Should timeout because PID is alive (us)
            with self.assertRaises(TimeoutError):
                with file_lock(target, timeout_seconds=0.3):
                    pass

            # Cleanup
            lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
