from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import ExtractedSignals, LLMProviderConfig, ProviderStatus


ALLOWED_OPTION_IDS = {
    "stuck_read_problem",
    "stuck_concept_formula",
    "stuck_transform",
    "stuck_select_method",
    "stuck_execution",
    "stuck_repeat_after_answer",
    "stuck_emotional_avoidance",
    "stuck_attention_overload",
    "stuck_confident_wrong_idea",
    "parent_explain_full_solution",
    "parent_add_more_exercises",
    "parent_ask_breakpoint",
    "parent_ai_gives_answer",
    "parent_review_then_retest",
    "math_same_template_ok_variant_fail",
    "math_symbol_condition_missed",
    "math_multi_condition_overload",
    "physics_no_diagram",
    "physics_formula_without_quantity_meaning",
    "physics_naive_force_motion",
    "physics_direction_sign_confusion",
    "chem_symbol_equation_mismatch",
    "chem_rule_cannot_transfer",
    "chem_conservation_or_valence_misconception",
    "probe_template_ok_variant_fail",
    "probe_knows_relation_not_formula",
    "probe_text_to_diagram_hard",
    "probe_diagram_to_formula_hard",
    "probe_ai_answer_first",
    "probe_parent_takes_over",
    "probe_cannot_name_breakpoint",
    "probe_only_reads_answer",
    "probe_emotion_blocks_start",
    "probe_many_conditions_overload",
    "probe_confident_but_wrong_rule",
    # P1 新增
    "probe_can_recite_not_explain",
    "probe_confuses_similar_concepts",
    "probe_cannot_give_example",
    "probe_misreads_keyword",
    "probe_cannot_parse_diagram",
    "probe_symbol_confusion",
    "probe_calculation_error",
    "probe_skip_steps",
    "probe_no_check",
    "probe_simple_ok_complex_fail",
    "probe_loses_condition",
    "probe_mid_step_forget",
    "probe_wrong_causal",
    "probe_intuitive_rule",
    "probe_previous_mislearn",
    "probe_forgot_previous",
    "probe_knows_but_cant_use",
    "probe_gap_specific_topic",
}


@dataclass(frozen=True)
class ProviderRegistry:
    deepseek: LLMProviderConfig
    doubao: LLMProviderConfig
    enable_llm: bool
    default_text_provider: str = "deepseek"
    timeout_seconds: int = 45


def load_dotenv_file(env_path: str | Path) -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def load_provider_registry(env_path: str | Path | None = None) -> ProviderRegistry:
    if env_path:
        load_dotenv_file(env_path)
    return ProviderRegistry(
        deepseek=LLMProviderConfig(
            provider="deepseek",
            api_key=os.getenv("DEEPSEEK_API_KEY") or None,
            base_url=os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com",
            text_model=os.getenv("DEEPSEEK_TEXT_MODEL") or "deepseek-v4-flash",
        ),
        doubao=LLMProviderConfig(
            provider="doubao",
            api_key=os.getenv("DOUBAO_API_KEY") or None,
            base_url=os.getenv("DOUBAO_BASE_URL") or None,
            text_model=os.getenv("DOUBAO_TEXT_MODEL") or None,
            vision_model=os.getenv("DOUBAO_VISION_MODEL") or None,
            asr_app_id=os.getenv("DOUBAO_ASR_APP_ID") or None,
            tts_app_id=os.getenv("DOUBAO_TTS_APP_ID") or None,
        ),
        enable_llm=(os.getenv("ENABLE_LLM") or "false").lower() == "true",
        default_text_provider=os.getenv("DEFAULT_TEXT_PROVIDER") or "deepseek",
        timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS") or "45"),
    )


