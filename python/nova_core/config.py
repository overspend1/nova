from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoreConfig:
    host: str
    port: int
    auth_token: str
    profile_root: Path
    data_root: Path
    audit_file: Path
    memory_root: Path
    allow_install_commands: bool
    model_provider: str
    local_model: str
    ollama_url: str
    model_timeout_seconds: int

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def load_config() -> CoreConfig:
    profile_root = Path(os.getenv("NOVA_PROFILE_ROOT", str(Path.home()))).resolve()
    data_root = Path(os.getenv("NOVA_DATA_PATH", str(profile_root / ".nova-py"))).resolve()
    auth_token = os.getenv("NOVA_AUTH_TOKEN", secrets.token_hex(24))

    return CoreConfig(
        host=os.getenv("NOVA_HOST", "127.0.0.1"),
        port=int(os.getenv("NOVA_PORT", "8765")),
        auth_token=auth_token,
        profile_root=profile_root,
        data_root=data_root,
        audit_file=Path(
            os.getenv("NOVA_AUDIT_FILE", str(data_root / "audit" / "timeline.jsonl"))
        ).resolve(),
        memory_root=Path(
            os.getenv("NOVA_MEMORY_ROOT", str(data_root / "memory"))
        ).resolve(),
        allow_install_commands=os.getenv("NOVA_ALLOW_INSTALL_COMMANDS", "false").lower()
        == "true",
        model_provider=os.getenv("NOVA_MODEL_PROVIDER", "ollama"),
        local_model=os.getenv("NOVA_LOCAL_MODEL", "qwen3:4b"),
        ollama_url=os.getenv("NOVA_OLLAMA_URL", "http://127.0.0.1:11434/api/chat"),
        model_timeout_seconds=int(os.getenv("NOVA_MODEL_TIMEOUT_SECONDS", "60")),
    )
