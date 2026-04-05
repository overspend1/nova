from __future__ import annotations


CAPABILITIES: list[dict[str, object]] = [
    {
        "name": "assistant.respond",
        "description": "Generates natural language responses using the configured AI model.",
        "requiresApproval": False,
        "risk": "low",
    },
    {
        "name": "intent.parse",
        "description": "Classifies user input into retrieval/planning/coding/bootstrap/command.",
        "requiresApproval": False,
        "risk": "low",
    },
    {
        "name": "actions.plan",
        "description": "Builds a dry-run, risk-labeled step plan from natural language.",
        "requiresApproval": False,
        "risk": "low",
    },
    {
        "name": "actions.execute",
        "description": "Executes only approved steps with audit logging and command allowlists.",
        "requiresApproval": True,
        "risk": "high",
    },
    {
        "name": "agent.task.create",
        "description": "Queues an autonomous planner/executor task with retry/replan behavior.",
        "requiresApproval": True,
        "risk": "high",
    },
    {
        "name": "agent.task.approve",
        "description": "Applies explicit approvals to a blocked task and resumes execution.",
        "requiresApproval": True,
        "risk": "high",
    },
    {
        "name": "agent.task.list",
        "description": "Lists queued/running/completed/blocked autonomous tasks.",
        "requiresApproval": False,
        "risk": "low",
    },
    {
        "name": "bootstrap.create",
        "description": "Generates a full TypeScript monorepo scaffold (web/api/worker).",
        "requiresApproval": True,
        "risk": "high",
    },
    {
        "name": "memory.search",
        "description": "Searches persistent notes and profile workspace index.",
        "requiresApproval": False,
        "risk": "low",
    },
    {
        "name": "memory.upsert",
        "description": "Persists developer memory records.",
        "requiresApproval": True,
        "risk": "medium",
    },
    {
        "name": "memory.context",
        "description": "Configures indexed/opt-out paths and optionally refreshes file index.",
        "requiresApproval": True,
        "risk": "medium",
    },
    {
        "name": "audit.timeline",
        "description": "Retrieves immutable run history for plan/approval/execution traceability.",
        "requiresApproval": False,
        "risk": "low",
    },
    {
        "name": "meta.model",
        "description": "Returns active AI model/provider configuration.",
        "requiresApproval": False,
        "risk": "low",
    },
]


def list_capabilities() -> list[dict[str, object]]:
    return CAPABILITIES
