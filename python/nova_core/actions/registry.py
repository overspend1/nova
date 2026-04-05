from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..bootstrap import (
    infer_bootstrap_spec_from_brief,
    materialize_bootstrap_files,
    validate_bootstrap_spec,
)
from ..config import CoreConfig
from ..memory_store import MemoryStore
from ..models import ActionKind, RiskLevel
from .cmd_control import run_shell_command, validate_command
from .computer_control import get_system_snapshot, list_processes, open_path
from .file_control import append_text_file, list_directory, read_text_file, write_text_file
from .web_search import duckduckgo_search


@dataclass(frozen=True)
class ToolRuntime:
    config: CoreConfig
    memory: MemoryStore


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    kind: ActionKind
    risk: RiskLevel
    requires_approval: bool
    handler: Callable[[dict[str, Any], ToolRuntime], dict[str, Any]]

    def declaration(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "risk": self.risk,
            "requiresApproval": self.requires_approval,
        }


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def declarations(self) -> list[dict[str, object]]:
        return [spec.declaration() for spec in self._specs.values()]

    def get(self, tool_name: str) -> ToolSpec | None:
        return self._specs.get(tool_name)

    def execute(
        self, tool_name: str, args: dict[str, Any], runtime: ToolRuntime
    ) -> dict[str, Any]:
        spec = self.get(tool_name)
        if spec is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        return spec.handler(args, runtime)


def build_tool_registry() -> ToolRegistry:
    specs = [
        ToolSpec(
            name="workspace.list_directory",
            description="List files and folders for a path.",
            kind="read",
            risk="low",
            requires_approval=False,
            handler=lambda args, _: list_directory(
                path=str(args.get("path", ".")),
                max_entries=int(args.get("maxEntries", 200)),
            ),
        ),
        ToolSpec(
            name="workspace.read_file",
            description="Read UTF-8 text from a file.",
            kind="read",
            risk="low",
            requires_approval=False,
            handler=lambda args, _: read_text_file(
                path=str(args.get("path", "")),
                max_chars=int(args.get("maxChars", 24_000)),
            ),
        ),
        ToolSpec(
            name="workspace.write_file",
            description="Write UTF-8 text to a file.",
            kind="write",
            risk="high",
            requires_approval=True,
            handler=lambda args, _: write_text_file(
                path=str(args.get("path", "")),
                content=str(args.get("content", "")),
                overwrite=bool(args.get("overwrite", True)),
                create_dirs=bool(args.get("createDirs", True)),
            ),
        ),
        ToolSpec(
            name="workspace.append_file",
            description="Append UTF-8 text to a file.",
            kind="write",
            risk="high",
            requires_approval=True,
            handler=lambda args, _: append_text_file(
                path=str(args.get("path", "")),
                content=str(args.get("content", "")),
                create_dirs=bool(args.get("createDirs", True)),
            ),
        ),
        ToolSpec(
            name="system.run_command",
            description="Run an allowlisted local command with arguments.",
            kind="system",
            risk="high",
            requires_approval=True,
            handler=_run_command_handler,
        ),
        ToolSpec(
            name="network.web_search",
            description="Search the web for documentation and references.",
            kind="network",
            risk="medium",
            requires_approval=True,
            handler=lambda args, _: duckduckgo_search(
                query=str(args.get("query", "")),
                limit=int(args.get("limit", 5)),
            ),
        ),
        ToolSpec(
            name="memory.search",
            description="Search persisted Nova memory records.",
            kind="memory",
            risk="low",
            requires_approval=False,
            handler=lambda args, runtime: {
                "results": [
                    item.model_dump()
                    for item in runtime.memory.search(
                        query=str(args.get("query", "")),
                        scope=str(args["scope"]) if "scope" in args else None,
                        limit=int(args.get("limit", 10)),
                    )
                ]
            },
        ),
        ToolSpec(
            name="memory.upsert",
            description="Persist a memory note into Nova's memory store.",
            kind="memory",
            risk="medium",
            requires_approval=True,
            handler=_memory_upsert_handler,
        ),
        ToolSpec(
            name="bootstrap.preview_spec",
            description="Infer and validate a project scaffold spec from a brief.",
            kind="bootstrap",
            risk="medium",
            requires_approval=False,
            handler=_bootstrap_preview_handler,
        ),
        ToolSpec(
            name="computer.system_snapshot",
            description="Collect machine/system snapshot information.",
            kind="read",
            risk="low",
            requires_approval=False,
            handler=lambda _args, _runtime: get_system_snapshot(),
        ),
        ToolSpec(
            name="computer.list_processes",
            description="List currently running processes.",
            kind="read",
            risk="low",
            requires_approval=False,
            handler=lambda args, _runtime: list_processes(
                limit=int(args.get("limit", 40))
            ),
        ),
        ToolSpec(
            name="computer.open_path",
            description="Open a local file or folder in the system shell.",
            kind="system",
            risk="high",
            requires_approval=True,
            handler=lambda args, _runtime: open_path(str(args.get("path", ""))),
        ),
    ]
    return ToolRegistry(specs)


def _run_command_handler(args: dict[str, Any], runtime: ToolRuntime) -> dict[str, Any]:
    command = str(args.get("command", "")).strip()
    if not command:
        raise ValueError("command is required.")
    command_args = [
        str(item) for item in (args.get("args") if isinstance(args.get("args"), list) else [])
    ]
    validate_command(command, allow_install=runtime.config.allow_install_commands)
    return run_shell_command(
        command=command,
        args=command_args,
        cwd=str(args["cwd"]) if "cwd" in args else None,
        timeout_seconds=int(args.get("timeoutSeconds", 90)),
    )


def _memory_upsert_handler(args: dict[str, Any], runtime: ToolRuntime) -> dict[str, Any]:
    from datetime import datetime, timezone

    from ..models import MemoryRecord

    now = datetime.now(timezone.utc).isoformat()
    record = runtime.memory.upsert(
        MemoryRecord(
            id=str(args.get("id", f"mem_{datetime.now(timezone.utc).timestamp():.0f}")),
            scope=str(args.get("scope", "general")),
            content=str(args.get("content", "")),
            tags=[str(tag) for tag in args.get("tags", [])]
            if isinstance(args.get("tags"), list)
            else [],
            createdAt=now,
            updatedAt=now,
        )
    )
    return {"record": record.model_dump()}


def _bootstrap_preview_handler(args: dict[str, Any], _runtime: ToolRuntime) -> dict[str, Any]:
    brief = str(args.get("brief", "")).strip()
    target = str(args.get("targetDirectory", "."))
    spec = infer_bootstrap_spec_from_brief(brief, target)
    errors = validate_bootstrap_spec(spec)
    files = materialize_bootstrap_files(spec)
    return {
        "valid": not errors,
        "errors": errors,
        "spec": spec.model_dump(),
        "filesPlanned": len(files),
        "sampleFiles": list(files.keys())[:10],
    }
