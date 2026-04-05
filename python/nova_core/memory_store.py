from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import MemoryRecord, WorkspaceContext, WorkspaceIndexHit

DEFAULT_EXCLUDES = [
    ".git",
    "node_modules",
    ".next",
    "dist",
    "bin",
    "obj",
    "AppData",
    "Program Files",
    "ProgramData",
    "Windows",
    "$Recycle.Bin",
]

DEFAULT_BINARY_EXTENSIONS = {
    ".7z",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ttf",
    ".woff",
    ".woff2",
    ".zip",
}


@dataclass
class WorkspaceIndex:
    generatedAt: str
    profileRoot: str
    files: list[WorkspaceIndexHit]


class MemoryStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.records_file = base_path / "records.json"
        self.context_file = base_path / "workspace-context.json"
        self.index_file = base_path / "workspace-index.json"

    def upsert(self, record: MemoryRecord) -> MemoryRecord:
        records = self._read_records()
        now = utc_now()

        for existing in records:
            if existing.id == record.id:
                existing.content = record.content
                existing.scope = record.scope
                existing.tags = record.tags
                existing.updatedAt = now
                self._write_records(records)
                return existing

        created = MemoryRecord(
            id=record.id,
            scope=record.scope,
            content=record.content,
            tags=record.tags,
            createdAt=record.createdAt or now,
            updatedAt=now,
        )
        records.append(created)
        self._write_records(records)
        return created

    def search(self, query: str, scope: str | None = None, limit: int = 10) -> list[MemoryRecord]:
        query_tokens = tokenize(query)
        records = self._read_records()
        if scope:
            records = [record for record in records if record.scope == scope]

        scored = [
            (record, score_memory_record(record.content, query_tokens, record.tags))
            for record in records
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [item[0] for item in scored[:limit]]

    def save_workspace_context(
        self,
        *,
        profile_root: str,
        indexed_paths: list[str] | None,
        opt_out_paths: list[str] | None,
    ) -> WorkspaceContext:
        self.base_path.mkdir(parents=True, exist_ok=True)
        root = str(Path(profile_root).resolve())
        context = WorkspaceContext(
            cwd=os.getcwd(),
            profileRoot=root,
            indexedPaths=normalize_paths(indexed_paths or [root]),
            optOutPaths=normalize_paths(opt_out_paths or []),
            excludeGlobs=DEFAULT_EXCLUDES,
        )
        self.context_file.write_text(context.model_dump_json(indent=2), encoding="utf-8")
        return context

    def get_workspace_context(self, profile_root: str) -> WorkspaceContext:
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not self.context_file.exists():
            return self.save_workspace_context(
                profile_root=profile_root,
                indexed_paths=None,
                opt_out_paths=None,
            )
        raw = self.context_file.read_text("utf-8")
        return WorkspaceContext.model_validate_json(raw)

    def refresh_workspace_index(
        self,
        *,
        profile_root: str,
        indexed_paths: list[str] | None = None,
        opt_out_paths: list[str] | None = None,
        max_files: int = 25_000,
    ) -> WorkspaceIndex:
        context = (
            self.save_workspace_context(
                profile_root=profile_root,
                indexed_paths=indexed_paths,
                opt_out_paths=opt_out_paths,
            )
            if indexed_paths is not None or opt_out_paths is not None
            else self.get_workspace_context(profile_root)
        )

        files: list[WorkspaceIndexHit] = []
        for root in context.indexedPaths:
            self._walk_path(
                path=Path(root),
                context=context,
                output=files,
                max_files=max_files,
            )
            if len(files) >= max_files:
                break

        payload = {
            "generatedAt": utc_now(),
            "profileRoot": context.profileRoot,
            "files": [entry.model_dump() for entry in files],
        }
        self.index_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return WorkspaceIndex(generatedAt=payload["generatedAt"], profileRoot=context.profileRoot, files=files)

    def search_workspace_index(self, query: str, limit: int = 10) -> list[WorkspaceIndexHit]:
        if not query.strip():
            return []
        index = self._read_or_create_index()
        tokens = tokenize(query)

        scored: list[WorkspaceIndexHit] = []
        for entry in index.files:
            score = score_workspace_entry(entry, tokens)
            if score <= 0:
                continue
            scored.append(
                WorkspaceIndexHit(
                    path=entry.path,
                    relativePath=entry.relativePath,
                    modifiedAt=entry.modifiedAt,
                    size=entry.size,
                    score=score,
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:limit]

    def _read_or_create_index(self) -> WorkspaceIndex:
        if not self.index_file.exists():
            context = self.get_workspace_context(str(Path.home()))
            return self.refresh_workspace_index(profile_root=context.profileRoot)
        raw = json.loads(self.index_file.read_text("utf-8"))
        files = [WorkspaceIndexHit.model_validate(item) for item in raw.get("files", [])]
        return WorkspaceIndex(
            generatedAt=raw.get("generatedAt", utc_now()),
            profileRoot=raw.get("profileRoot", str(Path.home())),
            files=files,
        )

    def _walk_path(
        self,
        *,
        path: Path,
        context: WorkspaceContext,
        output: list[WorkspaceIndexHit],
        max_files: int,
    ) -> None:
        if len(output) >= max_files:
            return

        resolved = path.resolve()
        if should_skip_path(resolved, context):
            return
        if not resolved.exists() or not resolved.is_dir():
            return

        try:
            children = list(resolved.iterdir())
        except OSError:
            return

        for child in children:
            if len(output) >= max_files:
                return

            if child.is_dir():
                if child.name.lower() in {item.lower() for item in context.excludeGlobs}:
                    continue
                self._walk_path(path=child, context=context, output=output, max_files=max_files)
                continue

            if not child.is_file():
                continue
            if child.suffix.lower() in DEFAULT_BINARY_EXTENSIONS:
                continue

            try:
                stats = child.stat()
            except OSError:
                continue

            relative = safe_relative_path(Path(context.profileRoot), child)
            output.append(
                WorkspaceIndexHit(
                    path=str(child),
                    relativePath=relative,
                    modifiedAt=datetime.fromtimestamp(
                        stats.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    size=int(stats.st_size),
                    score=0,
                )
            )

    def _read_records(self) -> list[MemoryRecord]:
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not self.records_file.exists():
            return []
        raw = json.loads(self.records_file.read_text("utf-8"))
        return [MemoryRecord.model_validate(item) for item in raw]

    def _write_records(self, records: list[MemoryRecord]) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump() for record in records]
        self.records_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def normalize_paths(paths: list[str]) -> list[str]:
    normalized = {str(Path(entry).resolve()) for entry in paths}
    return sorted(normalized)


def should_skip_path(target: Path, context: WorkspaceContext) -> bool:
    if target.name.lower() in {item.lower() for item in context.excludeGlobs}:
        return True
    for opt_out in context.optOutPaths:
        parent = Path(opt_out).resolve()
        try:
            target.relative_to(parent)
            return True
        except ValueError:
            continue
    return False


def safe_relative_path(base: Path, absolute: Path) -> str:
    try:
        return str(absolute.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(absolute.resolve())


def tokenize(text: str) -> list[str]:
    tokens = []
    current = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def score_memory_record(content: str, query_tokens: list[str], tags: list[str]) -> int:
    normalized = content.lower()
    tag_set = {tag.lower() for tag in tags}
    score = 0
    for token in query_tokens:
        if token in normalized:
            score += 2
        if token in tag_set:
            score += 3
    return score


def score_workspace_entry(entry: WorkspaceIndexHit, tokens: list[str]) -> int:
    path_lower = entry.relativePath.lower()
    base_name = Path(entry.relativePath).name.lower()
    score = 0
    for token in tokens:
        if token in base_name:
            score += 6
        elif token in path_lower:
            score += 3
    return score


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

