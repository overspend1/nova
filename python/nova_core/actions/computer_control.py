from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path


def get_system_snapshot() -> dict[str, object]:
    return {
        "os": platform.platform(),
        "pythonVersion": platform.python_version(),
        "machine": platform.machine(),
        "cwd": os.getcwd(),
        "username": os.getenv("USERNAME") or os.getenv("USER") or "unknown",
    }


def list_processes(limit: int = 40) -> dict[str, object]:
    completed = subprocess.run(
        ["tasklist"],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=15,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    data_lines = lines[3 : 3 + limit]
    return {
        "returnCode": completed.returncode,
        "processes": data_lines,
    }


def open_path(path: str) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")
    os.startfile(str(target))  # type: ignore[attr-defined]
    return {"opened": str(target)}
