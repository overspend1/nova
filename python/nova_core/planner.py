from __future__ import annotations

import re
import uuid

from .models import (
    ActionStep,
    Complexity,
    Intent,
    ModelRouteDecision,
)


def route_model(intent: Intent) -> ModelRouteDecision:
    complexity = infer_complexity(intent.normalizedInput)

    if intent.taskType in {"retrieval", "command"}:
        return ModelRouteDecision(
            taskType=intent.taskType,
            complexity=complexity,
            route="local",
            reason="Low-latency local route for retrieval/command tasks.",
        )

    if intent.taskType in {"coding", "planning"}:
        return ModelRouteDecision(
            taskType=intent.taskType,
            complexity=complexity,
            route="cloud" if complexity == "high" else "local",
            reason="Coding/planning route selected by complexity policy.",
        )

    if intent.taskType == "bootstrap":
        return ModelRouteDecision(
            taskType=intent.taskType,
            complexity=complexity,
            route="cloud",
            reason="Bootstrap tasks use cloud route for richer planning.",
        )

    return ModelRouteDecision(
        taskType=intent.taskType,
        complexity=complexity,
        route="local",
        reason="Fallback local route for unknown task.",
    )


def create_action_plan(intent: Intent) -> list[ActionStep]:
    if intent.taskType == "retrieval":
        return [
            _step(
                "Read workspace context",
                "Inspect indexed memory and repository context to answer the request.",
                kind="read",
                risk="low",
                requires_approval=False,
            ),
            _step(
                "Search memory store",
                "Run semantic memory search for relevant notes and prior decisions.",
                kind="memory",
                risk="low",
                requires_approval=False,
            ),
        ]

    if intent.taskType == "planning":
        return [
            _step(
                "Analyze constraints",
                "Identify project constraints and acceptance criteria.",
                kind="read",
                risk="low",
                requires_approval=False,
            ),
            _step(
                "Draft implementation approach",
                "Generate implementation roadmap and execution sequencing.",
                kind="read",
                risk="low",
                requires_approval=False,
            ),
        ]

    if intent.taskType == "coding":
        return [
            _step(
                "Inspect target code",
                "Read project files and identify exact edit scope.",
                kind="read",
                risk="low",
                requires_approval=False,
            ),
            _step(
                "Apply code changes",
                "Modify files required by the task. Approval required before any write.",
                kind="write",
                risk="high",
                requires_approval=True,
            ),
            _step(
                "Run validation",
                "Execute tests/lint checks relevant to modified modules.",
                kind="system",
                risk="medium",
                requires_approval=True,
                command="python",
                args=["--version"],
                dry_run_preview="python --version",
            ),
        ]

    if intent.taskType == "bootstrap":
        return [
            _step(
                "Generate scaffold spec",
                "Create structured bootstrap spec from user brief.",
                kind="bootstrap",
                risk="medium",
                requires_approval=False,
            ),
            _step(
                "Write scaffold files",
                "Create workspace files for web/api/worker starter.",
                kind="write",
                risk="high",
                requires_approval=True,
            ),
            _step(
                "Install dependencies",
                "Install generated project dependencies.",
                kind="install",
                risk="high",
                requires_approval=True,
                command="pnpm",
                args=["install"],
                dry_run_preview="pnpm install",
            ),
        ]

    if intent.taskType == "command":
        inferred = infer_command_from_text(intent.normalizedInput)
        if inferred:
            command, args = inferred
            preview = " ".join([command, *args]).strip()
            return [
                _step(
                    "Execute command",
                    "Run the requested local command after explicit approval.",
                    kind="system",
                    risk="high",
                    requires_approval=True,
                    command=command,
                    args=args,
                    dry_run_preview=preview,
                )
            ]
        return [
            _step(
                "Dry-run shell command",
                "Render command preview and explain impact.",
                kind="system",
                risk="medium",
                requires_approval=True,
            )
        ]

    return [
        _step(
            "Clarify request through context",
            "Use local context retrieval and ask for safer next action.",
            kind="read",
            risk="low",
            requires_approval=False,
        )
    ]


def infer_complexity(normalized_text: str) -> Complexity:
    length = len(normalized_text)
    if length < 80:
        return "low"
    if length < 280:
        return "medium"
    return "high"


def infer_command_from_text(text: str) -> tuple[str, list[str]] | None:
    compact = " ".join(text.strip().split())
    if not compact:
        return None

    app_aliases = {
        "firefox": "firefox",
        "chrome": "chrome",
        "google chrome": "chrome",
        "edge": "msedge",
        "microsoft edge": "msedge",
        "notepad": "notepad",
        "vscode": "code",
        "visual studio code": "code",
        "code": "code",
        "explorer": "explorer",
        "file explorer": "explorer",
    }

    for alias, command in app_aliases.items():
        if compact == alias:
            return command, []
        if compact.startswith(f"open {alias}") or compact.startswith(f"launch {alias}"):
            return command, []

    run_match = re.match(r"^(?:run|execute)\s+([a-z0-9._-]+)(?:\s+(.*))?$", compact)
    if run_match:
        command = run_match.group(1)
        rest = (run_match.group(2) or "").strip()
        args = rest.split() if rest else []
        return command, args
    return None


def _step(
    title: str,
    description: str,
    *,
    kind: ActionStep.__annotations__["kind"],
    risk: ActionStep.__annotations__["risk"],
    requires_approval: bool,
    command: str | None = None,
    args: list[str] | None = None,
    dry_run_preview: str | None = None,
) -> ActionStep:
    return ActionStep(
        id=f"step_{uuid.uuid4().hex[:8]}",
        title=title,
        description=description,
        kind=kind,
        risk=risk,
        requiresApproval=requires_approval,
        command=command,
        args=args or [],
        dryRunPreview=dry_run_preview,
    )
