from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..actions import ToolRegistry, ToolRuntime
from ..actions.cmd_control import run_shell_command, validate_command
from ..llm import LLMService
from ..models import (
    ActionStep,
    ApprovalDecision,
    ApprovalRequest,
    ExecutionAudit,
    ExecutionStepAudit,
    ExecutionStatus,
    Intent,
)


@dataclass
class ExecutorResult:
    audit: ExecutionAudit
    approval_requests: list[ApprovalRequest]
    assistant_summary: str | None


class AgentExecutor:
    def __init__(self, llm: LLMService, tools: ToolRegistry, runtime: ToolRuntime) -> None:
        self.llm = llm
        self.tools = tools
        self.runtime = runtime

    def execute(
        self,
        *,
        prompt: str,
        intent: Intent,
        steps: list[ActionStep],
        mode: ExecutionAudit.__annotations__["mode"],
        approvals: list[ApprovalDecision],
        run_id: str | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ExecutorResult:
        decision_map = {item.actionId: item for item in approvals}
        audits: list[ExecutionStepAudit] = []
        approval_requests: list[ApprovalRequest] = []
        status: ExecutionStatus = "completed"

        for step in steps:
            if is_cancelled and is_cancelled():
                audits.append(
                    ExecutionStepAudit(
                        stepId=step.id,
                        status="failed",
                        startedAt=utc_now(),
                        finishedAt=utc_now(),
                        details="Task cancelled before execution.",
                        error="cancelled",
                    )
                )
                status = "failed"
                break

            step_audit = ExecutionStepAudit(stepId=step.id, status="pending", startedAt=utc_now())

            if step.requiresApproval:
                decision = decision_map.get(step.id)
                if decision is None or not decision.approved:
                    step_audit.status = "rejected"
                    step_audit.finishedAt = utc_now()
                    step_audit.details = "Awaiting explicit approval."
                    audits.append(step_audit)
                    approval_requests.append(
                        ApprovalRequest(
                            actionId=step.id,
                            reason=step.description,
                            risk=step.risk,
                            requestedAt=utc_now(),
                        )
                    )
                    status = "blocked"
                    continue
                step_audit.status = "approved"

            if mode == "dry-run":
                step_audit.status = "succeeded"
                step_audit.finishedAt = utc_now()
                step_audit.details = step.dryRunPreview or "Dry-run simulation complete."
                audits.append(step_audit)
                continue

            try:
                outcome = self._execute_step(step)
                step_audit.status = "succeeded"
                step_audit.details = truncate_text(json.dumps(outcome, ensure_ascii=True))
            except Exception as error:  # noqa: BLE001
                step_audit.status = "failed"
                step_audit.error = str(error)
                step_audit.details = f"Step '{step.title}' failed."
                status = "failed"
            step_audit.finishedAt = utc_now()
            audits.append(step_audit)

        run_id_value = run_id or f"run_{uuid.uuid4().hex}"
        audit = ExecutionAudit(
            runId=run_id_value,
            intentId=intent.id,
            plannedAt=utc_now(),
            executedAt=utc_now(),
            mode=mode,
            status=status,
            approvals=approvals,
            steps=audits,
        )
        summary = self._summarize(prompt=prompt, intent=intent, audit=audit)
        return ExecutorResult(
            audit=audit,
            approval_requests=approval_requests,
            assistant_summary=summary,
        )

    def _execute_step(self, step: ActionStep) -> dict[str, object]:
        if step.toolName:
            return self.tools.execute(step.toolName, step.toolArgs, self.runtime)

        if step.command:
            validate_command(
                command=step.command,
                allow_install=self.runtime.config.allow_install_commands,
                network=step.kind == "network",
            )
            result = run_shell_command(
                command=step.command,
                args=step.args,
                cwd=step.workingDirectory,
            )
            if int(result.get("returnCode", 1)) != 0:
                raise RuntimeError(
                    f"Command failed: {step.command} {' '.join(step.args)}\n"
                    f"{result.get('output', '').strip()}"
                )
            return result

        return {"message": "No-op step completed."}

    def _summarize(self, *, prompt: str, intent: Intent, audit: ExecutionAudit) -> str | None:
        failures = [step for step in audit.steps if step.status == "failed"]
        blocked = [step for step in audit.steps if step.status == "rejected"]
        summary_seed = (
            f"Prompt: {prompt}\nIntent: {intent.taskType}\n"
            f"Status: {audit.status}\n"
            f"Failed steps: {len(failures)}\nBlocked steps: {len(blocked)}\n"
        )
        llm_result = self.llm.generate(
            prompt=(
                f"{summary_seed}\n"
                "Write a short operator summary including what worked and what needs approval."
            ),
            context_hint="execution-summary",
            temperature=0.2,
        )
        if llm_result.ok and llm_result.content.strip():
            return llm_result.content.strip()
        return (
            f"Execution {audit.status}. "
            f"Failed steps: {len(failures)}. Blocked steps awaiting approval: {len(blocked)}."
        )


def truncate_text(value: str, limit: int = 2200) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
