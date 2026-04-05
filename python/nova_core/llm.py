from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from .config import CoreConfig


def load_system_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent / "prompts" / "system_prompt.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return (
        "You are Nova, a local-first developer second mind.\n"
        "Be concise, practical, and safety-aware.\n"
        "When proposing actions that modify files/system state, call out approval requirements."
    )


@dataclass
class ModelResult:
    ok: bool
    content: str
    provider: str
    model: str
    error: str | None = None


class LLMService:
    def __init__(self, config: CoreConfig) -> None:
        self.config = config
        self.system_prompt = load_system_prompt()

    def is_enabled(self) -> bool:
        return self.config.model_provider.lower() == "ollama"

    def generate(
        self,
        *,
        prompt: str,
        context_hint: str | None = None,
        temperature: float = 0.2,
        system_override: str | None = None,
    ) -> ModelResult:
        provider = self.config.model_provider.lower()
        if provider != "ollama":
            return ModelResult(
                ok=False,
                content="Model provider is not configured.",
                provider=provider,
                model=self.config.local_model,
                error=f"Unsupported provider '{provider}'.",
            )

        system_prompt = system_override or self.system_prompt
        if context_hint:
            system_prompt = f"{system_prompt}\nContext: {context_hint}"

        payload = {
            "model": self.config.local_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            response = requests.post(
                self.config.ollama_url,
                json=payload,
                timeout=self.config.model_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            content = (
                data.get("message", {}).get("content")
                if isinstance(data, dict)
                else None
            )
            if not content:
                return ModelResult(
                    ok=False,
                    content="Model call returned no content.",
                    provider="ollama",
                    model=self.config.local_model,
                    error="Empty response payload from Ollama.",
                )
            return ModelResult(
                ok=True,
                content=str(content).strip(),
                provider="ollama",
                model=self.config.local_model,
            )
        except Exception as error:  # noqa: BLE001
            return ModelResult(
                ok=False,
                content=(
                    "I couldn't reach the local model. Start Ollama and pull the configured model, "
                    "then try again."
                ),
                provider="ollama",
                model=self.config.local_model,
                error=str(error),
            )
