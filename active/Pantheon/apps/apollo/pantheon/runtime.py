from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - depends on local environment
    Anthropic = None

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_TIMEOUT,
    OLLAMA_BASE_URL,
    PANTHEON_MODEL,
    PANTHEON_PRIMARY_PROVIDER,
    PRIMARY_MODEL,
)
from core.audit import log


@dataclass
class ProviderResult:
    content: str
    provider: str
    model: str


class AnthropicRuntime:
    """Anthropic-backed reasoning runtime."""

    def __init__(self, api_key: str | None = ANTHROPIC_API_KEY, model: str = PRIMARY_MODEL):
        self.api_key = api_key
        self.model = model
        self.timeout = ANTHROPIC_TIMEOUT
        self._client: Anthropic | None = None

    def available(self) -> bool:
        return bool(self.api_key)

    def _client_instance(self) -> Anthropic:
        if Anthropic is None:
            raise RuntimeError("anthropic package is not installed.")
        if self._client is None:
            self._client = Anthropic(api_key=self.api_key, timeout=self.timeout)
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> ProviderResult | None:
        if not self.available():
            return None
        try:
            response = self._client_instance().messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            parts = []
            for item in response.content:
                text = getattr(item, "text", "")
                if text:
                    parts.append(text)
            content = "\n".join(parts).strip()
            if content:
                return ProviderResult(content=content, provider="anthropic", model=self.model)
        except Exception as exc:
            log(f"Anthropic runtime unavailable: {exc}", system="PANTHEON")
        return None

    def diagnostics(self) -> dict[str, Any]:
        if Anthropic is None:
            return {
                "provider": "anthropic",
                "available": False,
                "model": self.model,
                "reason": "anthropic package is not installed in the active Python environment.",
            }
        return {
            "provider": "anthropic",
            "available": self.available(),
            "model": self.model,
            "reason": "" if self.available() else "ANTHROPIC_API_KEY is not configured.",
        }


class LocalModelRuntime:
    """Thin wrapper around a local Ollama runtime."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = PANTHEON_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.ok
        except requests.RequestException:
            return False

    def generate(self, system_prompt: str, user_prompt: str) -> ProviderResult | None:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            content = message.get("content", "").strip()
            if content:
                return ProviderResult(content=content, provider="ollama", model=self.model)
        except requests.RequestException as exc:
            log(f"Local model unavailable: {exc}", system="PANTHEON")
        return None

    def diagnostics(self) -> dict[str, Any]:
        available = self.available()
        return {
            "provider": "ollama",
            "available": available,
            "model": self.model,
            "reason": "" if available else f"Ollama is unavailable at {self.base_url}.",
        }


class ProviderGateway:
    """Primary/fallback provider gateway for Pantheon generation."""

    def __init__(self):
        self.anthropic = AnthropicRuntime()
        self.ollama = LocalModelRuntime()
        self.primary_provider = (PANTHEON_PRIMARY_PROVIDER or "anthropic").lower()

    def _ordered_runtimes(self) -> list[Any]:
        if self.primary_provider == "ollama":
            return [self.ollama, self.anthropic]
        return [self.anthropic, self.ollama]

    def available(self) -> bool:
        return any(runtime.available() for runtime in self._ordered_runtimes())

    def generate(self, system_prompt: str, user_prompt: str) -> ProviderResult | None:
        for runtime in self._ordered_runtimes():
            result = runtime.generate(system_prompt, user_prompt)
            if result:
                return result
        return None

    def diagnostics(self) -> dict[str, Any]:
        current_provider = "none"
        for runtime in self._ordered_runtimes():
            if runtime.available():
                current_provider = runtime.diagnostics()["provider"]
                break
        return {
            "current_provider": current_provider,
            "preferred_provider": self.primary_provider,
            "anthropic": self.anthropic.diagnostics(),
            "ollama": self.ollama.diagnostics(),
        }
