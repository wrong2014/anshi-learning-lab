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
    fallback_grade: int = 0  # 0=未识别, 1-12=年级


class ConversationAgent:
    """LLM 驱动的对话式智能体"""

    MAX_TURNS = 8  # 安全阀：最多 8 轮对话后强制出结果

    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    # ---- 年级工具 ----
    @staticmethod
    def _grade_bucket(grade: int) -> str:
        """年级分桶"""
        if grade <= 2:
            return "lower"       # 低年级 1-2
        if grade <= 4:
            return "middle"      # 中年级 3-4
        if grade <= 6:
            return "upper"       # 高年级 5-6
        if grade <= 9:
            return "junior"      # 初中 7-9
        return "senior"          # 高中 10-12

    @staticmethod
    def _grade_label(grade: int) -> str:
        """年级中文描述"""
        if grade == 0:
            return ""
        if grade <= 6:
            return f"{'一二三四五六'[grade - 1]}年级"
        if grade <= 9:
            return f"初{'一二三'[grade - 7]}"
        return f"高{'一二三'[grade - 10]}"

    # 年级不适用的选项 ID（低年级应过滤掉）
    _GRADE_FILTER_OPTIONS: dict[str, set[str]] = {
        "lower": {
            "math_calc_decimal_point",   # 低年级没学小数
            "math_calc_multistep_break", # 低年级没有多步复杂计算
            "math_method_no_idea", "math_method_unsure", "math_method_right_but_why",
            "phys_calc_multistep_lost", "phys_method_no_idea", "phys_method_confuse_law",
            "chem_calc_balance", "chem_calc_valence", "chem_calc_mole_mass",
            "chem_method_no_idea", "chem_method_cant_transfer",
        },
        "middle": {
            "math_calc_decimal_point",   # 3-4年级小数刚学，可作为选项但不过滤
            "chem_calc_balance", "chem_calc_mole_mass",  # 化学未开始
        },
    }

    def start_session(self) -> tuple[ConversationSession, AgentTurnResult]:
        """开始一个新的对话会话"""
        session = ConversationSession()

        if not self.adapter.is_ready():
            # LLM 不可用时的降级处理
            return session, AgentTurnResult(
                messages=[AgentMessage(
                    text="嗨，我是你的学习诊断助手～你先跟我聊聊：孩子最近学数学、物理或者化学，有没有哪件事让你特别头疼？就像跟朋友发微信一样说就行——哪一科、当时发生了什么、孩子什么反应、你当时怎么弄的。不用写很长，几句话就好。"
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
            if text and text.strip():
                session.fallback_option_ids.extend(infer_option_ids_from_text(text.strip()))
            # 提取年级
            if session.fallback_grade == 0:
                session.fallback_grade = self._extract_grade(combined_text)

        session.fallback_option_ids = list(dict.fromkeys(session.fallback_option_ids))

    @staticmethod
    def _extract_grade(text: str) -> int:
        """从文本中提取年级数字。0 表示未识别。"""
        import re as _re
        # 小学：一年级～六年级 → 1-6
        m = _re.search(r"([一二三四五六])(?:年|年级)", text)
        if m:
            return {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}.get(m.group(1), 0)
        # 初一/初二/初三 → 7-9
        m = _re.search(r"初([一二三])", text)
        if m:
            return {"一": 7, "二": 8, "三": 9}.get(m.group(1), 0)
        # 高一/高二/高三 → 10-12
        m = _re.search(r"高([一二三])", text)
        if m:
            return {"一": 10, "二": 11, "三": 12}.get(m.group(1), 0)
        # 纯数字: 1年级, 2年级
        m = _re.search(r"(\d+)\s*(?:年|年级)", text)
        if m:
            g = int(m.group(1))
            return g if 1 <= g <= 12 else 0
        return 0

    def _fallback_response(self, session: ConversationSession) -> AgentTurnResult:
        """LLM 不可用时的降级回复"""
        option_ids = set(session.fallback_option_ids)

        if session.fallback_subject == Subject.UNKNOWN and "fallback_subject_select" not in session.fallback_asked_block_ids:
            return self._fallback_question(
                session,
                text="我先确认一下，这件事主要是哪一科？如果你之前已经提过，就点一下就好。",
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
                text="我听下来，孩子确实遇到坎了。你感觉他最容易在哪一步卡住？选最像的一个就行。",
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
                text="孩子卡住的时候，你一般会怎么做？可以多选，这个没有对错，我就是想看看你的方式和孩子的卡点是不是一个频道的。",
                ui_block={
                    "type": "multi_choice",
                    "id": "fallback_parent_support",
                    "title": "你一般会怎么帮？",
                    "body": "可以多选。选你平时最常做的就行，不用纠结。",
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
                text="最后一个问题～题目做错或者卡住之后，你家通常接下来会发生什么？",
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
            messages=[AgentMessage(text="好的，我帮你理了一下，下面是我的判断～")],
            should_conclude=True,
            result=result,
        )

    # ---- 动态学科探针：根据用户选的 stuck_step 匹配追问 ----
    _DYNAMIC_PROBES: dict[Subject, dict[str, dict]] = {
        Subject.MATH: {
            "stuck_execution": {
                "text": "数学计算出错，更像是哪一种？我想定位到具体环节。",
                "options": [
                    {"id": "math_calc_carry_borrow", "label": "进退位、借位容易错"},
                    {"id": "math_calc_miscopy", "label": "抄错数字、符号或漏写"},
                    {"id": "math_calc_decimal_point", "label": "小数点、分数约分常出错"},
                    {"id": "math_calc_multistep_break", "label": "多步计算中间某步断掉或记错"},
                ],
            },
            "stuck_concept_formula": {
                "text": "概念理解上，哪种情况更多？",
                "options": [
                    {"id": "math_concept_recite_only", "label": "公式定义会背，但不会解释为什么"},
                    {"id": "math_concept_confuse", "label": "容易混淆相似概念或公式"},
                    {"id": "math_concept_real_meaning", "label": "说不清算式每一步在算什么"},
                ],
            },
            "stuck_read_problem": {
                "text": "读题时，更接近哪种情况？",
                "options": [
                    {"id": "math_read_miss_condition", "label": "漏看条件、数字或单位"},
                    {"id": "math_read_unsure_keyword", "label": "不确定关键词（如'至少''不超过'）"},
                    {"id": "math_read_not_understand_ask", "label": "读完不知道题目到底问什么"},
                ],
            },
            "stuck_transform": {
                "text": "转化这一步，更卡在哪里？",
                "options": [
                    {"id": "math_trans_text_to_expr", "label": "文字描述转不成算式或方程"},
                    {"id": "math_trans_cant_draw", "label": "不会画线段图、示意图来帮忙"},
                    {"id": "math_trans_table_relation", "label": "不会列表格或梳理数量关系"},
                ],
            },
            "stuck_select_method": {
                "text": "选方法时，更像哪种情况？",
                "options": [
                    {"id": "math_method_no_idea", "label": "不知道用什么公式或方法"},
                    {"id": "math_method_unsure", "label": "感觉会用但不确定对不对"},
                    {"id": "math_method_right_but_why", "label": "经常选对但说不清为什么选它"},
                ],
            },
            "stuck_repeat_after_answer": {
                "text": "这道题的类型，之前遇到过吗？",
                "options": [
                    {"id": "math_repeat_same_ok_variant_fail", "label": "同款题当时能做，换个数就不会"},
                    {"id": "math_repeat_understand_then_forget", "label": "当时说懂了，过两天完全不记得"},
                    {"id": "math_repeat_only_cram", "label": "主要靠考前突击，考完就忘"},
                ],
            },
            "stuck_attention_overload": {
                "text": "什么时候最容易乱？",
                "options": [
                    {"id": "math_attn_multi_condition", "label": "题目条件超过3个就开始丢"},
                    {"id": "math_attn_composite", "label": "单独知识点会，综合题就乱"},
                    {"id": "math_attn_midway_forget", "label": "做到后面忘了前面算什么"},
                ],
            },
            "stuck_confident_wrong_idea": {
                "text": "孩子很笃定但错了，更像哪种？",
                "options": [
                    {"id": "math_wrong_causal_direction", "label": "因果关系搞反了"},
                    {"id": "math_wrong_intuitive_rule", "label": "用生活经验代替数学规则"},
                    {"id": "math_wrong_previous_misunderstand", "label": "之前某个知识点就理解错了"},
                ],
            },
        },
        Subject.PHYSICS: {
            "stuck_execution": {
                "text": "物理计算出错或步骤问题，更像哪种？",
                "options": [
                    {"id": "phys_calc_unit_direction", "label": "单位、方向、正负号容易搞混"},
                    {"id": "phys_calc_formula_sub", "label": "公式会选但代入数字总出错"},
                    {"id": "phys_calc_multistep_lost", "label": "多步推导中间漏了关键一步"},
                ],
            },
            "stuck_concept_formula": {
                "text": "物理概念理解，更像哪种？",
                "options": [
                    {"id": "phys_concept_formula_no_meaning", "label": "公式会背，但每个量代表什么说不清"},
                    {"id": "phys_concept_naive_theory", "label": "容易被直觉经验带偏"},
                    {"id": "phys_concept_cant_explain", "label": "能算对但讲不出为什么"},
                ],
            },
            "stuck_read_problem": {
                "text": "物理读题，更像哪种？",
                "options": [
                    {"id": "phys_read_miss_condition", "label": "漏看条件或物理量"},
                    {"id": "phys_read_unsure_scene", "label": "不确定题目描述的是什么场景"},
                ],
            },
            "stuck_transform": {
                "text": "物理建模，卡在哪一步？",
                "options": [
                    {"id": "phys_trans_no_diagram", "label": "不画受力图/过程图/电路图就套公式"},
                    {"id": "phys_trans_scene_to_model", "label": "文字场景转化不成物理模型"},
                ],
            },
            "stuck_select_method": {
                "text": "选方法时更像哪种？",
                "options": [
                    {"id": "phys_method_no_idea", "label": "不知道用哪个公式或定律"},
                    {"id": "phys_method_confuse_law", "label": "混淆相似定律或公式"},
                ],
            },
            "stuck_repeat_after_answer": {
                "text": "物理题复测时？",
                "options": [
                    {"id": "phys_repeat_template_ok", "label": "同类题能做，换个情景就不会"},
                    {"id": "phys_repeat_forget_quickly", "label": "看懂后过两天又不会了"},
                ],
            },
            "stuck_attention_overload": {
                "text": "物理题什么时候最乱？",
                "options": [
                    {"id": "phys_attn_multi_object", "label": "题目涉及多物体/多过程就乱"},
                    {"id": "phys_attn_composite", "label": "力学电学混合题完全理不清"},
                ],
            },
            "stuck_confident_wrong_idea": {
                "text": "物理直觉出错，更像哪种？",
                "options": [
                    {"id": "phys_wrong_force_motion", "label": "力与运动关系直觉错误"},
                    {"id": "phys_wrong_current_consumed", "label": "认为电流会被用电器消耗"},
                ],
            },
        },
        Subject.CHEMISTRY: {
            "stuck_execution": {
                "text": "化学计算或书写，更像哪种错？",
                "options": [
                    {"id": "chem_calc_balance", "label": "方程式配平容易出错"},
                    {"id": "chem_calc_valence", "label": "化合价或化学式写错"},
                    {"id": "chem_calc_mole_mass", "label": "物质的量或质量计算混乱"},
                ],
            },
            "stuck_concept_formula": {
                "text": "化学概念理解，更像哪种？",
                "options": [
                    {"id": "chem_concept_particle_confuse", "label": "分不清原子、分子、离子"},
                    {"id": "chem_concept_conservation", "label": "守恒观念没有真正建立"},
                ],
            },
            "stuck_read_problem": {
                "text": "化学读题，更像哪种？",
                "options": [
                    {"id": "chem_read_miss_condition", "label": "漏看物质状态或反应条件"},
                    {"id": "chem_read_unsure_symbol", "label": "化学式或符号不认识"},
                ],
            },
            "stuck_transform": {
                "text": "化学表征，卡在哪？",
                "options": [
                    {"id": "chem_trans_macro_micro", "label": "宏观现象和微观粒子对不上"},
                    {"id": "chem_trans_equation_to_scene", "label": "方程式和实验场景联系不起来"},
                ],
            },
            "stuck_select_method": {
                "text": "化学推断，更像哪种？",
                "options": [
                    {"id": "chem_method_no_idea", "label": "不知道从哪个物质或反应入手"},
                    {"id": "chem_method_cant_transfer", "label": "反应规律换到新物质就不会用"},
                ],
            },
            "stuck_repeat_after_answer": {
                "text": "化学复测时？",
                "options": [
                    {"id": "chem_repeat_template_ok", "label": "同类题换物质就不会"},
                    {"id": "chem_repeat_forget_quickly", "label": "看完答案过两天忘"},
                ],
            },
            "stuck_attention_overload": {
                "text": "化学题什么时候最乱？",
                "options": [
                    {"id": "chem_attn_multi_step", "label": "推断流程一多就乱"},
                    {"id": "chem_attn_mix_calc", "label": "实验+计算混合题理不清"},
                ],
            },
            "stuck_confident_wrong_idea": {
                "text": "化学直觉出错，更像哪种？",
                "options": [
                    {"id": "chem_wrong_valence_misconception", "label": "化合价或电子观念理解偏差"},
                    {"id": "chem_wrong_reaction_rule", "label": "反应规律用反或套错"},
                ],
            },
        },
    }

    def _fallback_subject_probe(self, session: ConversationSession) -> AgentTurnResult | None:
        subject = session.fallback_subject
        option_ids = set(session.fallback_option_ids)
        block_id_map = {
            Subject.MATH: "fallback_math_probe",
            Subject.PHYSICS: "fallback_physics_probe",
            Subject.CHEMISTRY: "fallback_chemistry_probe",
        }
        block_id = block_id_map.get(subject)
        if not block_id:
            return None
        if block_id in session.fallback_asked_block_ids:
            return None

        # 找出用户选的 stuck_step
        stuck_step_ids = {
            "stuck_execution", "stuck_concept_formula", "stuck_read_problem",
            "stuck_transform", "stuck_select_method", "stuck_repeat_after_answer",
            "stuck_attention_overload", "stuck_confident_wrong_idea",
            "stuck_emotional_avoidance",
        }
        matched_stuck = option_ids.intersection(stuck_step_ids)
        stuck_step = next(iter(matched_stuck), None)

        # 根据 stuck_step 选择动态探针，无匹配时用通用探针
        subject_probes = self._DYNAMIC_PROBES.get(subject, {})
        probe = subject_probes.get(stuck_step or "") if stuck_step else None

        if probe:
            config = {
                "block_id": block_id,
                "text": probe["text"],
                "options": probe["options"],
                "ids": {opt["id"] for opt in probe["options"]},
            }
        else:
            # 通用兜底：保留原逻辑，问学科经典问题
            fallback_probes = {
                Subject.MATH: {
                    "text": "数学里我再收窄一点，哪种更像？",
                    "options": [
                        {"id": "math_same_template_ok_variant_fail", "label": "例题同款能做，变式不会"},
                        {"id": "math_symbol_condition_missed", "label": "题干条件、符号或图形关系常漏掉"},
                        {"id": "math_multi_condition_overload", "label": "条件一多就乱、漏条件"},
                    ],
                },
                Subject.PHYSICS: {
                    "text": "物理里我再收窄一点，哪种更像？",
                    "options": [
                        {"id": "physics_no_diagram", "label": "不画过程图、受力图或电路图就套公式"},
                        {"id": "physics_formula_without_quantity_meaning", "label": "公式会背，但每个量代表什么说不清"},
                        {"id": "physics_naive_force_motion", "label": "容易被直觉经验带偏"},
                        {"id": "physics_direction_sign_confusion", "label": "方向、正负号或单位容易混乱"},
                    ],
                },
                Subject.CHEMISTRY: {
                    "text": "化学里我再收窄一点，哪种更像？",
                    "options": [
                        {"id": "chem_symbol_equation_mismatch", "label": "现象、粒子变化和方程式对不上"},
                        {"id": "chem_rule_cannot_transfer", "label": "反应规律换到新物质就不会用"},
                        {"id": "chem_conservation_or_valence_misconception", "label": "守恒、化合价或微粒观念理解偏了"},
                    ],
                },
            }
            fb = fallback_probes.get(subject)
            if not fb:
                return None
            config = {
                "block_id": block_id,
                "text": fb["text"],
                "options": fb["options"],
                "ids": {opt["id"] for opt in fb["options"]},
            }

        # 已经问过或已经覆盖了这些选项 → 跳过
        if option_ids.intersection(config["ids"]):
            return None

        # 按年级过滤不合适的选项
        options = config["options"]
        grade = session.fallback_grade
        if grade > 0:
            bucket = self._grade_bucket(grade)
            filter_set = self._GRADE_FILTER_OPTIONS.get(bucket, set())
            options = [opt for opt in options if opt["id"] not in filter_set]

        return self._fallback_question(
            session,
            text=config["text"],
            ui_block={
                "type": "single_choice",
                "id": block_id,
                "title": config["text"],
                "allow_free_text": True,
                "free_text_label": "都不像，我自己说",
                "free_text_placeholder": "用你自己的话补一句具体表现。",
                "options": options,
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

    # ---- 个性化建议库（口语版） ----
    _PERSONALIZED_ADVICE: dict[str, dict[str, str]] = {
        "math_calc_carry_borrow": {
            "problem_name": "进退位容易出错",
            "why_happens": (
                "{grade_opener}进退位容易出错，通常不是粗心——是当初学进退位的时候没有练到'不过脑子就能做对'的程度。"
                "后面题目一多，脑子要同时处理好几件事，进退位这个基本功就容易掉链子。"
            ),
            "try_this": (
                "每天就做5道进退位专项题，不贪多。每做一步让孩子念出来："
                "'个位8加7等于15，写5进1，十位变成...'——念出声是帮动作变成本能。"
            ),
        },
        "math_calc_miscopy": {
            "problem_name": "抄错数字或符号",
            "why_happens": (
                "抄错数字不是马虎，是孩子从题目到草稿纸这个过程里，眼睛和手没形成稳定的对接。"
                "很多孩子是'扫一眼就写'，中间漏了一拍。"
            ),
            "try_this": (
                "练一个小动作：抄完题目后，合上草稿纸，让孩子凭记忆把刚才抄的数字再默写一遍，"
                "然后跟原题对照。找到哪里不一样，他自己就会意识到漏在哪。"
            ),
        },
        "math_calc_decimal_point": {
            "problem_name": "小数点和分数易出错",
            "why_happens": (
                "小数点、约分这些，本质上不是计算问题，是'规则感'还没形成。"
                "孩子知道要小数点对齐、要约分，但做题时一紧张就忘了——这是正常的，需要反复练到变成条件反射。"
            ),
            "try_this": (
                "每天3道小数加减加3道分数约分。关键不是做完，是做完以后让孩子自己批改："
                "拿红笔标出哪个位置错了、为什么错。他自己发现了，下次才记得住。"
            ),
        },
        "math_calc_multistep_break": {
            "problem_name": "多步计算容易断掉",
            "why_happens": (
                "这不是孩子脑子不够用，是工作记忆还没练出来。多步计算需要同时记住中间结果和下一步操作，"
                "五年级的孩子大脑还在发育，这个能力有个体差异。"
            ),
            "try_this": (
                "把一张草稿纸折成小格子，每格只做一步，做完一格划一道线。"
                "这样孩子不用靠脑子记中间结果，眼睛一看就知道上一步算的是什么。"
            ),
        },
        "math_concept_recite_only": {
            "problem_name": "公式会背但不太理解",
            "try_this": (
                "让孩子用'自己的话'给你讲一遍这个概念是什么意思，不许用课本上的词。"
                "比如'分数就是披萨切了几块，拿了几块'——能用人话说出来，才是真懂了。"
            ),
        },
        "math_concept_confuse": {
            "problem_name": "容易混淆相似概念",
            "try_this": (
                "拿两张纸，左边写概念A，右边写概念B，中间写'哪里一样''哪里不一样'。"
                "自己画出来的对比表，比看十遍课本都管用。"
            ),
        },
        "_default": {
            "problem_name": "某个具体环节需要加强",
            "try_this": (
                "先不要急着加量，先把卡住的那一步单独揪出来，每天只练这一步，练稳了再往下走。"
            ),
        },
    }

    # ---- 因果链条库（口语版） ----
    _CAUSAL_LINKS: dict[str, str] = {
        ("parent_add_more_exercises", "probe_only_reads_answer"): (
            "你是不是也这样：看孩子出错就让他多做几道？但孩子那边呢，主要是把答案看懂了就过了，"
            "没有自己独立再做一遍。这样题是做了，但出错的那个点其实没练到——"
            "就像投篮姿势不对，你让他投100个，姿势还是错的。"
        ),
        ("parent_add_more_exercises", "probe_cannot_name_breakpoint"): (
            "你给孩子加了题量，但他其实说不清楚自己到底哪一步开始卡住的。"
            "这就有点像车坏了但你不知道哪里坏了，就一直在路上开——开再多也修不好。"
        ),
        ("parent_explain_full_solution", "probe_only_reads_answer"): (
            "你是不是习惯把整道题从头讲一遍？讲的时候孩子点头说明白了，"
            "但那是你在想，不是他在想。他需要自己从卡住的那一步重新走一遍，而不是听你走一遍。"
        ),
        ("parent_explain_full_solution", "probe_cannot_name_breakpoint"): (
            "你讲得很认真，但孩子说不出从哪一步开始不会的。"
            "这说明他在'接收'你的思路，不是在'参与'思考。下次换道题，他还是找不到那个断点。"
        ),
        ("parent_ai_gives_answer", "probe_only_reads_answer"): (
            "AI或大人很快给了答案，孩子看完觉得懂了——但这个'懂了'是假的。"
            "没有自己重新做一遍，明天遇到差不多的题照样错。这不是孩子的问题，是这个方式本身就容易造成假懂。"
        ),
        ("parent_add_more_exercises", "probe_ai_answer_first"): (
            "加题量加上较快给答案——两个加在一起，孩子其实没有经历过'自己死磕'的过程。"
            "而真正学会，往往就发生在他自己憋了半天终于想通的那一刻。"
        ),
        "_default_parent_strategy": (
            "你现在帮孩子的方式，和孩子真正卡住的那个点，可能有一点错位。"
            "调整一下方向，效果会明显不一样。"
        ),
    }

    # ---- 引流钩子库 ----
    _HOOKS: dict[str, str] = {
        "math": (
            "对了，刚才聊的主要是计算这一块。但计算出错有时候不只是计算本身的问题——"
            "往前倒一步，可能是更早的知识点没扎稳。{grade_hook}"
            "如果你想，可以跟我说说孩子这门课之前的考试情况，我帮你看看是不是前面有窟窿。"
        ),
        "physics": (
            "物理这一科比较特殊，很多孩子的卡点其实不在物理本身，而在数学工具没跟上。"
            "如果你想，可以跟我说说孩子数学学到什么程度了，我帮你看看是不是数学基础拖了物理的后腿。"
        ),
        "chemistry": (
            "化学刚开始学的时候，很多孩子是被符号和方程式吓住的，不一定真的不会。"
            "如果你想，可以跟我说说孩子是几年级开始学化学的、用的什么教材，我帮你判断一下是不是衔接问题。"
        ),
        "_default": (
            "每个孩子的卡点细节都不一样，刚才说的只是一个大方向。"
            "如果你愿意多聊几句——比如孩子最近一次考试卷子长什么样、哪道题错得最让你想不通——"
            "我可以帮你定位得更准，告诉你接下来具体怎么做。"
        ),
    }

    def _compose_fallback_result(self, session: ConversationSession) -> dict[str, Any]:
        scores = accumulate_scores(session.fallback_subject, session.fallback_option_ids)
        if not scores:
            scores = {FactorCode.F07_METACOGNITION: 1.0}

        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        primary = sorted_scores[0][0]
        secondary = [factor for factor, _ in sorted_scores[1:3]]
        option_ids = session.fallback_option_ids
        option_set = set(option_ids)

        # ---- 个性化建议 ----
        primary_label = FACTOR_PUBLIC_LABELS[primary]
        primary_action = FACTOR_ACTIONS[primary]

        personal = self._PERSONALIZED_ADVICE.get("_default")
        for oid in option_ids:
            if oid in self._PERSONALIZED_ADVICE:
                personal = self._PERSONALIZED_ADVICE[oid]
                break

        problem_name = personal.get("problem_name", "某个环节需要加强")
        why_happens = personal.get("why_happens", "")
        try_this = personal.get("try_this", primary_action["start"])

        # ---- 年级占位符替换 ----
        grade = session.fallback_grade
        grade_label = self._grade_label(grade)
        if grade_label:
            grade_opener = f"{grade_label}的孩子" if grade <= 6 else f"{grade_label}阶段"
        else:
            grade_opener = "很多孩子"

        # 年级钩子文案
        grade_hook_texts = {
            "lower": "比如20以内的进退位是不是真的过关了？数数和比大小的基础稳不稳？",
            "middle": "比如乘法口诀是不是到多位数就慢了？分数概念是不是只停留在背定义？",
            "upper": "比如小数和分数的转换是不是还有坑？应用题里的数量关系是不是靠猜？",
            "junior": "比如方程思想是不是还没建立？函数图像看得懂吗？",
            "senior": "比如函数和导数的关系是不是只是背公式？概率统计的直觉对不对？",
        }
        bucket = self._grade_bucket(grade) if grade > 0 else "upper"
        grade_hook = grade_hook_texts.get(bucket, grade_hook_texts["upper"])

        why_happens = why_happens.replace("{grade_opener}", grade_opener)

        # ---- 因果链 ----
        causal = self._build_causal_chain(option_set)

        # ---- 证据 ----
        evidence = [
            OPTION_PUBLIC_LABELS.get(oid, oid)
            for oid in option_ids
            if oid in OPTION_PUBLIC_LABELS
        ]
        if not evidence:
            evidence = ["根据你描述的情况"]

        # ---- 钩子 ----
        subject_key = session.fallback_subject.value if session.fallback_subject != Subject.UNKNOWN else "_default"
        hook = self._HOOKS.get(subject_key, self._HOOKS["_default"])
        hook = hook.replace("{grade_hook}", grade_hook)

        # ---- 构建 public_summary（口语版） ----
        evidence_line = "从你刚才说的情况来看"
        secondary_labels = [FACTOR_PUBLIC_LABELS[f] for f in secondary if f in FACTOR_PUBLIC_LABELS]

        parts = [
            f"{evidence_line}，孩子现在最突出的问题是「{problem_name}」。",
        ]
        if why_happens:
            parts.append(why_happens)
        parts.append(causal)
        parts.append(f"你可以先试一个小动作：{try_this}")
        parts.append("")
        parts.append(hook)
        parts.append("")
        parts.append("诊断进阶：如果想要更准确的判断，请准备两张孩子最近考完的大考试卷，拍照发给我，我可以定位到具体哪类题型、哪个知识点的哪个环节出了错。")

        public_summary = "\n\n".join(parts)

        return {
            "subject": session.fallback_subject.value,
            "primary_factor": primary_label,
            "primary_desc": f"主要是「{problem_name}」——{why_happens}" if why_happens else f"主要是「{problem_name}」。",
            "secondary_factors": secondary_labels,
            "evidence": evidence[:6],
            "missing_information": [] if len(evidence) >= 3 else ["如果能再具体说说孩子最近一次考试的情况，我可以判断得更准。"],
            "parent_common_mistake": primary_action["mistake"],
            "next_7_days_stop": primary_action["stop"],
            "next_7_days_start": try_this,
            "public_summary": public_summary,
            "hook": hook,
        }

    def _build_causal_chain(self, option_set: set[str]) -> str:
        """根据用户选项组合，生成因果推理链（口语版）。"""
        parent_ids = {
            "parent_add_more_exercises", "parent_explain_full_solution",
            "parent_ai_gives_answer", "parent_review_then_retest",
        }
        review_ids = {
            "probe_only_reads_answer", "probe_cannot_name_breakpoint",
            "probe_ai_answer_first", "probe_template_ok_variant_fail",
            "probe_emotion_blocks_start",
        }
        selected_parent = option_set.intersection(parent_ids)
        selected_review = option_set.intersection(review_ids)

        if selected_parent and selected_review:
            for pid in selected_parent:
                for rid in selected_review:
                    key = (pid, rid)
                    if key in self._CAUSAL_LINKS:
                        return self._CAUSAL_LINKS[key]
            return self._CAUSAL_LINKS.get(
                "_default_parent_strategy",
                "你现在帮孩子的方式，和孩子真正卡住的那个点，可能有一点错位。"
            )

        if selected_parent:
            return "你帮孩子的心意肯定没问题，但也许可以换一种帮法，效果会更好。"

        return "孩子在这个环节卡住其实挺常见的，关键是用对方法去练，而不是练更多。"
