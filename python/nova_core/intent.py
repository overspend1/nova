from __future__ import annotations

import uuid

from .models import Intent, IntentChannel, TaskType


TASK_KEYWORDS: dict[TaskType, list[str]] = {
    "retrieval": ["find", "search", "where", "explain", "read"],
    "planning": ["plan", "design", "architecture", "roadmap"],
    "coding": ["fix", "refactor", "implement", "build", "code"],
    "bootstrap": ["bootstrap", "scaffold", "new project", "starter", "generate project"],
    "command": ["run", "execute", "open", "install", "deploy"],
    "unknown": [],
}


def parse_intent(
    text: str,
    channel: IntentChannel = "text",
    metadata: dict[str, str] | None = None,
) -> Intent:
    normalized = text.strip().lower()
    task_type = infer_task_type(normalized)
    return Intent(
        id=uuid.uuid4().hex,
        rawInput=text,
        normalizedInput=normalized,
        channel=channel,
        taskType=task_type,
        confidence=0.45 if task_type == "unknown" else 0.85,
        metadata=metadata or {},
    )


def infer_task_type(text: str) -> TaskType:
    for task_type, words in TASK_KEYWORDS.items():
        if any(word in text for word in words):
            return task_type
    return "unknown"

