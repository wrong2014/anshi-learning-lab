"""
P01 对话式智能体 —— LLM 驱动 + 规则校验 + 阶段化对话

融合三个分支精华：
- main: LLM 驱动的自然对话体验
- accuracy: 5+3 分类体系 + 结果目录 + 验证动作
- debug: 规则交叉校验 + 年级感知 + 阶段化控制
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .factor_rules import (
    OPTION_WEIGHTS,
    SUBJECT_PRIORS,
    accumulate_scores,
    infer_option_ids_from_text,
    infer_subject_from_text,
)
from .llm_providers import LLMAdapter
from .models import (
    DiagnosticCategory,
    AmplifierCode,
    FactorCode,
    Subject,
    FACTOR_TO_CATEGORY,
    CATEGORY_LABELS,
    AMPLIFIER_LABELS,
)
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

    # 阶段化控制（来自 debug 分支）
    stage: str = "opening"  # opening → story → narrow → probe → conclude

    # 年级感知（来自 debug 分支）
    grade: int = 0  # 0=未识别, 1-12=年级
    grade_label: str = ""

    # 规则信号收集（来自 debug 分支）
    rule_option_ids: list[str] = field(default_factory=list)
    rule_subject: Subject = Subject.UNKNOWN
    free_text_evidence: list[str] = field(default_factory=list)

    # 5+3 诊断追踪（来自 accuracy 分支）
    candidate_categories: list[str] = field(default_factory=list)
    identified_category: str = ""
    identified_amplifier: str = ""


class ConversationAgent:
    """LLM 驱动 + 规则护栏的对话式智能体"""

    MAX_TURNS = 7  # 最多 7 轮对话

    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter
        self._raw_response_cache: str = ""

    # ==================== 年级工具（来自 debug 分支）====================

    @staticmethod
    def _extract_grade(text: str) -> int:
        """从文本中提取年级"""
        # 初中
        m = re.search(r"初([一二三1-3])", text)
        if m:
            mapping = {"一": 7, "二": 8, "三": 9, "1": 7, "2": 8, "3": 9}
            return mapping.get(m.group(1), 0)
        # 高中
        m = re.search(r"高([一二三1-3])", text)
        if m:
            mapping = {"一": 10, "二": 11, "三": 12, "1": 10, "2": 11, "3": 12}
            return mapping.get(m.group(1), 0)
        # 小学
        m = re.search(r"([一二三四五六1-6])\s*年级", text)
        if m:
            mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
            val = m.group(1)
            if val in mapping:
                return mapping[val]
            if val.isdigit():
                return int(val)
        # "初中""高中"
        if re.search(r"初中", text):
            return 8
        if re.search(r"高中", text):
            return 11
        return 0

    @staticmethod
    def _grade_to_label(grade: int) -> str:
        if grade == 0:
            return ""
        if grade <= 6:
            return f"{'一二三四五六'[grade - 1]}年级"
        if grade <= 9:
            return f"初{'一二三'[grade - 7]}"
        if grade <= 12:
            return f"高{'一二三'[grade - 10]}"
        return ""

    # ==================== 会话入口 ====================

    def start_session(self) -> tuple[ConversationSession, AgentTurnResult]:
        """开始一个新的对话会话"""
        session = ConversationSession()

        if not self.adapter.is_ready():
            return session, self._fallback_opening(session)

        # 用 LLM 生成开场白
        session.history.append({"role": "user", "content": FIRST_TURN_USER_MESSAGE})
        result = self._call_llm(session)
        session.history.append({"role": "assistant", "content": self._raw_response_cache})
        session.turn_count += 1
        session.stage = "story"

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

        # === Phase 2 & 3：无论 LLM 是否可用，始终收集规则信号 ===
        self._record_rule_signals(
            session=session,
            text=text,
            selected_option_ids=selected_option_ids or [],
            selected_labels=selected_labels or [],
        )

        if not self.adapter.is_ready():
            return self._fallback_response(session)

        # 阶段推进
        self._advance_stage(session)

        # 如果到了最大轮次，强制出结果
        force_conclude = session.turn_count >= self.MAX_TURNS

        result = self._call_llm(session, force_conclude=force_conclude)
        session.history.append({"role": "assistant", "content": self._raw_response_cache})

        # === Phase 2：LLM 出结论时，用规则做交叉校验 ===
        if result.should_conclude and result.result:
            result = self._ground_with_rules(session, result)

        # 从 LLM 返回的 collected_signals 中同步状态
        if result.collected_signals:
            signals = result.collected_signals
            if signals.get("identified_category"):
                session.identified_category = signals["identified_category"]
            if signals.get("amplifier"):
                session.identified_amplifier = signals["amplifier"]
            if signals.get("candidate_categories"):
                session.candidate_categories = signals["candidate_categories"]

        if result.should_conclude:
            session.is_complete = True

        return result

    # ==================== 规则信号收集（来自 debug 分支）====================

    def _record_rule_signals(
        self,
        session: ConversationSession,
        text: str | None,
        selected_option_ids: list[str],
        selected_labels: list[str],
    ) -> None:
        """每轮无条件收集规则信号"""
        # 收集选项 ID
        for oid in selected_option_ids:
            if oid not in session.rule_option_ids:
                session.rule_option_ids.append(oid)

        if text and text.strip():
            stripped = text.strip()

            # 收集家长原话
            if stripped not in session.free_text_evidence:
                session.free_text_evidence.append(stripped)

            # 从文本推断学科
            if session.rule_subject == Subject.UNKNOWN:
                inferred = infer_subject_from_text(stripped)
                if inferred != Subject.UNKNOWN:
                    session.rule_subject = inferred

            # 从文本推断选项
            text_ids = infer_option_ids_from_text(stripped)
            for oid in text_ids:
                if oid not in session.rule_option_ids:
                    session.rule_option_ids.append(oid)

            # 年级提取
            if session.grade == 0:
                grade = self._extract_grade(stripped)
                if grade > 0:
                    session.grade = grade
                    session.grade_label = self._grade_to_label(grade)

    # ==================== 规则交叉校验（来自 debug 分支）====================

    def _ground_with_rules(self, session: ConversationSession, result: AgentTurnResult) -> AgentTurnResult:
        """LLM 出结论后，用规则引擎做交叉校验"""
        if not session.rule_option_ids:
            return result

        # 用规则引擎计算因子得分
        scores = accumulate_scores(session.rule_subject, session.rule_option_ids)
        if not scores:
            return result

        # 找到规则引擎的 top category
        category_scores: dict[DiagnosticCategory, float] = defaultdict(float)
        for factor, score in scores.items():
            if factor in FACTOR_TO_CATEGORY:
                category_scores[FACTOR_TO_CATEGORY[factor]] += score

        if not category_scores:
            return result

        rule_top_category = max(category_scores, key=lambda c: category_scores[c])

        # 从 LLM 的 result 中提取 category
        llm_result = result.result or {}
        llm_category_str = llm_result.get("primary_category", "")

        # 映射 LLM 的 category 字符串到枚举
        category_map = {
            "A": DiagnosticCategory.A_FOUNDATION,
            "B": DiagnosticCategory.B_REPRESENTATION,
            "C": DiagnosticCategory.C_MODELING,
            "D": DiagnosticCategory.D_EXECUTION,
            "E": DiagnosticCategory.E_SELF_REGULATION,
        }
        llm_category = category_map.get(llm_category_str)

        if llm_category and llm_category != rule_top_category:
            # 冲突：在结果中标注
            rule_label = CATEGORY_LABELS.get(rule_top_category, "")
            if "uncertainties" not in llm_result:
                llm_result["uncertainties"] = []
            llm_result["uncertainties"].append(
                f"规则评分更倾向「{rule_label}」方向，建议通过今晚验证进一步确认。"
            )
            # 降低置信度
            llm_result["confidence"] = "medium"

        # 注入验证动作
        try:
            from .verification_actions import get_verification_action
            if llm_category:
                verification = get_verification_action(llm_category, session.rule_subject)
                llm_result["verification_action"] = verification
        except ImportError:
            pass

        # 注入年级标签
        if session.grade_label:
            llm_result["grade_label"] = session.grade_label

        result.result = llm_result
        return result

    # ==================== 阶段推进 ====================

    def _advance_stage(self, session: ConversationSession) -> None:
        """根据轮次和已有信息推进对话阶段"""
        if session.stage == "opening":
            session.stage = "story"
        elif session.stage == "story" and session.turn_count >= 2:
            session.stage = "narrow"
        elif session.stage == "narrow" and session.turn_count >= 4:
            session.stage = "probe"
        elif session.stage == "probe" and session.turn_count >= 5:
            session.stage = "conclude"

    # ==================== LLM 调用 ====================

    def _call_llm(self, session: ConversationSession, force_conclude: bool = False) -> AgentTurnResult:
        """调用 LLM 获取下一轮回复"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 注入当前阶段和已收集的规则信号作为上下文
        context_parts = [f"当前对话阶段：{session.stage}，已进行 {session.turn_count} 轮。"]
        if session.grade_label:
            context_parts.append(f"孩子年级：{session.grade_label}。")
        if session.rule_subject != Subject.UNKNOWN:
            subject_map = {Subject.MATH: "数学", Subject.PHYSICS: "物理", Subject.CHEMISTRY: "化学"}
            context_parts.append(f"已识别学科：{subject_map.get(session.rule_subject, '未知')}。")
        if session.candidate_categories:
            context_parts.append(f"当前候选主类：{', '.join(session.candidate_categories)}。")
        if session.identified_category:
            context_parts.append(f"已初步锁定主类：{session.identified_category}。")

        if context_parts:
            messages.append({"role": "system", "content": " ".join(context_parts)})

        # 添加对话历史
        for msg in session.history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 强制出结果
        if force_conclude:
            messages.append({
                "role": "system",
                "content": "注意：对话已足够多轮。请在本轮直接输出最终定位结果（should_conclude=true），不要再追问。如果信息不足，在 uncertainties 中说明。"
            })

        try:
            raw = self.adapter.text_client().chat_text(messages, max_tokens=2000)
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
            return AgentTurnResult(messages=[AgentMessage(text=raw.strip())])

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

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
        if match:
            return json.loads(match.group(1))

        match = re.search(r"\{.*\}", stripped, re.S)
        if match:
            return json.loads(match.group(0))

        raise ValueError("No JSON found in LLM response")

    # ==================== 降级回复 ====================

    def _fallback_opening(self, session: ConversationSession) -> AgentTurnResult:
        session.stage = "story"
        return AgentTurnResult(
            messages=[AgentMessage(
                text="你好！我是理科学习卡点定位助手。\n\n你先把孩子最近在数学、物理或化学上最让你头疼的一件事告诉我。可以直接说：哪类题、什么时候容易错、考试还是作业、你已经试过什么。不用先判断是不是粗心，我会先帮你把问题缩小到更具体的一类。",
                ui_block={
                    "type": "subject_picker",
                    "id": "opening_subject",
                    "title": "今天先看哪一科？",
                    "body": "一次只看一科，判断会更准。",
                    "options": [
                        {"id": "subject_math", "label": "数学", "hint": "计算、几何、函数、应用题"},
                        {"id": "subject_physics", "label": "物理", "hint": "概念、公式、实验、综合题"},
                        {"id": "subject_chemistry", "label": "化学", "hint": "概念、方程式、实验、计算"},
                    ],
                }
            )]
        )

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
                            {"id": "subject_math", "label": "数学"},
                            {"id": "subject_physics", "label": "物理"},
                            {"id": "subject_chemistry", "label": "化学"},
                        ]
                    }
                )]
            )
        else:
            return AgentTurnResult(
                messages=[AgentMessage(text="LLM 服务暂时不可用，无法完成深度定位。请稍后再试。")],
                should_conclude=True,
            )
