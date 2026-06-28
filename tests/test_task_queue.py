from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path


class DurableTaskQueueTests(unittest.TestCase):
    def test_enqueue_claim_heartbeat_complete_and_events_are_transactional(self) -> None:
        from src.a2a_ecommerce_demo.task_queue import TaskQueue

        now = datetime(2026, 5, 20, 9, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            queue = TaskQueue(Path(tmp) / "tasks.sqlite")
            first = queue.enqueue(
                goal="导入 raw 资料并同步知识库",
                requested_by="test",
                idempotency_key="raw-ingest:unove",
            )
            duplicate = queue.enqueue(
                goal="导入 raw 资料并同步知识库",
                requested_by="test",
                idempotency_key="raw-ingest:unove",
            )

            self.assertEqual(first["task_id"], duplicate["task_id"])
            self.assertEqual(1, queue.count_tasks())

            claimed = queue.claim_next(worker_id="worker-a", lease_seconds=30, now=now)
            self.assertIsNotNone(claimed)
            assert claimed is not None
            self.assertEqual(first["task_id"], claimed["task_id"])
            self.assertEqual("running", queue.get_task(first["task_id"])["status"])
            self.assertIsNone(queue.claim_next(worker_id="worker-b", lease_seconds=30, now=now + timedelta(seconds=1)))

            heartbeat = queue.heartbeat(
                first["task_id"],
                worker_id="worker-a",
                lease_seconds=60,
                now=now + timedelta(seconds=10),
            )
            self.assertTrue(heartbeat["ok"])
            self.assertGreater(heartbeat["expires_at"], claimed["expires_at"])

            completed = queue.complete(
                first["task_id"],
                worker_id="worker-a",
                summary="工作流完成",
                now=now + timedelta(seconds=20),
            )
            self.assertEqual("success", completed["status"])
            self.assertIsNone(queue.claim_next(worker_id="worker-c", lease_seconds=30, now=now + timedelta(seconds=21)))

            events = [event["event_type"] for event in queue.list_events(first["task_id"])]
            self.assertEqual(["task_enqueued", "task_claimed", "task_heartbeat", "task_completed"], events)

    def test_crash_reclaim_expires_claim_and_allows_new_worker(self) -> None:
        from src.a2a_ecommerce_demo.task_queue import TaskQueue

        now = datetime(2026, 5, 20, 10, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            queue = TaskQueue(Path(tmp) / "tasks.sqlite")
            task = queue.enqueue(goal="同步 LightRAG", requested_by="test", idempotency_key="lightrag:sync")
            first_claim = queue.claim_next(worker_id="worker-a", lease_seconds=5, now=now)
            self.assertIsNotNone(first_claim)
            assert first_claim is not None
            self.assertEqual(task["task_id"], first_claim["task_id"])

            reclaimed = queue.reclaim_expired(now=now + timedelta(seconds=6))

            self.assertEqual([task["task_id"]], [item["task_id"] for item in reclaimed])
            self.assertEqual("recoverable", queue.get_task(task["task_id"])["status"])
            second_claim = queue.claim_next(worker_id="worker-b", lease_seconds=30, now=now + timedelta(seconds=7))
            self.assertIsNotNone(second_claim)
            assert second_claim is not None
            self.assertEqual(task["task_id"], second_claim["task_id"])
            self.assertEqual("worker-b", second_claim["worker_id"])

            events = [event["event_type"] for event in queue.list_events(task["task_id"])]
            self.assertIn("task_reclaimed", events)

    def test_fail_retry_cancel_and_terminal_state_rules(self) -> None:
        from src.a2a_ecommerce_demo.task_queue import TaskQueue

        now = datetime(2026, 5, 20, 11, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            queue = TaskQueue(Path(tmp) / "tasks.sqlite")
            task = queue.enqueue(
                goal="处理大 Excel",
                requested_by="test",
                idempotency_key="excel:large",
                max_attempts=2,
            )
            first_claim = queue.claim_next(worker_id="worker-a", lease_seconds=30, now=now)
            self.assertIsNotNone(first_claim)
            assert first_claim is not None
            self.assertEqual(task["task_id"], first_claim["task_id"])

            retry = queue.fail(
                task["task_id"],
                worker_id="worker-a",
                step_name="large_excel_pipeline",
                reason="temporary file lock",
                retryable=True,
                now=now + timedelta(seconds=5),
            )
            self.assertEqual("queued", retry["status"])
            self.assertEqual(1, len(queue.list_retries(task["task_id"])))

            second_claim = queue.claim_next(worker_id="worker-b", lease_seconds=30, now=now + timedelta(seconds=6))
            self.assertIsNotNone(second_claim)
            assert second_claim is not None
            self.assertEqual(task["task_id"], second_claim["task_id"])
            failed = queue.fail(
                task["task_id"],
                worker_id="worker-b",
                step_name="large_excel_pipeline",
                reason="same failure after retry",
                retryable=True,
                now=now + timedelta(seconds=10),
            )
            self.assertEqual("failed", failed["status"])
            self.assertIsNone(queue.claim_next(worker_id="worker-c", lease_seconds=30, now=now + timedelta(seconds=11)))

            cancelled_task = queue.enqueue(goal="待取消任务", requested_by="test", idempotency_key="cancel:queued")
            cancelled = queue.cancel(cancelled_task["task_id"], requested_by="test", now=now + timedelta(seconds=12))
            self.assertEqual("cancelled", cancelled["status"])
            self.assertIsNone(queue.claim_next(worker_id="worker-d", lease_seconds=30, now=now + timedelta(seconds=13)))

    def test_concurrent_claim_only_assigns_task_once(self) -> None:
        from src.a2a_ecommerce_demo.task_queue import TaskQueue

        now = datetime(2026, 5, 20, 12, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            queue = TaskQueue(Path(tmp) / "tasks.sqlite")
            task = queue.enqueue(goal="并发 claim 测试", requested_by="test", idempotency_key="claim:once")
            results: list[dict[str, object] | None] = []
            lock = threading.Lock()

            def claim(worker_id: str) -> None:
                result = queue.claim_next(worker_id=worker_id, lease_seconds=30, now=now)
                with lock:
                    results.append(result)

            threads = [threading.Thread(target=claim, args=(f"worker-{index}",)) for index in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            claimed = [result for result in results if result is not None]
            self.assertEqual(1, len(claimed))
            self.assertEqual(task["task_id"], claimed[0]["task_id"])
            self.assertEqual("running", queue.get_task(task["task_id"])["status"])

    def test_p17_handoff_and_qa_gate_events_are_standardized(self) -> None:
        from src.a2a_ecommerce_demo.task_queue import P17_TASK_EVENT_TYPES, TaskQueue

        with tempfile.TemporaryDirectory() as tmp:
            queue = TaskQueue(Path(tmp) / "tasks.sqlite")
            task = queue.enqueue(goal="P17 handoff qa", requested_by="test", idempotency_key="p17:events")

            handoff = queue.append_handoff_event(
                task["task_id"],
                from_agent="data_agent",
                to_agent="inventory_agent",
                summary="数据归并完成，交给库存复盘。",
                evidence_paths=["wiki/datasets/unove.md"],
                next_actions=["检查断货风险"],
            )
            qa_fail = queue.append_qa_gate_event(
                task["task_id"],
                verdict="FAIL",
                checked_by="qa_agent",
                summary="缺少 ERP 查询时间。",
                evidence_paths=["data/reports/unove.md"],
                retry_count=2,
                next_actions=["补 query_erp_live_snapshot 证据"],
            )

            self.assertIn("handoff.created", P17_TASK_EVENT_TYPES)
            self.assertIn("qa.fail", P17_TASK_EVENT_TYPES)
            self.assertEqual("handoff.created", handoff["event_type"])
            self.assertEqual("data_agent", handoff["payload"]["from_agent"])
            self.assertEqual("inventory_agent", handoff["payload"]["to_agent"])
            self.assertEqual("qa.fail", qa_fail["event_type"])
            self.assertEqual("FAIL", qa_fail["payload"]["verdict"])
            self.assertEqual(2, qa_fail["payload"]["retry_count"])

            events = [event["event_type"] for event in queue.list_events(task["task_id"])]
            self.assertEqual(["task_enqueued", "handoff.created", "qa.fail"], events)

            with self.assertRaises(ValueError):
                queue.append_qa_gate_event(task["task_id"], verdict="MAYBE")


if __name__ == "__main__":
    unittest.main()
