"""
P01 对话式智能体 —— LLM 驱动的对话引擎

取代原来的 if-else 问卷状态机。
LLM 负责：理解语义 → 决定追问/出结果 → 生成自然语言 + 可选 UI Block。
规则系统退到幕后做护栏校验。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .llm_providers import LLMAdapter, ProviderRegistry
from .prompts import SYSTEM_PROMPT, FIRST_TURN_USER_MESSAGE


@dataclass
class AgentMessage:
    """智能体的一轮回复"""
    text: str
    ui_block: dict[str, Any] | None = None


@dataclass
class AgentTurnResult:
    """一轮对话的完整结果"""
    messages: list[AgentMessage]
    should_conclude: bool = False
    result: dict[str, Any] | None = None
    thinking: str = ""
    collected_signals: dict[str, Any] | None = None


@dataclass
class ConversationSession:
    """对话会话状态"""
    session_id: str = field(default_factory=lambda: str(uuid4()))
    history: list[dict[str, str]] = field(default_factory=list)
    turn_count: int = 0
    is_complete: bool = False


class ConversationAgent:
    """LLM 驱动的对话式智能体"""

    MAX_TURNS = 8  # 安全阀：最多 8 轮对话后强制出结果

    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def start_session(self) -> tuple[ConversationSession, AgentTurnResult]:
        """开始一个新的对话会话"""
        session = ConversationSession()

        if not self.adapter.is_ready():
            # LLM 不可用时的降级处理
            return session, AgentTurnResult(
                messages=[AgentMessage(
                    text="你好！我是理科学习卡点定位助手。最近孩子在数学、物理或化学的学习中，哪件事最让你担心？你可以像发微信一样说一段，也可以从下面选一个最接近的场景。",
                    ui_block={
                        "type": "single_choice",
                        "id": "opening",
                        "title": "最近哪件事最让你担心？",
                        "options": [
                            {"id": "concern_1", "label": "课堂像听懂了，一做题就不会启动"},
                            {"id": "concern_2", "label": "错题反复错，看答案懂了下次又不会"},
                            {"id": "concern_3", "label": "孩子一遇到难题就想让 AI 给答案"},
                            {"id": "concern_4", "label": "我越帮越累，关系也越来越紧张"},
                        ]
                    }
                )]
            )

        # 用 LLM 生成开场白
        session.history.append({"role": "user", "content": FIRST_TURN_USER_MESSAGE})
        result = self._call_llm(session)
        session.history.append({"role": "assistant", "content": self._raw_response_cache})
        session.turn_count += 1

        return session, result

    def process_user_input(
        self,
        session: ConversationSession,
        text: str | None = None,
        selected_option_ids: list[str] | None = None,
        selected_labels: list[str] | None = None,
    ) -> AgentTurnResult:
        """处理用户的一轮输入"""
        # 构建用户消息
        parts = []
        if text:
            parts.append(text)
        if selected_labels:
            parts.append(f"（用户选择了：{'、'.join(selected_labels)}）")
        elif selected_option_ids:
            parts.append(f"（用户选择了选项：{'、'.join(selected_option_ids)}）")

        user_message = " ".join(parts) if parts else "（用户跳过了这个问题）"
        session.history.append({"role": "user", "content": user_message})
        session.turn_count += 1

        if not self.adapter.is_ready():
            return self._fallback_response(session)

        # 如果已经到了最大轮次，强制要求出结果
        force_conclude = session.turn_count >= self.MAX_TURNS

        result = self._call_llm(session, force_conclude=force_conclude)
        session.history.append({"role": "assistant", "content": self._raw_response_cache})

        if result.should_conclude:
            session.is_complete = True

        return result

    def _call_llm(self, session: ConversationSession, force_conclude: bool = False) -> AgentTurnResult:
        """调用 LLM 获取下一轮回复"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 添加对话历史（跳过内部的 system message）
        for msg in session.history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 如果需要强制出结果，追加指令
        if force_conclude:
            messages.append({
                "role": "system",
                "content": "注意：对话已经进行了足够多轮。请在本轮直接输出最终定位结果（should_conclude=true），不要再追问。如果信息不足，在 missing_information 中说明。"
            })

        try:
            raw = self.adapter.text_client().chat_text(messages, max_tokens=1500)
            self._raw_response_cache = raw
            return self._parse_llm_response(raw)
        except Exception as e:
            print(f"[ConversationAgent] LLM call failed: {e}")
            self._raw_response_cache = ""
            return AgentTurnResult(
                messages=[AgentMessage(text="抱歉，我需要一点时间整理思路。你可以继续描述，或者选择下面的选项。")],
            )

    def _parse_llm_response(self, raw: str) -> AgentTurnResult:
        """解析 LLM 返回的 JSON"""
        try:
            data = self._extract_json(raw)
        except (json.JSONDecodeError, ValueError):
            # 如果 LLM 没有返回有效 JSON，把整个文本当作回复
            return AgentTurnResult(
                messages=[AgentMessage(text=raw.strip())]
            )

        response_text = data.get("response_text", "")
        ui_block = data.get("ui_block")
        should_conclude = data.get("should_conclude", False)
        thinking = data.get("thinking", "")
        collected_signals = data.get("collected_signals")
        result = data.get("result")

        messages = [AgentMessage(text=response_text, ui_block=ui_block)]

        return AgentTurnResult(
            messages=messages,
            should_conclude=should_conclude,
            result=result,
            thinking=thinking,
            collected_signals=collected_signals,
        )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """从 LLM 输出中提取 JSON 对象"""
        stripped = text.strip()

        # 尝试直接解析
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown code block 中提取
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
        if match:
            return json.loads(match.group(1))

        # 尝试找最外层的 JSON 对象
        match = re.search(r"\{.*\}", stripped, re.S)
        if match:
            return json.loads(match.group(0))

        raise ValueError("No JSON found in LLM response")

    def _fallback_response(self, session: ConversationSession) -> AgentTurnResult:
        """LLM 不可用时的降级回复"""
        turn = session.turn_count
        if turn <= 2:
            return AgentTurnResult(
                messages=[AgentMessage(
                    text="谢谢你的描述。这件事主要发生在哪一科？",
                    ui_block={
                        "type": "single_choice",
                        "id": "subject_select",
                        "title": "这件事主要发生在哪一科？",
                        "options": [
                            {"id": "math", "label": "数学"},
                            {"id": "physics", "label": "物理"},
                            {"id": "chemistry", "label": "化学"},
                        ]
                    }
                )]
            )
        else:
            return AgentTurnResult(
                messages=[AgentMessage(
                    text="LLM 服务暂时不可用，无法完成深度定位。请稍后再试。"
                )],
                should_conclude=True,
            )
