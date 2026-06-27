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
from copy import deepcopy
from uuid import uuid4

from .factor_rules import (
    FACTOR_ACTIONS,
    FACTOR_PUBLIC_LABELS,
    OPTION_PUBLIC_LABELS,
    accumulate_scores,
    infer_option_ids_from_text,
    infer_subject_from_text,
)
from .llm_providers import LLMAdapter, ProviderRegistry
from .models import FactorCode, Subject
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
    pending_ui_block_id: str | None = None
    pending_ui_block_type: str | None = None
    fallback_subject: Subject = Subject.UNKNOWN
    fallback_option_ids: list[str] = field(default_factory=list)
    fallback_asked_block_ids: set[str] = field(default_factory=set)


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
                    text="你好，我先听你说。最近孩子在数学、物理或化学学习里，哪件事最让你担心？像发微信一样说一段就行：哪一科、发生了什么、孩子怎么反应、你当时怎么帮。"
                )]
            )

        # 用 LLM 生成开场白
        session.history.append({"role": "user", "content": FIRST_TURN_USER_MESSAGE})
        result = self._call_llm(session)
        session.history.append({"role": "assistant", "content": self._raw_response_cache})
        session.turn_count += 1
        self._remember_pending_ui_block(session, result)

        return session, result

    def process_user_input(
        self,
        session: ConversationSession,
        text: str | None = None,
        selected_option_ids: list[str] | None = None,
        selected_labels: list[str] | None = None,
        ui_block_id: str | None = None,
    ) -> AgentTurnResult:
        """处理用户的一轮输入"""
        # 构建用户消息
        parts = []
        if ui_block_id:
            parts.append(f"（正在回答追问ID：{ui_block_id}）")
            if session.pending_ui_block_id and ui_block_id != session.pending_ui_block_id:
                parts.append(f"（注意：服务端当前等待的追问ID是：{session.pending_ui_block_id}，本轮可能来自旧卡片或用户自由补充。）")
        if text:
            parts.append(text)
        if selected_labels:
            parts.append(f"（用户选择了：{'、'.join(selected_labels)}）")
        elif selected_option_ids:
            parts.append(f"（用户选择了选项：{'、'.join(selected_option_ids)}）")

        user_message = " ".join(parts) if parts else "（用户跳过了这个问题）"
        session.history.append({"role": "user", "content": user_message})
        session.turn_count += 1

        # P0 修复：无论 LLM 是否可用，始终收集规则信号
        # 这样 LLM 模式下用户的选项选择也会被记录到评分管道
        self._record_rule_signals(
            session=session,
            text=text,
            selected_option_ids=selected_option_ids or [],
            selected_labels=selected_labels or [],
            ui_block_id=ui_block_id,
        )

        if not self.adapter.is_ready():
            return self._fallback_response(session)

        # 如果已经到了最大轮次，强制要求出结果
        force_conclude = session.turn_count >= self.MAX_TURNS

        result = self._call_llm(session, force_conclude=force_conclude)
        session.history.append({"role": "assistant", "content": self._raw_response_cache})
        self._remember_pending_ui_block(session, result)

        # P0 修复：LLM 说要出结论时，用规则评分做交叉校验
        if result.should_conclude and result.result:
            result = self._ground_with_rules(session, result)

        if result.should_conclude:
            session.is_complete = True

        return result

    def _remember_pending_ui_block(self, session: ConversationSession, result: AgentTurnResult) -> None:
        """记录当前等待用户回答的 UI block，保证多轮对话有明确追问 ID。"""
        ui_block = None
        for message in reversed(result.messages):
            if message.ui_block:
                ui_block = message.ui_block
                break

        if ui_block:
            session.pending_ui_block_id = str(ui_block.get("id") or "")
            session.pending_ui_block_type = str(ui_block.get("type") or "")
        else:
            session.pending_ui_block_id = None
            session.pending_ui_block_type = None

    # ---- 中文标签 → FactorCode 反向映射（模块级缓存） ----
    _LABEL_TO_FACTOR: dict[str, FactorCode] | None = None

    @classmethod
    def _label_to_factor_map(cls) -> dict[str, FactorCode]:
        if cls._LABEL_TO_FACTOR is None:
            cls._LABEL_TO_FACTOR = {label: code for code, label in FACTOR_PUBLIC_LABELS.items()}
        return cls._LABEL_TO_FACTOR

    def _ground_with_rules(self, session: ConversationSession, llm_result: AgentTurnResult) -> AgentTurnResult:
        """P0 修复：用规则评分校验 LLM 结论，双路径交叉验证。

        1. 从 session.fallback_option_ids 计算规则评分
        2. LLM primary_factor（中文）→ FactorCode 反向查找
        3. 一致 → 高置信，使用 LLM 文案
        4. 不一致 → 以规则评分为主，标记需人工复核
        5. 合并 evidence/missing_information
        """
        llm_data = llm_result.result or {}
        rule_scores = accumulate_scores(session.fallback_subject, session.fallback_option_ids)

        # 规则评分排序
        sorted_rules = sorted(rule_scores.items(), key=lambda item: item[1], reverse=True)
        rule_top1 = sorted_rules[0][0] if sorted_rules else None
        rule_top3 = [factor for factor, _ in sorted_rules[:3]]

        # LLM primary_factor 反向查找 FactorCode
        llm_primary_label = str(llm_data.get("primary_factor") or "")
        label_map = self._label_to_factor_map()
        llm_primary_code = label_map.get(llm_primary_label)

        # ----- 交叉校验 -----
        is_aligned = (llm_primary_code is not None and llm_primary_code == rule_top1)

        if is_aligned:
            # 一致：信任 LLM 文案，补充规则 evidence
            primary_code = llm_primary_code
            secondary_codes = [
                label_map.get(label)
                for label in (llm_data.get("secondary_factors") or [])
                if label_map.get(label) and label_map.get(label) != primary_code
            ][:2]
            human_review = False
        elif rule_top1 and rule_scores.get(rule_top1, 0) >= 1.5:
            # 不一致但规则有足够信号：以规则为主
            primary_code = rule_top1
            secondary_codes = rule_top3[1:3] if len(rule_top3) >= 2 else []
            # 如果 LLM 也有判断，作为次因子备选
            if llm_primary_code and llm_primary_code not in secondary_codes and llm_primary_code != primary_code:
                secondary_codes.append(llm_primary_code)
            secondary_codes = secondary_codes[:2]
            human_review = True
        else:
            # 规则信号太弱，保留 LLM 原始判断但标记低置信
            primary_code = llm_primary_code or rule_top1
            secondary_codes = (
                [label_map.get(label) for label in (llm_data.get("secondary_factors") or []) if label_map.get(label)]
                if llm_primary_code
                else rule_top3[1:3]
            )
            human_review = True

        primary_label = FACTOR_PUBLIC_LABELS.get(primary_code, str(primary_code))
        action = FACTOR_ACTIONS.get(primary_code, FACTOR_ACTIONS[FactorCode.F07_METACOGNITION])

        # ----- 合并 evidence -----
        rule_evidence = [
            OPTION_PUBLIC_LABELS.get(option_id, option_id)
            for option_id in session.fallback_option_ids
            if option_id in OPTION_PUBLIC_LABELS
        ]
        llm_evidence = llm_data.get("evidence") or []
        merged_evidence = list(dict.fromkeys(llm_evidence + rule_evidence))[:6]
        if not merged_evidence:
            merged_evidence = ["当前主要依据来自家长自然描述，证据还偏少。"]

        # ----- 合并 missing_information -----
        llm_missing = llm_data.get("missing_information") or []
        rule_missing: list[str] = []
        if not session.fallback_option_ids:
            rule_missing.append("还缺孩子自己的说法或一道具体错题。")
        merged_missing = list(dict.fromkeys(llm_missing + rule_missing))

        # ----- 构建最终 result -----
        secondary_labels = [FACTOR_PUBLIC_LABELS.get(code, "") for code in secondary_codes if code]

        grounded_result: dict[str, Any] = {
            "subject": session.fallback_subject.value if session.fallback_subject != Subject.UNKNOWN else llm_data.get("subject", "unknown"),
            "primary_factor": primary_label,
            "primary_desc": llm_data.get("primary_desc", f"目前线索最集中在「{primary_label}」。"),
            "secondary_factors": secondary_labels,
            "evidence": merged_evidence,
            "missing_information": merged_missing,
            "parent_common_mistake": action["mistake"],
            "next_7_days_stop": action["stop"],
            "next_7_days_start": action["start"],
            "public_summary": llm_data.get("public_summary", (
                f"目前更像是「{primary_label}」在优先影响这次理科学习。"
                f"先不要把问题扩大成孩子不努力，未来 7 天只观察一个小动作：{action['start']}"
            )),
            "human_review_needed": human_review,
            "cross_validation": "aligned" if is_aligned else "rule_override" if rule_top1 and rule_scores.get(rule_top1, 0) >= 1.5 else "weak_signal",
        }

        return AgentTurnResult(
            messages=llm_result.messages,
            should_conclude=True,
            result=grounded_result,
            thinking=llm_result.thinking,
            collected_signals=llm_result.collected_signals,
        )

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
        ui_block = self._normalize_ui_block(data.get("ui_block"))
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

    def _normalize_ui_block(self, ui_block: Any) -> dict[str, Any] | None:
        """把 LLM 生成的 UI block 规整成前端稳定可执行的结构。"""
        if not isinstance(ui_block, dict):
            return None

        block = deepcopy(ui_block)
        block_type = str(block.get("type") or "single_choice")
        title = str(block.get("title") or "")
        body = str(block.get("body") or "")
        block_id = str(block.get("id") or "")
        semantic_text = f"{block_id} {title} {body}"

        # P2 修复：用多模式组合判断，避免单关键词（如"AI"）误触发
        MULTI_SIGNALS = [
            r"多选",
            r"可以多选",
            r"可能不止",
            r"通常会|一般会|最常",
            r"哪些|哪种.*帮",
            r"怎么帮|帮助方式",
        ]
        should_be_multi = any(re.search(pat, semantic_text) for pat in MULTI_SIGNALS)

        if should_be_multi:
            block_type = "multi_choice"

        block["type"] = block_type
        block.setdefault("allow_free_text", True)
        block.setdefault("free_text_label", "都不像，我自己说")
        block.setdefault("free_text_placeholder", "用你自己的话说，不用选上面的。")

        if block_type == "multi_choice":
            block.setdefault("allow_skip", True)
            block.setdefault("min_select", 1)
            block.setdefault("max_select", 3)

        options = block.get("options")
        if not isinstance(options, list):
            block["options"] = []

        return block

    def _record_rule_signals(
        self,
        session: ConversationSession,
        text: str | None,
        selected_option_ids: list[str],
        selected_labels: list[str],
        ui_block_id: str | None,
    ) -> None:
        if ui_block_id:
            session.fallback_asked_block_ids.add(ui_block_id)

        subject_map = {
            "subject_math": Subject.MATH,
            "math": Subject.MATH,
            "subject_physics": Subject.PHYSICS,
            "physics": Subject.PHYSICS,
            "subject_chemistry": Subject.CHEMISTRY,
            "chemistry": Subject.CHEMISTRY,
        }

        for option_id in selected_option_ids:
            if option_id in subject_map:
                session.fallback_subject = subject_map[option_id]
            elif option_id and not option_id.startswith("_"):
                session.fallback_option_ids.append(option_id)

        combined_text = " ".join([text or "", " ".join(selected_labels or [])]).strip()
        if combined_text:
            inferred_subject = infer_subject_from_text(combined_text)
            if session.fallback_subject == Subject.UNKNOWN and inferred_subject != Subject.UNKNOWN:
                session.fallback_subject = inferred_subject
            # P0 修复：只对用户自由文本做 option_id 推断，不对 UI 标签文本推断
            # 避免标签中文文本（如"看懂答案"）被正则误匹配注入假 option_id
            if text and text.strip():
                session.fallback_option_ids.extend(infer_option_ids_from_text(text.strip()))

        session.fallback_option_ids = list(dict.fromkeys(session.fallback_option_ids))

    def _fallback_response(self, session: ConversationSession) -> AgentTurnResult:
        """LLM 不可用时的降级回复"""
        option_ids = set(session.fallback_option_ids)

        if session.fallback_subject == Subject.UNKNOWN and "fallback_subject_select" not in session.fallback_asked_block_ids:
            return self._fallback_question(
                session,
                text="我先把范围收窄一点。这件事主要发生在哪一科？如果你已经说过，也可以直接用自己的话补充。",
                ui_block={
                    "type": "single_choice",
                    "id": "fallback_subject_select",
                    "title": "主要是哪一科？",
                    "allow_free_text": True,
                    "free_text_label": "我自己说",
                    "free_text_placeholder": "比如：主要是物理电路题。",
                    "options": [
                        {"id": "subject_math", "label": "数学"},
                        {"id": "subject_physics", "label": "物理"},
                        {"id": "subject_chemistry", "label": "化学"},
                    ],
                },
            )

        stuck_ids = {
            "stuck_read_problem",
            "stuck_concept_formula",
            "stuck_transform",
            "stuck_select_method",
            "stuck_execution",
            "stuck_repeat_after_answer",
            "stuck_emotional_avoidance",
            "stuck_attention_overload",
            "stuck_confident_wrong_idea",
        }
        if not option_ids.intersection(stuck_ids) and "fallback_stuck_step" not in session.fallback_asked_block_ids:
            return self._fallback_question(
                session,
                text="我听到的是一次真实卡住。只看这一次，更像先卡在哪一步？可以选一个，也可以自己说。",
                ui_block={
                    "type": "single_choice",
                    "id": "fallback_stuck_step",
                    "title": "更像卡在哪一步？",
                    "allow_free_text": True,
                    "free_text_label": "都不像，我自己说",
                    "free_text_placeholder": "比如：题目条件太多，他一下就乱了。",
                    "options": [
                        {"id": "stuck_read_problem", "label": "题目读完，不确定在问什么"},
                        {"id": "stuck_concept_formula", "label": "概念或公式知道，但说不清"},
                        {"id": "stuck_transform", "label": "不知道怎么画图、列式或转化"},
                        {"id": "stuck_select_method", "label": "不知道选哪个方法或公式"},
                        {"id": "stuck_execution", "label": "会做但步骤、计算、单位总出错"},
                        {"id": "stuck_repeat_after_answer", "label": "看答案懂了，下次又不会"},
                        {"id": "stuck_attention_overload", "label": "条件一多就乱、漏条件"},
                        {"id": "stuck_confident_wrong_idea", "label": "孩子很笃定，但理解方向错了"},
                    ],
                },
            )

        subject_probe = self._fallback_subject_probe(session)
        if subject_probe:
            return subject_probe

        parent_ids = {
            "parent_explain_full_solution",
            "parent_add_more_exercises",
            "parent_ask_breakpoint",
            "parent_ai_gives_answer",
            "parent_review_then_retest",
        }
        if not option_ids.intersection(parent_ids) and "fallback_parent_support" not in session.fallback_asked_block_ids:
            return self._fallback_question(
                session,
                text="这个时候你一般会怎么帮？这里可能不止一种，选最常发生的就行。",
                ui_block={
                    "type": "multi_choice",
                    "id": "fallback_parent_support",
                    "title": "你当时一般怎么帮？",
                    "body": "可以多选。不是评判你对错，是看帮助方式和卡点是否对位。",
                    "allow_skip": True,
                    "allow_free_text": True,
                    "free_text_label": "我家的情况不太一样",
                    "free_text_placeholder": "比如：我会先让他讲思路，但讲着讲着就变成我在讲。",
                    "min_select": 1,
                    "max_select": 3,
                    "options": [
                        {"id": "parent_explain_full_solution", "label": "我会直接讲完整解法"},
                        {"id": "parent_add_more_exercises", "label": "我会让他多做几道类似题"},
                        {"id": "parent_ask_breakpoint", "label": "我会先问他从哪一步不会"},
                        {"id": "parent_ai_gives_answer", "label": "会让 AI 或软件讲答案"},
                        {"id": "parent_review_then_retest", "label": "会复盘并隔天重做"},
                    ],
                },
            )

        review_ids = {
            "probe_cannot_name_breakpoint",
            "probe_only_reads_answer",
            "probe_ai_answer_first",
            "probe_parent_takes_over",
            "probe_many_conditions_overload",
            "probe_confident_but_wrong_rule",
            "probe_emotion_blocks_start",
        }
        if not option_ids.intersection(review_ids) and "fallback_review_probe" not in session.fallback_asked_block_ids:
            return self._fallback_question(
                session,
                text="最后我再确认一个会影响准确率的点：错题或难题之后，最常发生什么？",
                ui_block={
                    "type": "multi_choice",
                    "id": "fallback_review_probe",
                    "title": "后面通常会发生什么？",
                    "allow_skip": True,
                    "allow_free_text": True,
                    "free_text_label": "我自己说",
                    "free_text_placeholder": "比如：他当时说懂了，但第二天不愿意再碰。",
                    "min_select": 1,
                    "max_select": 3,
                    "options": [
                        {"id": "probe_cannot_name_breakpoint", "label": "孩子说不清第一处断点"},
                        {"id": "probe_only_reads_answer", "label": "主要看懂答案，很少隔天独立重做"},
                        {"id": "probe_ai_answer_first", "label": "很快找 AI 或答案"},
                        {"id": "probe_parent_takes_over", "label": "父母会接管思路，孩子主要听"},
                        {"id": "probe_many_conditions_overload", "label": "条件一多就乱"},
                        {"id": "probe_confident_but_wrong_rule", "label": "很有把握，但规则用错"},
                        {"id": "probe_emotion_blocks_start", "label": "明显烦躁、紧张或逃开"},
                    ],
                },
            )

        result = self._compose_fallback_result(session)
        session.is_complete = True
        session.pending_ui_block_id = None
        session.pending_ui_block_type = None
        return AgentTurnResult(
            messages=[AgentMessage(text="我先按你刚才说到的线索，整理一个可执行的判断。")],
            should_conclude=True,
            result=result,
        )

    def _fallback_subject_probe(self, session: ConversationSession) -> AgentTurnResult | None:
        subject = session.fallback_subject
        option_ids = set(session.fallback_option_ids)
        probe_ids_by_subject = {
            Subject.MATH: {
                "block_id": "fallback_math_probe",
                "ids": {"math_same_template_ok_variant_fail", "math_symbol_condition_missed", "math_multi_condition_overload"},
                "text": "数学里我再收窄一点，哪种更像？",
                "options": [
                    {"id": "math_same_template_ok_variant_fail", "label": "例题同款能做，变式不会"},
                    {"id": "math_symbol_condition_missed", "label": "题干条件、符号或图形关系常漏掉"},
                    {"id": "math_multi_condition_overload", "label": "条件一多就乱、漏条件"},
                ],
            },
            Subject.PHYSICS: {
                "block_id": "fallback_physics_probe",
                "ids": {"physics_no_diagram", "physics_formula_without_quantity_meaning", "physics_naive_force_motion", "physics_direction_sign_confusion"},
                "text": "物理里我再收窄一点，哪种更像？",
                "options": [
                    {"id": "physics_no_diagram", "label": "不画过程图、受力图或电路图就套公式"},
                    {"id": "physics_formula_without_quantity_meaning", "label": "公式会背，但每个量代表什么说不清"},
                    {"id": "physics_naive_force_motion", "label": "容易被直觉经验带偏"},
                    {"id": "physics_direction_sign_confusion", "label": "方向、正负号或单位容易混乱"},
                ],
            },
            Subject.CHEMISTRY: {
                "block_id": "fallback_chemistry_probe",
                "ids": {"chem_symbol_equation_mismatch", "chem_rule_cannot_transfer", "chem_conservation_or_valence_misconception"},
                "text": "化学里我再收窄一点，哪种更像？",
                "options": [
                    {"id": "chem_symbol_equation_mismatch", "label": "现象、粒子变化和方程式对不上"},
                    {"id": "chem_rule_cannot_transfer", "label": "反应规律换到新物质就不会用"},
                    {"id": "chem_conservation_or_valence_misconception", "label": "守恒、化合价或微粒观念理解偏了"},
                ],
            },
        }
        config = probe_ids_by_subject.get(subject)
        if not config:
            return None
        block_id = config["block_id"]
        if block_id in session.fallback_asked_block_ids or option_ids.intersection(config["ids"]):
            return None
        return self._fallback_question(
            session,
            text=str(config["text"]),
            ui_block={
                "type": "single_choice",
                "id": block_id,
                "title": str(config["text"]),
                "allow_free_text": True,
                "free_text_label": "都不像，我自己说",
                "free_text_placeholder": "用你自己的话补一句具体表现。",
                "options": config["options"],
            },
        )

    def _fallback_question(
        self,
        session: ConversationSession,
        text: str,
        ui_block: dict[str, Any],
    ) -> AgentTurnResult:
        session.pending_ui_block_id = str(ui_block.get("id") or "")
        session.pending_ui_block_type = str(ui_block.get("type") or "")
        return AgentTurnResult(messages=[AgentMessage(text=text, ui_block=ui_block)])

    def _compose_fallback_result(self, session: ConversationSession) -> dict[str, Any]:
        scores = accumulate_scores(session.fallback_subject, session.fallback_option_ids)
        if not scores:
            scores = {FactorCode.F07_METACOGNITION: 1.0}

        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        primary = sorted_scores[0][0]
        secondary = [factor for factor, _ in sorted_scores[1:3]]
        action = FACTOR_ACTIONS[primary]

        evidence = [
            OPTION_PUBLIC_LABELS.get(option_id, option_id)
            for option_id in session.fallback_option_ids
            if option_id in OPTION_PUBLIC_LABELS
        ]
        if not evidence:
            evidence = ["当前主要依据来自家长自然描述，证据还偏少。"]

        primary_label = FACTOR_PUBLIC_LABELS[primary]
        return {
            "subject": session.fallback_subject.value,
            "primary_factor": primary_label,
            "primary_desc": f"目前线索最集中在「{primary_label}」。这个判断来自最近一次卡住事件，需要后续结合具体题目继续校准。",
            "secondary_factors": [FACTOR_PUBLIC_LABELS[factor] for factor in secondary],
            "evidence": evidence[:6],
            "missing_information": [] if len(evidence) >= 3 else ["还缺孩子自己的说法或一道具体错题。"],
            "parent_common_mistake": action["mistake"],
            "next_7_days_stop": action["stop"],
            "next_7_days_start": action["start"],
            "public_summary": (
                f"目前更像是「{primary_label}」在优先影响这次理科学习。"
                f"先不要把问题扩大成孩子不努力，未来 7 天只观察一个小动作：{action['start']}"
            ),
        }
