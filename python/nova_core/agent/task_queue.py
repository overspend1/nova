from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ..audit_log import AuditLog
from ..models import (
    AgentTaskCreateRequest,
    AgentTaskRecord,
    ApprovalDecision,
    ExecutionMode,
    TaskPriority,
)
from .executor import AgentExecutor
from .planner import AgentPlanner


PRIORITY_MAP: dict[TaskPriority, int] = {
    "critical": 0,
    "high": 1,
    "normal": 2,
    "low": 3,
}


@dataclass
class _TaskOptions:
    max_steps: int
    allow_replan: bool
    replan_attempts: int = 0


class AgentTaskQueue:
    def __init__(
        self,
        *,
        planner: AgentPlanner,
        executor: AgentExecutor,
        audit_log: AuditLog,
    ) -> None:
        self.planner = planner
        self.executor = executor
        self.audit_log = audit_log
        self._tasks: dict[str, AgentTaskRecord] = {}
        self._task_options: dict[str, _TaskOptions] = {}
        self._work_queue: queue.PriorityQueue[tuple[int, float, str]] = queue.PriorityQueue()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="nova-agent")
        self._worker.start()

    def create_task(self, request: AgentTaskCreateRequest) -> AgentTaskRecord:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        task = AgentTaskRecord(
            id=task_id,
            prompt=request.prompt,
            channel=request.channel,
            metadata=request.metadata,
            mode=request.mode,
            priority=request.priority,
            status="queued",
            createdAt=now,
            updatedAt=now,
            logs=["Task created and queued."],
            approvals=request.approvals,
        )
        with self._lock:
            self._tasks[task.id] = task
            self._task_options[task.id] = _TaskOptions(
                max_steps=request.maxSteps,
                allow_replan=request.allowReplan,
            )
            self._enqueue(task.id, request.priority)
        return task

    def get_task(self, task_id: str) -> AgentTaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.model_copy(deep=True) if task else None

    def list_tasks(self, limit: int = 50) -> list[AgentTaskRecord]:
        with self._lock:
            tasks = sorted(
                self._tasks.values(),
                key=lambda item: item.updatedAt,
                reverse=True,
            )
            return [task.model_copy(deep=True) for task in tasks[:limit]]

    def cancel_task(self, task_id: str) -> AgentTaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.status = "cancelled"
            task.updatedAt = utc_now()
            task.logs.append("Task cancelled by user.")
            return task.model_copy(deep=True)

    def approve_task(
        self,
        task_id: str,
        approvals: list[ApprovalDecision],
        *,
        mode: ExecutionMode,
    ) -> AgentTaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.status != "awaiting_approval":
                task.logs.append("Approval update ignored because task is not awaiting approval.")
                task.updatedAt = utc_now()
                return task.model_copy(deep=True)

            merged = {item.actionId: item for item in task.approvals}
            for item in approvals:
                merged[item.actionId] = item
            task.approvals = list(merged.values())
            task.mode = mode
            task.status = "queued"
            task.updatedAt = utc_now()
            task.logs.append("Approvals received. Task re-queued.")
            self._enqueue(task.id, task.priority)
            return task.model_copy(deep=True)

    def _enqueue(self, task_id: str, priority: TaskPriority) -> None:
        self._work_queue.put((PRIORITY_MAP[priority], time.time(), task_id))

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                _priority, _stamp, task_id = self._work_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._run_task(task_id)
            finally:
                self._work_queue.task_done()

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status == "cancelled":
                return
            task.status = "running"
            task.updatedAt = utc_now()
            task.logs.append("Worker started execution.")
            task_snapshot = task.model_copy(deep=True)
            options = self._task_options.get(task.id) or _TaskOptions(max_steps=8, allow_replan=True)

        if task_snapshot.intent is None or not task_snapshot.steps:
            plan = self.planner.plan(
                prompt=task_snapshot.prompt,
                channel=task_snapshot.channel,
                metadata=task_snapshot.metadata,
                max_steps=options.max_steps,
            )
            with self._lock:
                task = self._tasks.get(task_id)
                if task is None or task.status == "cancelled":
                    return
                task.intent = plan.intent
                task.route = plan.route
                task.steps = plan.steps
                task.updatedAt = utc_now()
                task.logs.append(f"Planning completed via {plan.source}.")
                if plan.rawModelOutput and plan.source == "heuristic":
                    task.logs.append("LLM planning failed; fallback heuristic plan was used.")
                task_snapshot = task.model_copy(deep=True)

        if task_snapshot.intent is None:
            with self._lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = "failed"
                    task.error = "Intent resolution failed."
                    task.updatedAt = utc_now()
            return

        result = self.executor.execute(
            prompt=task_snapshot.prompt,
            intent=task_snapshot.intent,
            steps=task_snapshot.steps,
            mode=task_snapshot.mode,
            approvals=task_snapshot.approvals,
            run_id=f"run_{uuid.uuid4().hex}",
            is_cancelled=lambda: self._is_cancelled(task_id),
        )

        if result.audit.status == "failed" and options.allow_replan and options.replan_attempts < 1:
            options.replan_attempts += 1
            replanned_steps = self.planner.replan(
                prompt=task_snapshot.prompt,
                intent=task_snapshot.intent,
                previous_steps=task_snapshot.steps,
                failure_summary="One or more steps failed during execution.",
                max_steps=options.max_steps,
            )
            with self._lock:
                task = self._tasks.get(task_id)
                if task is None or task.status == "cancelled":
                    return
                task.steps = replanned_steps
                task.updatedAt = utc_now()
                task.logs.append("Initial execution failed; generated one replan attempt.")
                task_snapshot = task.model_copy(deep=True)

            result = self.executor.execute(
                prompt=task_snapshot.prompt,
                intent=task_snapshot.intent,
                steps=task_snapshot.steps,
                mode=task_snapshot.mode,
                approvals=task_snapshot.approvals,
                run_id=f"run_{uuid.uuid4().hex}",
                is_cancelled=lambda: self._is_cancelled(task_id),
            )

        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if task.status == "cancelled":
                task.logs.append("Worker noticed cancellation after execution.")
                task.updatedAt = utc_now()
                return

            task.audit = result.audit
            task.assistantSummary = result.assistant_summary
            task.approvalRequests = result.approval_requests
            task.error = self._first_error(result.audit)
            task.updatedAt = utc_now()
            self.audit_log.append(result.audit)

            if result.audit.status == "blocked":
                task.status = "awaiting_approval"
                task.logs.append("Execution blocked pending approvals.")
            elif result.audit.status == "completed":
                task.status = "completed"
                task.logs.append("Execution completed.")
            else:
                task.status = "failed"
                task.logs.append("Execution failed.")

    def _is_cancelled(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            return bool(task and task.status == "cancelled")

    def _first_error(self, audit) -> str | None:
        for step in audit.steps:
            if step.error:
                return step.error
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
