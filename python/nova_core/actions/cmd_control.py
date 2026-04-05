from __future__ import annotations

import os
import subprocess
from pathlib import Path


SAFE_BASE_COMMANDS = {
    "python",
    "python3",
    "node",
    "pnpm",
    "npm",
    "corepack",
    "git",
    "firefox",
    "chrome",
    "msedge",
    "notepad",
    "code",
    "explorer",
}
SAFE_INSTALL_COMMANDS = {"pnpm", "npm", "corepack"}
SAFE_NETWORK_COMMANDS = {"curl", "wget"}


def normalize_command_name(command: str) -> str:
    name = Path(command.strip().lower()).stem
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def validate_command(command: str, *, allow_install: bool, network: bool = False) -> None:
    base = normalize_command_name(command)
    if network:
        if base not in SAFE_NETWORK_COMMANDS:
            raise PermissionError(f"Network command '{command}' is not allowlisted.")
        return

    if base in SAFE_INSTALL_COMMANDS and not allow_install:
        raise PermissionError(
            "Install commands are disabled by NOVA_ALLOW_INSTALL_COMMANDS=false."
        )
    if base not in SAFE_BASE_COMMANDS:
        raise PermissionError(f"Command '{command}' is not allowlisted.")


def run_shell_command(
    command: str,
    args: list[str] | None = None,
    *,
    cwd: str | None = None,
    timeout_seconds: int = 90,
) -> dict[str, object]:
    cmd = [command, *(args or [])]
    completed = subprocess.run(
        cmd,
        cwd=os.path.abspath(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=timeout_seconds,
    )
    output = "\n".join(
        chunk for chunk in [completed.stdout.strip(), completed.stderr.strip()] if chunk
    )
    return {
        "command": cmd,
        "cwd": cwd,
        "returnCode": completed.returncode,
        "output": output,
    }
