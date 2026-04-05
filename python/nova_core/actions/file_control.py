from __future__ import annotations

from pathlib import Path


def list_directory(path: str, max_entries: int = 200) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {target}")

    entries: list[dict[str, object]] = []
    for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[
        :max_entries
    ]:
        entries.append(
            {
                "name": item.name,
                "path": str(item),
                "kind": "directory" if item.is_dir() else "file",
            }
        )
    return {"path": str(target), "entries": entries, "count": len(entries)}


def read_text_file(path: str, max_chars: int = 24_000) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"File does not exist: {target}")
    if not target.is_file():
        raise ValueError(f"Path is not a file: {target}")
    content = target.read_text(encoding="utf-8", errors="replace")
    clipped = content[:max_chars]
    return {
        "path": str(target),
        "size": target.stat().st_size,
        "truncated": len(content) > len(clipped),
        "content": clipped,
    }


def write_text_file(
    path: str,
    content: str,
    *,
    overwrite: bool = True,
    create_dirs: bool = True,
) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    if target.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": str(target), "bytesWritten": len(content.encode("utf-8"))}


def append_text_file(path: str, content: str, create_dirs: bool = True) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(content)
    return {"path": str(target), "bytesAppended": len(content.encode("utf-8"))}
