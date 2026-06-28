from __future__ import annotations

import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path


class RecoverableWorkflowQueueTests(unittest.TestCase):
    def test_recovers_queued_and_running_tasks_from_disk_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["A2A_TASK_DIR"] = str(Path(tmp) / "tasks")

            import src.a2a_ecommerce_demo.task_delegation_tools as task_tools

            task_tools = importlib.reload(task_tools)
            calls: list[str] = []

            def fake_runner(task_id: str, limit: int = 10) -> str:
                calls.append(f"{task_id}:{limit}")
                task = task_tools._load_task(task_id)
                task["status"] = "success"
                task["updated_at"] = task_tools._now()
                task_tools._save_task(task)
                return json.dumps(task)

            setattr(task_tools, "_WORKFLOW_RUNNER", fake_runner)
            queued = json.loads(task_tools.create_workflow_task("我刚放了 raw 资料，帮我整理入库", requested_by="test"))
            running = json.loads(task_tools.create_workflow_task("我刚放了 raw 资料，帮我同步知识库", requested_by="test"))
            ignored = json.loads(task_tools.create_workflow_task("已完成任务", requested_by="test"))

            queued_task = task_tools._load_task(queued["task_id"])
            queued_task["status"] = "queued"
            task_tools._save_task(queued_task)

            running_task = task_tools._load_task(running["task_id"])
            running_task["status"] = "running"
            task_tools._save_task(running_task)

            ignored_task = task_tools._load_task(ignored["task_id"])
            ignored_task["status"] = "success"
            task_tools._save_task(ignored_task)

            result = json.loads(task_tools.recover_workflow_queue(limit=7))
            duplicate_result = json.loads(task_tools.recover_workflow_queue(limit=7))

            deadline = time.time() + 2
            while len(calls) < 2 and time.time() < deadline:
                time.sleep(0.05)

            self.assertEqual("success", result["status"])
            self.assertEqual(2, result["recovered"])
            self.assertEqual(0, duplicate_result["recovered"])
            self.assertCountEqual(
                [f"{queued['task_id']}:7", f"{running['task_id']}:7"],
                calls,
            )
            self.assertEqual("success", task_tools._load_task(queued["task_id"])["status"])
            recovered_running = task_tools._load_task(running["task_id"])
            self.assertEqual("success", recovered_running["status"])
            self.assertTrue(recovered_running["recovered_from_interrupted_run"])

    def test_cancel_queued_task_uses_cancelled_terminal_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["A2A_TASK_DIR"] = str(Path(tmp) / "tasks")
            os.environ["A2A_TASK_QUEUE_DB"] = str(Path(tmp) / "tasks" / "tasks.sqlite")

            import src.a2a_ecommerce_demo.task_delegation_tools as task_tools

            task_tools = importlib.reload(task_tools)
            created = json.loads(task_tools.create_workflow_task("我刚放了 raw 资料，帮我整理入库", requested_by="test"))
            task = task_tools._load_task(created["task_id"])
            task["status"] = "queued"
            task_tools._save_task(task)

            result = json.loads(task_tools.cancel_workflow_task(created["task_id"]))

            self.assertEqual("cancelled", result["status"])
            self.assertEqual("cancelled", task_tools._load_task(created["task_id"])["status"])
            self.assertEqual("cancelled", task_tools._task_queue().get_task(created["task_id"])["status"])

    def test_json_task_creation_is_mirrored_to_durable_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["A2A_TASK_DIR"] = str(Path(tmp) / "tasks")
            os.environ["A2A_TASK_QUEUE_DB"] = str(Path(tmp) / "tasks" / "tasks.sqlite")

            import src.a2a_ecommerce_demo.task_delegation_tools as task_tools

            task_tools = importlib.reload(task_tools)
            created = json.loads(task_tools.create_workflow_task("我刚放了 raw 资料，帮我整理入库", requested_by="test"))
            task = task_tools._load_task(created["task_id"])
            durable = task_tools._task_queue().get_task(created["task_id"])
            listed = json.loads(task_tools.list_workflow_tasks(limit=10))
            status = json.loads(task_tools.get_workflow_task_status(created["task_id"]))

            self.assertTrue(task["idempotency_key"].startswith("workflow:test:"))
            self.assertEqual(created["task_id"], durable["task_id"])
            self.assertEqual("created", durable["status"])
            self.assertEqual("sqlite+json", next(item for item in listed["tasks"] if item["task_id"] == created["task_id"])["storage"])
            self.assertEqual("created", status["durable_queue"]["status"])

    def test_list_and_status_support_sqlite_only_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["A2A_TASK_DIR"] = str(Path(tmp) / "tasks")
            os.environ["A2A_TASK_QUEUE_DB"] = str(Path(tmp) / "tasks" / "tasks.sqlite")

            import src.a2a_ecommerce_demo.task_delegation_tools as task_tools

            task_tools = importlib.reload(task_tools)
            task_tools._task_queue().enqueue(
                task_id="sqlite-only-task",
                goal="队列中尚未导出 JSON 的任务",
                requested_by="test",
                idempotency_key="sqlite-only",
            )

            listed = json.loads(task_tools.list_workflow_tasks(limit=10))
            status = json.loads(task_tools.get_workflow_task_status("sqlite-only-task"))

            sqlite_item = next(item for item in listed["tasks"] if item["task_id"] == "sqlite-only-task")
            self.assertEqual("sqlite", sqlite_item["storage"])
            self.assertEqual("queued", status["status"])
            self.assertEqual("sqlite", status["storage"])


if __name__ == "__main__":
    unittest.main()
