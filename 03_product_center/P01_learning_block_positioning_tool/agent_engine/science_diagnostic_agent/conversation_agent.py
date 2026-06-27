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
    accumulate_category_scores,
    top_category,
    infer_option_ids_from_text,
    infer_subject_from_text,
)
from .llm_providers import LLMAdapter, ProviderRegistry
from .models import (
    FactorCode, Subject,
    StuckCategory, Amplifier,
    CATEGORY_LABELS, AMPLIFIER_LABELS,
)
from .prompts import SYSTEM_PROMPT, FIRST_TURN_USER_MESSAGE
from .question_bank import category_probe as v2_category_probe
from .question_bank import amplifier_probe as v2_amplifier_probe
from .verification_actions import get_verification_action, get_uncertainties


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
    # V2 字段
    v2_stage: str = "opening"  # opening|paraphrase|narrow|probe|amplifier|verify|report
    identified_category: str = ""    # 主卡点 A|B|C|D|E
    identified_amplifier: str = ""    # 放大器 F|G|H
    free_text_evidence: list[str] = field(default_factory=list)  # 家长原话
    verification_done: bool = False


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

    # 年级不适用的选项 ID
    _GRADE_FILTER_OPTIONS: dict[str, set[str]] = {
        "lower": {  # 1-2年级
            "math_calc_decimal_point", "math_calc_multistep_break",
            "math_method_no_idea", "math_method_unsure", "math_method_right_but_why",
            "math_attn_multi_condition", "math_attn_composite",
            "phys_calc_multistep_lost", "phys_method_no_idea", "phys_method_confuse_law",
            "chem_calc_balance", "chem_calc_valence", "chem_calc_mole_mass",
            "chem_method_no_idea", "chem_method_cant_transfer",
        },
        "middle": {  # 3-4年级
            "chem_calc_balance", "chem_calc_mole_mass",
        },
        "junior": {  # 初中：过滤小学特征选项
            "math_calc_carry_borrow", "math_calc_miscopy",
        },
        "senior": {  # 高中
            "math_calc_carry_borrow", "math_calc_decimal_point",
            "math_calc_miscopy", "math_calc_multistep_break",
        },
    }

    def start_session(self) -> tuple[ConversationSession, AgentTurnResult]:
        """开始一个新的对话会话"""
        session = ConversationSession()

        if not self.adapter.is_ready():
            # LLM 不可用时的降级处理
            session.v2_stage = "opening"
            return session, AgentTurnResult(
                messages=[AgentMessage(
                    text="你先把孩子最近在数学或物理上最让你头疼的一件事告诉我。可以直接说：哪类题、什么时候容易错、考试还是作业、你已经试过什么。不用先判断是不是粗心，我会先帮你把问题缩小到更具体的一类。"
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

        # V2: 收集家长原话作为证据
        if text and text.strip():
            stripped = text.strip()
            if stripped not in session.free_text_evidence:
                session.free_text_evidence.append(stripped)

        # P0 修复：无论 LLM 是否可用，始终收集规则信号
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
        """V2：用规则评分校验 LLM 结论。LLM 主要驱动，规则兜底补充 evidence + uncertainties。"""
        llm_data = llm_result.result or {}

        # LLM 已输出 V2 格式 → 直接验证并补充
        if llm_data.get("primary_category"):
            # 补充规则 evidence
            rule_evidence = [
                OPTION_PUBLIC_LABELS.get(oid, oid)
                for oid in session.fallback_option_ids if oid in OPTION_PUBLIC_LABELS
            ]
            llm_evidence = llm_data.get("evidence") or []
            llm_data["evidence"] = list(dict.fromkeys(llm_evidence + rule_evidence))[:6]
            # 确保有 uncertainties
            if not llm_data.get("uncertainties"):
                llm_data["uncertainties"] = ["需要看真实试卷才能进一步确认具体是哪一种错误模式。"]
            # 确保有 diagnostic_upgrade
            if not llm_data.get("diagnostic_upgrade"):
                subject = session.fallback_subject.value if session.fallback_subject != Subject.UNKNOWN else "math"
                sn = "数学" if subject == "math" else "物理"
                llm_data["diagnostic_upgrade"] = (
                    "刚才的对话，我们只是通过描述看到了水面上的冰山一角。"
                    "看病不能光听家属描述，必须看最终的'化验单'——也就是孩子的真实演算卷面。"
                    "把孩子最近的1-2张" + sn + "大考卷发过来，我会像做X光扫描一样，逐行拆解他的解题步骤，"
                    "帮你出一份精准的漏洞定位与修复方案。找准了底层的那个漏洞，把逻辑重新顺一遍，比瞎做100道题都管用。"
                )
            return AgentTurnResult(
                messages=llm_result.messages, should_conclude=True,
                result=llm_data, thinking=llm_result.thinking,
                collected_signals=llm_result.collected_signals,
            )

        # LLM 输出的是旧格式 → 用 V2 报告覆盖
        v2_report = self._compose_v2_report(session)
        return AgentTurnResult(
            messages=llm_result.messages, should_conclude=True,
            result=v2_report, thinking=llm_result.thinking,
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
        # 先匹配初中/高中（"初中一年级""高中二年级"）——"初中"后跟"X年级"
        m = _re.search(r"初(?:中)?\s*(?:([一二三])(?:年|年级)|(\d)\s*(?:年|年级))", text)
        if m:
            digit = m.group(1) or m.group(2)
            if digit:
                return {"一": 7, "二": 8, "三": 9, "1": 7, "2": 8, "3": 9}.get(digit, 0)
        m = _re.search(r"高(?:中)?\s*(?:([一二三])(?:年|年级)|(\d)\s*(?:年|年级))", text)
        if m:
            digit = m.group(1) or m.group(2)
            if digit:
                return {"一": 10, "二": 11, "三": 12, "1": 10, "2": 11, "3": 12}.get(digit, 0)
        # 初一/初二/初三 → 7-9
        m = _re.search(r"初([一二三])", text)
        if m:
            return {"一": 7, "二": 8, "三": 9}.get(m.group(1), 0)
        # 高一/高二/高三 → 10-12
        m = _re.search(r"高([一二三])", text)
        if m:
            return {"一": 10, "二": 11, "三": 12}.get(m.group(1), 0)
        # 小学：一年级～六年级 → 1-6（放最后，避免误匹配"初中一年级"）
        m = _re.search(r"(?<!初)(?<!高)([一二三四五六])(?:年|年级)", text)
        if m:
            return {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}.get(m.group(1), 0)
        # 纯数字: 7年级=初一, 8年级=初二...
        m = _re.search(r"(\d+)\s*(?:年|年级)", text)
        if m:
            g = int(m.group(1))
            return g if 1 <= g <= 12 else 0
        return 0


    # ============================================================
    # V2 初筛智能体：5 步状态机
    # ============================================================

    def _fallback_response(self, session: ConversationSession) -> AgentTurnResult:
        """V2 初筛流程：subject -> paraphrase+narrow -> category_probe -> amplifier -> report"""
        option_ids = set(session.fallback_option_ids)
        stage = session.v2_stage

        # Stage 0: 确定学科
        if session.fallback_subject == Subject.UNKNOWN:
            if "fallback_subject_select" not in session.fallback_asked_block_ids:
                return self._fallback_question(
                    session,
                    text="我先确认一下，这件事主要是哪一科？",
                    ui_block={
                        "type": "single_choice", "id": "fallback_subject_select",
                        "title": "主要是哪一科？", "allow_free_text": True,
                        "free_text_label": "我自己说",
                        "options": [
                            {"id": "subject_math", "label": "数学"},
                            {"id": "subject_physics", "label": "物理"},
                        ],
                    },
                )

        # Stage 1: 复述家长的话 + 给出 2 个候选方向
        if stage in ("opening", "paraphrase"):
            # 如果家长只说"数学不好""总粗心"，先追问具体事件
            evidence_text = " ".join(session.free_text_evidence) if session.free_text_evidence else ""
            if len(evidence_text) < 10:
                return self._fallback_question(
                    session,
                    text="你印象最深的一次是什么？是哪一类题、哪一次考试，还是哪一种经常重复的错误？多说一点细节，我才能帮你缩小范围。",
                    ui_block={
                        "type": "short_text", "id": "v2_more_detail",
                        "title": "多说一点细节",
                        "allow_free_text": True,
                        "free_text_label": "我自己说",
                        "free_text_placeholder": "比如：最近一次单元测验，计算题总是进退位搞反，平时作业还好，一到考试就错。",
                        "options": [],
                    },
                )
            session.v2_stage = "narrow"
            paraphrase = self._paraphrase_parent(session)
            candidates = self._narrow_candidates(session)
            return AgentTurnResult(messages=[AgentMessage(
                text=candidates["text"],
                ui_block=candidates["ui_block"],
            )])

        # Stage 2: 按类别追问
        if stage == "narrow":
            session.v2_stage = "amplifier"
            cat_code = self._infer_category_from_options(session)
            session.identified_category = cat_code
            cat_map = {"A": StuckCategory.A_CONCEPT, "B": StuckCategory.B_RULE_BOUNDARY,
                        "C": StuckCategory.C_INFO_SYMBOL, "D": StuckCategory.D_EXECUTION,
                        "E": StuckCategory.E_MODELING}
            cat = cat_map.get(cat_code, StuckCategory.D_EXECUTION)
            probe = v2_category_probe(cat)
            return AgentTurnResult(messages=[AgentMessage(
                text=self._category_lead_in(cat_code),
                ui_block={
                    "type": probe.type.value, "id": "v2_category_probe",
                    "title": probe.title, "allow_free_text": True,
                    "free_text_label": "不确定，我自己说",
                    "options": [{"id": o.id, "label": o.label} for o in probe.options],
                },
            )])

        # Stage 3: 放大器追问
        if stage == "amplifier":
            session.v2_stage = "report"
            amp_code = self._infer_amplifier_from_options(session)
            session.identified_amplifier = amp_code
            amp_map = {"F": Amplifier.F_FIX_LOOP, "G": Amplifier.G_EXAM_PACE, "H": Amplifier.H_AVOIDANCE}
            amp = amp_map.get(amp_code, Amplifier.F_FIX_LOOP)
            probe = v2_amplifier_probe(amp)
            return AgentTurnResult(messages=[AgentMessage(
                text=self._amplifier_lead_in(amp_code),
                ui_block={
                    "type": probe.type.value, "id": "v2_amplifier_probe",
                    "title": probe.title, "allow_free_text": True,
                    "free_text_label": "不确定",
                    "options": [{"id": o.id, "label": o.label} for o in probe.options],
                },
            )])

        # Stage 4: 出初筛报告
        result = self._compose_v2_report(session)
        session.is_complete = True
        session.v2_stage = "report"
        session.pending_ui_block_id = None
        return AgentTurnResult(
            messages=[AgentMessage(text="好的，我帮你理了一下，下面是我的初筛判断～")],
            should_conclude=True,
            result=result,
        )

    # ---- V2 辅助方法 ----

    def _paraphrase_parent(self, session: ConversationSession) -> str:
        evidence = session.free_text_evidence
        if evidence:
            core = evidence[0][:80]
            return (
                "我先把你说的情况捋一下：你担心的不是单纯'不会做'，而是「" + core + "…」。"
                "这类情况表面上都像'粗心'或'没认真'，但后面可能是几种不同问题。我们先把它缩小一点。"
            )
        return "我先把你说的情况捋一下。这类情况表面上像粗心，但后面可能是几种不同问题。我们先把它缩小一点。"

    def _narrow_candidates(self, session: ConversationSession) -> dict:
        cat_scores, _ = accumulate_category_scores(
            session.fallback_subject, session.fallback_option_ids, decay_prior=True
        )
        sorted_cats = sorted(cat_scores.items(), key=lambda x: x[1], reverse=True)
        top2 = sorted_cats[:2] if len(sorted_cats) >= 2 else sorted_cats

        labels = {
            StuckCategory.A_CONCEPT: "基础概念不太稳",
            StuckCategory.B_RULE_BOUNDARY: "规则会背但用不对地方",
            StuckCategory.C_INFO_SYMBOL: "读题信息没进到解题里",
            StuckCategory.D_EXECUTION: "思路对但中间步骤总出错",
            StuckCategory.E_MODELING: "应用题或综合题不会建关系",
        }
        candidates = [labels.get(c[0], "其他") for c in top2]
        return {
            "text": (
                "目前我更想优先看两个方向：一个是「" + candidates[0] + "」，"
                "另一个是「" + candidates[1] + "」。"
                "先帮我分一下：这种错最常发生在哪一刻？"
            ),
            "ui_block": {
                "type": "single_choice", "id": "v2_narrow",
                "title": "最常发生在哪一刻？",
                "allow_free_text": True,
                "free_text_label": "不确定，我自己说",
                "options": [
                    {"id": "narrow_primary", "label": "更像「" + candidates[0] + "」"},
                    {"id": "narrow_secondary", "label": "更像「" + candidates[1] + "」"},
                    {"id": "narrow_unsure", "label": "不确定"},
                ],
            },
        }

    def _category_lead_in(self, cat_code: str) -> str:
        leads = {
            "A": "我想再确认一下：孩子遇到这类题的时候，是概念本身没搞懂，还是知道概念但不会用？",
            "B": "我想再确认一下：是规则本身记错了，还是不知道什么时候该用哪条规则？",
            "C": "这种错最常发生在读题那一刻，还是列式画图的时候？",
            "D": "这种计算错误是偶尔一次，还是同一种错在不同题里反复出现？",
            "E": "孩子是题目读不懂，还是读懂了但不会转化成数学式子？",
        }
        return leads.get(cat_code, "我先确认一下具体情况。")

    def _amplifier_lead_in(self, amp_code: str) -> str:
        leads = {
            "F": "最后一个问题：孩子做错以后，通常接下来会发生什么？",
            "G": "再确认一个点：平时作业和考试差别大吗？",
            "H": "孩子遇到难题时，第一反应通常是什么？",
        }
        return leads.get(amp_code, "最后一个问题。")

    def _infer_category_from_options(self, session: ConversationSession) -> str:
        """从选项推断最可能的主卡点类别"""
        cat_scores, _ = accumulate_category_scores(
            session.fallback_subject, session.fallback_option_ids
        )
        if cat_scores:
            top = max(cat_scores, key=lambda k: cat_scores[k])
            return top.value[0]  # A/B/C/D/E
        return "D"

    def _infer_amplifier_from_options(self, session: ConversationSession) -> str:
        """从选项推断最可能的放大器"""
        _, amp_scores = accumulate_category_scores(
            session.fallback_subject, session.fallback_option_ids
        )
        if amp_scores:
            top = max(amp_scores, key=lambda k: amp_scores[k])
            return top.value[0]  # F/G/H
        return "F"

    def _compose_v2_report(self, session: ConversationSession) -> dict[str, Any]:
        """V2 初筛报告：5 段固定结构"""
        cat_code = session.identified_category or "D"
        amp_code = session.identified_amplifier or ""
        subject = session.fallback_subject.value if session.fallback_subject != Subject.UNKNOWN else "math"

        cat_map = {"A": StuckCategory.A_CONCEPT, "B": StuckCategory.B_RULE_BOUNDARY,
                    "C": StuckCategory.C_INFO_SYMBOL, "D": StuckCategory.D_EXECUTION,
                    "E": StuckCategory.E_MODELING}
        amp_map = {"F": Amplifier.F_FIX_LOOP, "G": Amplifier.G_EXAM_PACE, "H": Amplifier.H_AVOIDANCE}
        category = cat_map.get(cat_code, StuckCategory.D_EXECUTION)
        amplifier = amp_map.get(amp_code)
        cat_label = CATEGORY_LABELS.get(category, "某个环节需要加强")
        amp_label = AMPLIFIER_LABELS.get(amplifier, "") if amplifier else ""

        # 证据：引用家长原话
        evidence = session.free_text_evidence[:3] if session.free_text_evidence else []
        opt_evidence = [
            OPTION_PUBLIC_LABELS.get(oid, oid)
            for oid in session.fallback_option_ids if oid in OPTION_PUBLIC_LABELS
        ]
        evidence = list(dict.fromkeys(evidence + opt_evidence))
        if not evidence:
            evidence = ["根据你描述的情况"]

        # 验证动作 + 不确定性
        vaction = get_verification_action(category, subject)
        uncertainties = get_uncertainties(category)

        # 报告
        amp_line = "，同时" + amp_label + "可能让它反复出现" if amp_label else ""
        subject_name = "数学" if subject == "math" else "物理"
        public_summary = (
            "这次的问题核心更像是「" + cat_label + "」" + amp_line + "。\n"
            "别再让孩子无效刷题或者罚抄错题了！这根本不是粗心，而是底层的" + subject_name + "逻辑架构没搭稳。"
            "就像盖楼一样，地基歪了，你在上面怎么修补墙皮都没用。\n\n"
            "我这样判断，是因为你刚才提到：\n"
            + "\n".join("· " + e for e in evidence[:3]) +
            "\n\n现在单靠描述还不能确定的是：\n"
            + "\n".join("· " + u for u in uncertainties[:3]) +
            "\n\n今晚可以试一个小动作——" + vaction["title"] + "：\n" + vaction["steps"] + "\n\n"
            "注意：在做这个验证时，你大概率会发现孩子根本说不出第一处跑偏在哪里，或者解释不清最基础的那个概念。"
            "不要生气，这非常正常。这说明他的" + subject_name + "基础架构已经有了断层，单靠盯着一道错题是找不到真正断点的。"
        )

        diagnostic_upgrade = (
            "刚才的对话，我们只是通过描述看到了水面上的冰山一角。"
            "看病不能光听家属描述，必须看最终的'化验单'——也就是孩子的真实演算卷面。"
            "把孩子最近的1-2张" + subject_name + "大考卷发过来，我会像做X光扫描一样，逐行拆解他的解题步骤，"
            "帮你出一份精准的漏洞定位与修复方案。找准了底层的那个漏洞，把逻辑重新顺一遍，比瞎做100道题都管用。"
        )

        return {
            "subject": subject,
            "primary_factor": cat_label,
            "primary_category": cat_label,
            "primary_desc": "这次更像是「" + cat_label + "」" + amp_line,
            "secondary_factors": [amp_label] if amp_label else [],
            "amplifier": amp_label,
            "evidence": evidence[:6],
            "uncertainties": uncertainties,
            "verification_action": vaction,
            "missing_information": uncertainties[:2],
            "next_7_days_start": vaction.get("title", ""),
            "parent_common_mistake": "把表面现象简单归为粗心或态度问题。",
            "next_7_days_stop": "先不要急着加题量或反复讲答案。",
            "public_summary": public_summary,
            "diagnostic_upgrade": diagnostic_upgrade,
        }


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
