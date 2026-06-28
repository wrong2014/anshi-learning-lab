"""Controlled conversational diagnostic flow for P01.

The rule engine owns evidence and flow. The optional LLM only extracts signals
from free text and polishes the final parent-facing summary.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .factor_rules import (
    OPTION_PUBLIC_LABELS,
    OPTION_WEIGHTS,
    accumulate_amplifier_scores,
    accumulate_category_scores,
    accumulate_scores,
    infer_option_ids_from_text,
    infer_subject_from_text,
    ranked_categories,
)
from .llm_providers import LLMAdapter
from .models import (
    CATEGORY_LABELS,
    FACTOR_TO_CATEGORY,
    DiagnosticCategory,
    FactorCode,
    Subject,
    UIBlock,
)
from .question_bank import (
    category_candidate_question,
    category_detail_question,
    context_amplifier_question,
)
from .result_catalog import CATEGORY_DESCRIPTIONS, SUBJECT_LABELS, build_result_payload


@dataclass
class AgentMessage:
    text: str
    ui_block: dict[str, Any] | None = None


@dataclass
class AgentTurnResult:
    messages: list[AgentMessage]
    should_conclude: bool = False
    result: dict[str, Any] | None = None
    thinking: str = ""
    collected_signals: dict[str, Any] | None = None


@dataclass
class ConversationSession:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    history: list[dict[str, str]] = field(default_factory=list)
    turn_count: int = 0
    is_complete: bool = False
    pending_ui_block_id: str | None = None
    pending_ui_block_type: str | None = None
    fallback_subject: Subject = Subject.UNKNOWN
    fallback_option_ids: list[str] = field(default_factory=list)
    fallback_asked_block_ids: set[str] = field(default_factory=set)
    grade_level: int = 0
    diagnostic_stage: str = "story"
    free_text_evidence: list[str] = field(default_factory=list)
    llm_evidence: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    candidate_categories: list[str] = field(default_factory=list)
    identified_category: str = ""


class ConversationAgent:
    """Evidence-driven dialogue with optional semantic extraction."""

    MAX_TURNS = 6

    _DEFAULT_CATEGORY_ORDER = {
        Subject.MATH: [
            DiagnosticCategory.C_MODELING,
            DiagnosticCategory.B_REPRESENTATION,
            DiagnosticCategory.D_EXECUTION,
            DiagnosticCategory.A_FOUNDATION,
            DiagnosticCategory.E_SELF_REGULATION,
        ],
        Subject.PHYSICS: [
            DiagnosticCategory.B_REPRESENTATION,
            DiagnosticCategory.A_FOUNDATION,
            DiagnosticCategory.C_MODELING,
            DiagnosticCategory.D_EXECUTION,
            DiagnosticCategory.E_SELF_REGULATION,
        ],
        Subject.CHEMISTRY: [
            DiagnosticCategory.B_REPRESENTATION,
            DiagnosticCategory.A_FOUNDATION,
            DiagnosticCategory.C_MODELING,
            DiagnosticCategory.D_EXECUTION,
            DiagnosticCategory.E_SELF_REGULATION,
        ],
        Subject.UNKNOWN: list(DiagnosticCategory),
    }

    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def start_session(self) -> tuple[ConversationSession, AgentTurnResult]:
        session = ConversationSession()
        return session, AgentTurnResult(
            messages=[AgentMessage(
                text=(
                    "你好。能走到这里，你多半已经为孩子试过不少办法，也可能越帮越着急。"
                    "先不用证明谁对谁错，我们只看最近一次，我陪你把乱成一团的感觉慢慢理清。"
                ),
                ui_block={
                    "type": "opening_prompt",
                    "id": "opening_story_prompt",
                    "title": "从最近一次让你心里一沉的时刻说起",
                    "body": "不用讲完整，也不用先判断原因。想到哪里，就从哪里开始。",
                    "starters": [
                        {
                            "id": "opening_paper",
                            "label": "一张卷子",
                            "text": "最近一张让我担心的卷子是……",
                        },
                        {
                            "id": "opening_repeated_error",
                            "label": "一道总错的题",
                            "text": "有一类题孩子明明学过，却总是……",
                        },
                        {
                            "id": "opening_help_conflict",
                            "label": "一次辅导冲突",
                            "text": "最近一次我试着帮他，结果反而……",
                        },
                    ],
                },
            )]
        )

    def process_user_input(
        self,
        session: ConversationSession,
        text: str | None = None,
        selected_option_ids: list[str] | None = None,
        selected_labels: list[str] | None = None,
        ui_block_id: str | None = None,
    ) -> AgentTurnResult:
        selected_option_ids = selected_option_ids or []
        selected_labels = selected_labels or []
        session.turn_count += 1

        self._append_history(session, text, selected_labels, selected_option_ids, ui_block_id)
        self._record_signals(
            session,
            text=text,
            selected_option_ids=selected_option_ids,
            ui_block_id=ui_block_id,
        )

        if session.turn_count >= self.MAX_TURNS and session.diagnostic_stage != "story":
            return self._conclude(session)

        if session.diagnostic_stage == "story":
            return self._handle_story(session)
        if session.diagnostic_stage == "candidate":
            return self._handle_candidate_answer(session)
        if session.diagnostic_stage == "detail":
            return self._handle_detail_answer(session)
        if session.diagnostic_stage == "context":
            return self._conclude(session)

        return self._conclude(session)

    def _append_history(
        self,
        session: ConversationSession,
        text: str | None,
        selected_labels: list[str],
        selected_option_ids: list[str],
        ui_block_id: str | None,
    ) -> None:
        parts: list[str] = []
        if ui_block_id:
            parts.append(f"（回答追问：{ui_block_id}）")
        if text and text.strip():
            parts.append(text.strip())
        if selected_labels:
            parts.append(f"（选择：{'、'.join(selected_labels)}）")
        elif selected_option_ids:
            parts.append(f"（选择ID：{'、'.join(selected_option_ids)}）")
        session.history.append({"role": "user", "content": " ".join(parts) or "（跳过）"})

    def _record_signals(
        self,
        session: ConversationSession,
        text: str | None,
        selected_option_ids: list[str],
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
        clean_ids = [option_id for option_id in selected_option_ids if option_id]
        if "context_none_obvious" in clean_ids and len(clean_ids) > 1:
            clean_ids = [option_id for option_id in clean_ids if option_id != "context_none_obvious"]

        for option_id in clean_ids:
            if option_id in subject_map:
                session.fallback_subject = subject_map[option_id]
            elif not option_id.startswith("_"):
                session.fallback_option_ids.append(option_id)

        if text and text.strip():
            stripped = text.strip()
            if stripped not in session.free_text_evidence:
                session.free_text_evidence.append(stripped)

            inferred_subject = infer_subject_from_text(stripped)
            if session.fallback_subject == Subject.UNKNOWN and inferred_subject != Subject.UNKNOWN:
                session.fallback_subject = inferred_subject
            if session.grade_level == 0:
                session.grade_level = self._extract_grade(stripped)

            session.fallback_option_ids.extend(infer_option_ids_from_text(stripped))
            self._record_llm_signals(session, stripped)

        session.fallback_option_ids = list(dict.fromkeys(session.fallback_option_ids))

    def _record_llm_signals(self, session: ConversationSession, text: str) -> None:
        if not self.adapter.is_ready():
            return
        extracted = self.adapter.extract_signals(session.fallback_subject.value, text)
        session.fallback_option_ids.extend(extracted.option_ids)
        for note in extracted.evidence_notes:
            if note and note not in session.llm_evidence:
                session.llm_evidence.append(note)
        for note in extracted.uncertainty_notes:
            if note and note not in session.uncertainty_notes:
                session.uncertainty_notes.append(note)

    def _handle_story(self, session: ConversationSession) -> AgentTurnResult:
        if session.fallback_subject == Subject.UNKNOWN:
            return self._question(
                session,
                text="我先确认一下，你刚才说的这件事主要发生在哪一科？",
                ui_block={
                    "type": "single_choice",
                    "id": "diagnostic_subject",
                    "title": "主要是哪一科？",
                    "options": [
                        {"id": "subject_math", "label": "数学"},
                        {"id": "subject_physics", "label": "物理"},
                        {"id": "subject_chemistry", "label": "化学"},
                    ],
                    "allow_free_text": True,
                    "free_text_label": "我直接说",
                    "free_text_placeholder": "比如：主要是初二物理电路题。",
                },
            )

        if not self._has_core_evidence(session) and "diagnostic_more_detail" not in session.fallback_asked_block_ids:
            return self._question(
                session,
                text=(
                    "我知道你很着急，但“成绩差”或“总粗心”还不能帮我找到断点。"
                    "你想一下最近印象最深的一次：哪类题、孩子从哪一步开始不对？"
                ),
                ui_block={
                    "type": "short_text",
                    "id": "diagnostic_more_detail",
                    "title": "说一次最近发生的具体情况",
                    "options": [],
                    "allow_free_text": True,
                    "free_text_label": "我来描述",
                    "free_text_placeholder": "比如：初二数学应用题，题意能复述，但每次都列不出关系式。",
                },
            )

        categories = self._candidate_categories(session)
        session.candidate_categories = [category.value for category in categories]
        session.diagnostic_stage = "candidate"
        block = self._ui_block(category_candidate_question(session.fallback_subject, categories))
        return self._question(
            session,
            text=self._paraphrase_and_narrow(session, categories),
            ui_block=block,
        )

    def _handle_candidate_answer(self, session: ConversationSession) -> AgentTurnResult:
        category = self._top_category(session)
        session.identified_category = category.value
        session.diagnostic_stage = "detail"
        return self._question(
            session,
            text=(
                f"明白了。现在更值得优先核对的是「{CATEGORY_LABELS[category]}」。"
                "我再用一个问题把里面最容易混淆的几种情况分开。"
            ),
            ui_block=self._ui_block(category_detail_question(category)),
        )

    def _handle_detail_answer(self, session: ConversationSession) -> AgentTurnResult:
        category = self._top_category(session)
        session.identified_category = category.value
        session.diagnostic_stage = "context"
        return self._question(
            session,
            text=(
                "这条线索已经比较清楚了。最后只看一下有没有外部情况在放大它；"
                "这些不会被算成孩子学不好的根因。"
            ),
            ui_block=self._ui_block(context_amplifier_question()),
        )

    def _conclude(self, session: ConversationSession) -> AgentTurnResult:
        result = self._compose_result(session)
        session.is_complete = True
        session.diagnostic_stage = "complete"
        session.pending_ui_block_id = None
        session.pending_ui_block_type = None
        return AgentTurnResult(
            messages=[AgentMessage(text="好，我把刚才的线索收拢一下。下面是初步定位，不是给孩子贴标签。")],
            should_conclude=True,
            result=result,
            collected_signals={
                "subject": session.fallback_subject.value,
                "evidence_count": len(session.fallback_option_ids),
            },
        )

    def _compose_result(self, session: ConversationSession) -> dict[str, Any]:
        category = self._top_category(session)
        factor_scores = accumulate_scores(session.fallback_subject, session.fallback_option_ids)
        ranked_factors = sorted(factor_scores.items(), key=lambda item: item[1], reverse=True)
        category_factors = [
            (factor, score)
            for factor, score in ranked_factors
            if FACTOR_TO_CATEGORY.get(factor) == category
        ]
        primary_factor = category_factors[0][0] if category_factors else FactorCode.F07_METACOGNITION
        amplifier_scores = accumulate_amplifier_scores(session.fallback_option_ids)
        amplifier = max(amplifier_scores, key=amplifier_scores.get) if amplifier_scores else None
        if amplifier and amplifier_scores[amplifier] < 2:
            amplifier = None

        evidence = self._public_evidence(session)
        confidence = self._confidence(session, category)
        uncertainties = self._uncertainties(session, confidence)
        grade_label = self._grade_label(session.grade_level)
        result = build_result_payload(
            subject=session.fallback_subject,
            grade_label=grade_label,
            category=category,
            primary_factor=primary_factor,
            amplifier=amplifier,
            evidence=evidence,
            uncertainties=uncertainties,
            confidence=confidence,
        )

        polished = self.adapter.polish_result({
            "subject": SUBJECT_LABELS[session.fallback_subject],
            "grade": grade_label,
            "category": CATEGORY_LABELS[category],
            "description": CATEGORY_DESCRIPTIONS[category],
            "amplifier": result["amplifier_label"],
            "evidence": evidence[:3],
            "uncertainties": uncertainties[:2],
        })
        unsafe_claim = bool(polished and re.search(r"说明.{0,12}没问题|根本不是|问题就是|一定是", polished))
        if polished and 40 <= len(polished) <= 360 and not unsafe_claim:
            result["public_summary"] = polished
        return result

    def _public_evidence(self, session: ConversationSession) -> list[str]:
        evidence: list[str] = []
        for text in session.free_text_evidence[:2]:
            compact = re.sub(r"\s+", " ", text).strip()
            if compact:
                evidence.append(f"家长提到：{compact[:100]}")
        for note in session.llm_evidence[:2]:
            evidence.append(note[:100])
        for option_id in session.fallback_option_ids:
            label = OPTION_PUBLIC_LABELS.get(option_id)
            if label and not option_id.startswith("category_hint_"):
                evidence.append(label)
        return list(dict.fromkeys(evidence))[:6] or ["当前证据仍较少，需要用具体错题继续确认。"]

    def _uncertainties(self, session: ConversationSession, confidence: str) -> list[str]:
        notes = list(session.uncertainty_notes)
        notes.append("还没有核对孩子的真实卷面和演算过程。")
        if not session.grade_level:
            notes.append("年级信息还不明确，不同年级的知识要求会影响判断。")
        if confidence == "low":
            notes.append("当前可观察线索偏少，主卡点仍可能随具体错题调整。")
        notes.append("还需要区分这是长期稳定模式，还是最近一次考试中的偶发现象。")
        return list(dict.fromkeys(note for note in notes if note))[:4]

    def _confidence(self, session: ConversationSession, category: DiagnosticCategory) -> str:
        category_scores = accumulate_category_scores(session.fallback_subject, session.fallback_option_ids)
        ordered = sorted(category_scores.values(), reverse=True)
        gap = ordered[0] - ordered[1] if len(ordered) > 1 else (ordered[0] if ordered else 0)
        core_count = sum(
            1
            for option_id in set(session.fallback_option_ids)
            if any(factor in FACTOR_TO_CATEGORY for factor in OPTION_WEIGHTS.get(option_id, {}))
        )
        detail_answered = "diagnostic_category_detail" in session.fallback_asked_block_ids
        if core_count >= 4 and gap >= 2 and detail_answered:
            return "high"
        if core_count >= 2 and gap >= 0.8:
            return "medium"
        return "low"

    def _has_core_evidence(self, session: ConversationSession) -> bool:
        return any(
            any(factor in FACTOR_TO_CATEGORY for factor in OPTION_WEIGHTS.get(option_id, {}))
            for option_id in session.fallback_option_ids
        )

    def _candidate_categories(self, session: ConversationSession) -> list[DiagnosticCategory]:
        ordered = ranked_categories(session.fallback_subject, session.fallback_option_ids)
        for category in self._DEFAULT_CATEGORY_ORDER[session.fallback_subject]:
            if category not in ordered:
                ordered.append(category)
        return ordered[:3]

    def _top_category(self, session: ConversationSession) -> DiagnosticCategory:
        ordered = ranked_categories(session.fallback_subject, session.fallback_option_ids)
        if ordered:
            return ordered[0]
        if session.identified_category:
            return DiagnosticCategory(session.identified_category)
        return self._DEFAULT_CATEGORY_ORDER[session.fallback_subject][0]

    def _paraphrase_and_narrow(
        self,
        session: ConversationSession,
        categories: list[DiagnosticCategory],
    ) -> str:
        original = session.free_text_evidence[0] if session.free_text_evidence else "孩子最近理科学习不太稳定"
        original = re.sub(r"\s+", " ", original).strip()[:90].rstrip("。！？!?，,；;")
        labels = "、".join(f"「{CATEGORY_LABELS[item]}」" for item in categories[:2])
        return (
            f"我先确认一下我听懂了：你最担心的是“{original}”。"
            f"这不一定只是粗心，目前更值得先区分的是{labels}。"
            "下面哪一种最接近孩子真正开始卡住的那一刻？"
        )

    def _question(
        self,
        session: ConversationSession,
        text: str,
        ui_block: dict[str, Any],
    ) -> AgentTurnResult:
        block = deepcopy(ui_block)
        block.setdefault("allow_free_text", True)
        block.setdefault("free_text_label", "都不像，我自己说")
        block.setdefault("free_text_placeholder", "用你自己的话补充，我会重新分析。")
        if block.get("type") == "multi_choice":
            block.setdefault("allow_skip", True)
            block.setdefault("min_select", 1)
            block.setdefault("max_select", 3)
        session.pending_ui_block_id = str(block.get("id") or "")
        session.pending_ui_block_type = str(block.get("type") or "")
        if session.pending_ui_block_id:
            session.fallback_asked_block_ids.add(session.pending_ui_block_id)
        return AgentTurnResult(messages=[AgentMessage(text=text, ui_block=block)])

    @staticmethod
    def _ui_block(block: UIBlock) -> dict[str, Any]:
        return block.model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _extract_grade(text: str) -> int:
        junior = re.search(r"初(?:中)?\s*([一二三123])", text)
        if junior:
            return {"一": 7, "二": 8, "三": 9, "1": 7, "2": 8, "3": 9}[junior.group(1)]
        senior = re.search(r"高(?:中)?\s*([一二三123])", text)
        if senior:
            return {"一": 10, "二": 11, "三": 12, "1": 10, "2": 11, "3": 12}[senior.group(1)]
        chinese = re.search(r"([一二三四五六七八九])\s*年级", text)
        if chinese:
            return {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}[chinese.group(1)]
        numeric = re.search(r"(1[0-2]|[1-9])\s*年级", text)
        if numeric:
            return int(numeric.group(1))
        return 0

    @staticmethod
    def _grade_label(grade: int) -> str:
        if 1 <= grade <= 6:
            return f"小学{grade}年级"
        if 7 <= grade <= 9:
            return f"初{'一二三'[grade - 7]}"
        if 10 <= grade <= 12:
            return f"高{'一二三'[grade - 10]}"
        return ""
