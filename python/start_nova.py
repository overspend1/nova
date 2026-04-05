from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests


def main() -> int:
    root = Path(__file__).resolve().parent
    token = os.getenv("NOVA_AUTH_TOKEN", secrets.token_hex(24))
    env = os.environ.copy()
    env["NOVA_AUTH_TOKEN"] = token
    env.setdefault("NOVA_HOST", "127.0.0.1")
    requested_port = int(env.get("NOVA_PORT", "8765"))
    selected_port = pick_port(preferred=requested_port)
    env["NOVA_PORT"] = str(selected_port)
    env["NOVA_BASE_URL"] = f"http://{env['NOVA_HOST']}:{selected_port}"

    print(f"NOVA_AUTH_TOKEN={token}")
    print(f"NOVA_BASE_URL={env['NOVA_BASE_URL']}")
    core_cmd = [sys.executable, str(root / "start_core.py")]
    desktop_cmd = [sys.executable, str(root / "start_desktop.py")]

    core_process = subprocess.Popen(core_cmd, cwd=str(root), env=env)
    try:
        if not wait_for_core_ready(
            base_url=env["NOVA_BASE_URL"],
            token=token,
            timeout_seconds=15,
        ):
            print(
                "Nova core failed to become ready with the selected token. "
                "Check existing processes and retry."
            )
            return 1
        return subprocess.call(desktop_cmd, cwd=str(root), env=env)
    finally:
        if core_process.poll() is None:
            core_process.terminate()
            try:
                core_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                core_process.kill()


def pick_port(preferred: int) -> int:
    if is_port_free(preferred):
        return preferred
    for candidate in range(preferred + 1, preferred + 200):
        if is_port_free(candidate):
            return candidate
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def wait_for_core_ready(*, base_url: str, token: str, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    headers = {"x-nova-token": token}
    while time.time() < deadline:
        try:
            health = requests.get(f"{base_url}/health", timeout=2)
            if health.status_code != 200:
                time.sleep(0.25)
                continue
            authed = requests.get(
                f"{base_url}/actions/catalog",
                headers=headers,
                timeout=2,
            )
            if authed.status_code == 200:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.25)
    return False


if __name__ == "__main__":
    raise SystemExit(main())
