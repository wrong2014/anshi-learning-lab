from __future__ import annotations

from collections import deque
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Protocol

from .models import ProviderConfig


class JsonProvider(Protocol):
    name: str

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


def _completion_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.S)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("provider response must be a JSON object")
    return value


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key environment variable: {self.config.api_key_env}")
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": self.config.thinking},
        }
        if self.config.thinking == "enabled" and self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort
        request = urllib.request.Request(
            _completion_url(self.config.base_url),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"provider {self.name} returned HTTP {exc.code}: {body}") from exc
        try:
            choice = raw["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"provider {self.name} returned an unexpected response") from exc
        if not content or not content.strip():
            reasoning_length = len(message.get("reasoning_content") or "")
            finish_reason = choice.get("finish_reason", "unknown")
            raise RuntimeError(
                f"provider {self.name} returned empty content "
                f"(finish_reason={finish_reason}, reasoning_chars={reasoning_length}); "
                "increase max_tokens or disable reasoning for this provider"
            )
        return parse_json_object(content)


class ScriptedProvider:
    """Deterministic provider for tests and local pipeline demonstrations."""

    def __init__(self, name: str, responses: list[dict[str, Any]]):
        self.name = name
        self._responses = deque(responses)
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        self.calls.append((system_prompt, user_prompt))
        if not self._responses:
            raise RuntimeError(f"scripted provider {self.name} has no response left")
        return self._responses.popleft()


def build_providers(configs: list[ProviderConfig]) -> dict[str, JsonProvider]:
    return {item.name: OpenAICompatibleProvider(item) for item in configs if item.enabled}
