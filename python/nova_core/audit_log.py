from __future__ import annotations

import json
from pathlib import Path

from .models import ExecutionAudit


class AuditLog:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def append(self, audit: ExecutionAudit) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit.model_dump()) + "\n")

    def list(self, limit: int = 100) -> list[ExecutionAudit]:
        if not self.file_path.exists():
            return []

        lines = [line.strip() for line in self.file_path.read_text("utf-8").splitlines()]
        lines = [line for line in lines if line]
        recent = lines[-limit:]
        recent.reverse()
        return [ExecutionAudit.model_validate_json(line) for line in recent]