class OpenAICompatibleChatClient:
    def __init__(self, config: LLMProviderConfig, timeout_seconds: int = 45):
        self.config = config
        self.timeout_seconds = timeout_seconds

    def ready(self) -> bool:
        return bool(self.config.api_key and self.config.base_url and self.config.text_model)

    def chat_json(self, messages: list[dict[str, str]], max_tokens: int = 800) -> dict[str, Any]:
        content = self.chat(messages, response_format={"type": "json_object"}, max_tokens=max_tokens)
        return parse_json_object(content)

    def chat_text(self, messages: list[dict[str, str]], max_tokens: int = 900) -> str:
        return self.chat(messages, response_format=None, max_tokens=max_tokens)

    def chat(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None,
        max_tokens: int,
    ) -> str:
        if not self.ready():
            raise RuntimeError(f"{self.config.provider} provider is not configured")

        payload: dict[str, Any] = {
            "model": self.config.text_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format
        if self.config.provider == "deepseek":
            payload["thinking"] = {"type": os.getenv("DEEPSEEK_THINKING") or "disabled"}

        url = completion_url(self.config.base_url or "")
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.config.provider} API error {exc.code}: {error_body}") from exc

        data = json.loads(raw)
        return data["choices"][0]["message"]["content"] or ""


def completion_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


class LLMAdapter:
    """Optional LLM layer.

    The rule engine remains the source of truth. This adapter improves free-text
    signal extraction and parent-facing explanation when keys are configured.
    """

    def __init__(self, registry: ProviderRegistry):
        self.registry = registry
        self.clients = {
            "deepseek": OpenAICompatibleChatClient(registry.deepseek, registry.timeout_seconds),
            "doubao": OpenAICompatibleChatClient(registry.doubao, registry.timeout_seconds),
        }

    def is_ready(self) -> bool:
        return self.registry.enable_llm and self.text_client().ready()

    def text_client(self) -> OpenAICompatibleChatClient:
        provider = self.registry.default_text_provider
        return self.clients.get(provider) or self.clients["deepseek"]

    def status(self) -> ProviderStatus:
        deepseek_ready = self.clients["deepseek"].ready()
        doubao_ready = self.clients["doubao"].ready()
        return ProviderStatus(
            enable_llm=self.registry.enable_llm,
            default_text_provider=self.registry.default_text_provider,
            deepseek_ready=deepseek_ready,
            doubao_ready=doubao_ready,
            deepseek_model=self.registry.deepseek.text_model,
            doubao_text_model=self.registry.doubao.text_model,
            mode="llm" if self.is_ready() else "rules",
        )

    def extract_signals(self, subject: str, free_text: str) -> ExtractedSignals:
        if not self.is_ready() or not free_text.strip():
            return ExtractedSignals()

        messages = [
            {
                "role": "system",
                "content": (
                    "你是理科学习卡点定位系统的证据抽取模块。"
                    "你只从家长描述中抽取可观察信号，不下诊断，不贴标签。"
                    "必须输出 JSON，字段为 option_ids, evidence_notes, uncertainty_notes。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"学科：{subject}\n"
                    f"家长描述：{free_text}\n\n"
                    "允许的 option_ids 只能从以下列表选择：\n"
                    f"{sorted(ALLOWED_OPTION_IDS)}\n\n"
                    "请返回 JSON，例如："
                    '{"option_ids":["stuck_select_method"],"evidence_notes":["..."],"uncertainty_notes":["..."]}'
                ),
            },
        ]
        try:
            data = self.text_client().chat_json(messages, max_tokens=700)
            parsed = ExtractedSignals.model_validate(data)
        except (RuntimeError, ValidationError, json.JSONDecodeError, KeyError):
            return ExtractedSignals()

        parsed.option_ids = [item for item in parsed.option_ids if item in ALLOWED_OPTION_IDS]
        return parsed

    def polish_result(self, result_json: dict[str, Any]) -> str | None:
        if not self.is_ready():
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "你是面向家长的学习支持定位助手。"
                    "请把结构化结果写成克制、具体、可执行的一段中文。"
                    "不要说孩子是某某型，不要承诺提分，不要做心理诊断。"
                    "必须以“目前更像是”开头，长度 120-180 字。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(result_json, ensure_ascii=False),
            },
        ]
        try:
            return self.text_client().chat_text(messages, max_tokens=420).strip()
        except RuntimeError:
            return None


# Backward-compatible alias used by earlier docs.
PydanticAIAdapter = LLMAdapter
