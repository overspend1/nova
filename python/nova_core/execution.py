from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .models import ActionStep, ApprovalDecision, ExecutionAudit, ExecutionStepAudit


SAFE_BASE_COMMANDS = {"python", "python3", "node", "pnpm", "npm", "corepack", "git"}
SAFE_INSTALL_COMMANDS = {"pnpm", "npm", "corepack"}
SAFE_NETWORK_COMMANDS = {"curl", "wget"}


def execute_plan(
    *,
    run_id: str,
    intent_id: str,
    mode: ExecutionAudit.__annotations__["mode"],
    steps: list[ActionStep],
    approvals: list[ApprovalDecision],
    allow_install_commands: bool,
) -> ExecutionAudit:
    approval_map = {decision.actionId: decision for decision in approvals}
    step_audits: list[ExecutionStepAudit] = []
    status: ExecutionAudit.__annotations__["status"] = "completed"

    for step in steps:
        step_audit = ExecutionStepAudit(
            stepId=step.id,
            status="pending",
            startedAt=utc_now(),
        )

        if step.requiresApproval:
            decision = approval_map.get(step.id)
            if not decision or not decision.approved:
                step_audit.status = "rejected"
                step_audit.finishedAt = utc_now()
                step_audit.details = "Blocked: explicit approval missing."
                step_audits.append(step_audit)
                status = "blocked"
                continue
            step_audit.status = "approved"

        if mode == "dry-run":
            step_audit.status = "succeeded"
            step_audit.finishedAt = utc_now()
            step_audit.details = step.dryRunPreview or "Dry run completed."
            step_audits.append(step_audit)
            continue

        if step.kind == "install" and not allow_install_commands:
            step_audit.status = "failed"
            step_audit.finishedAt = utc_now()
            step_audit.error = "Install commands are disabled by NOVA_ALLOW_INSTALL_COMMANDS."
            step_audits.append(step_audit)
            status = "failed"
            continue

        if not is_step_command_allowed(step, allow_install_commands):
            step_audit.status = "failed"
            step_audit.finishedAt = utc_now()
            step_audit.error = (
                f"Command '{step.command or 'none'}' is not allowed for step kind '{step.kind}'."
            )
            step_audits.append(step_audit)
            status = "failed"
            continue

        if step.command:
            result = run_command(step.command, step.args, step.workingDirectory)
            if result.returncode == 0:
                step_audit.status = "succeeded"
                step_audit.details = result.output
            else:
                step_audit.status = "failed"
                step_audit.details = result.output
                step_audit.error = f"Command exited with code {result.returncode}."
                status = "failed"
        else:
            step_audit.status = "succeeded"
            step_audit.details = "No command to execute; step acknowledged."

        step_audit.finishedAt = utc_now()
        step_audits.append(step_audit)

    return ExecutionAudit(
        runId=run_id,
        intentId=intent_id,
        plannedAt=utc_now(),
        executedAt=utc_now(),
        mode=mode,
        status=status,
        approvals=approvals,
        steps=step_audits,
    )


def is_step_command_allowed(step: ActionStep, allow_install_commands: bool) -> bool:
    if not step.command:
        return True

    base = normalize_command_name(step.command)
    if step.kind == "install":
        return allow_install_commands and base in SAFE_INSTALL_COMMANDS
    if step.kind == "git":
        return base == "git"
    if step.kind == "network":
        return base in SAFE_NETWORK_COMMANDS
    return base in SAFE_BASE_COMMANDS


def normalize_command_name(command: str) -> str:
    name = Path(command.strip().lower()).stem
    if name.endswith(".exe"):
        name = name[:-4]
    return name


class CommandResult:
    def __init__(self, returncode: int, output: str) -> None:
        self.returncode = returncode
        self.output = output


def run_command(
    command: str,
    args: list[str] | None = None,
    working_directory: str | None = None,
) -> CommandResult:
    cmd = [command, *(args or [])]
    try:
        completed = subprocess.run(
            cmd,
            cwd=os.path.abspath(working_directory) if working_directory else None,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        ).strip()
        return CommandResult(completed.returncode, output)
    except Exception as error:  # noqa: BLE001
        return CommandResult(1, str(error))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

