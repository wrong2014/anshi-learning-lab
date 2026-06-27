from __future__ import annotations

from .factor_rules import (
    FACTOR_ACTIONS,
    FACTOR_PUBLIC_LABELS,
    OPTION_PUBLIC_LABELS,
    OPTION_WEIGHTS,
    accumulate_scores,
    infer_option_ids_from_text,
    infer_subject_from_text,
)
from .models import (
    Actor,
    AnswerEvent,
    Confidence,
    DiagnosisResult,
    DiagnosticSession,
    FactorCode,
    FactorScore,
    FactorScoringResult,
    RecommendedPath,
    Subject,
    UIBlock,
)
from .question_bank import (
    adaptive_probe_question,
    child_checkpoint_question,
    opening_story_question,
    parent_support_question,
    stuck_step_question,
    subject_question,
    subject_specific_question,
)


class DiagnosticEngine:
    def start_session(self) -> tuple[DiagnosticSession, UIBlock]:
        session = DiagnosticSession()
        return session, opening_story_question()

    def record_answer(self, session: DiagnosticSession, answer: AnswerEvent) -> DiagnosticSession:
        session.answers.append(answer)
        session.completed_question_ids.append(answer.question_id)

        if answer.question_id == "subject_select":
            selected = answer.selected_option_ids[0] if answer.selected_option_ids else ""
            session.subject = {
                "subject_math": Subject.MATH,
                "subject_physics": Subject.PHYSICS,
                "subject_chemistry": Subject.CHEMISTRY,
            }.get(selected, Subject.UNKNOWN)
        elif answer.question_id == "opening_story" and answer.free_text:
            inferred_subject = infer_subject_from_text(answer.free_text)
            if session.subject == Subject.UNKNOWN and inferred_subject != Subject.UNKNOWN:
                session.subject = inferred_subject
            inferred_options = infer_option_ids_from_text(answer.free_text)
            answer.selected_option_ids = list(dict.fromkeys(answer.selected_option_ids + inferred_options))

        return session

    def next_question(self, session: DiagnosticSession) -> UIBlock | None:
        completed = set(session.completed_question_ids)
        if "opening_story" not in completed:
            return opening_story_question()
        if "subject_select" not in completed and session.subject == Subject.UNKNOWN:
            return subject_question()
        if "stuck_step" not in completed:
            return stuck_step_question()

        subject_probe_id = {
            Subject.MATH: "math_probe",
            Subject.PHYSICS: "physics_probe",
            Subject.CHEMISTRY: "chemistry_probe",
        }.get(session.subject)
        if subject_probe_id and subject_probe_id not in completed:
            return subject_specific_question(session.subject.value)

        if "parent_support" not in completed:
            return parent_support_question()
        if "child_checkpoint" not in completed:
            return child_checkpoint_question()
        if "adaptive_probe" not in completed:
            scoring = self.score_session(session)
            return adaptive_probe_question(scoring.top_factors)
        return None

    def score_session(self, session: DiagnosticSession) -> FactorScoringResult:
        option_ids: list[str] = []
        evidence_by_factor: dict[FactorCode, list[str]] = {}

        for answer in session.answers:
            option_ids.extend(answer.selected_option_ids)
            if answer.free_text:
                # P1 修复：用规则正则从自由文本提取信号，不再全部归到 F07
                inferred_ids = infer_option_ids_from_text(answer.free_text)
                option_ids.extend(inferred_ids)
                # 将自由文本关联到推断出的因子作为证据
                for inferred_id in set(inferred_ids):
                    for factor_code in OPTION_WEIGHTS.get(inferred_id, {}):
                        if answer.free_text not in evidence_by_factor.get(factor_code, []):
                            evidence_by_factor.setdefault(factor_code, []).append(answer.free_text)
                # 如果正则没匹配到任何信号，保留文本但不绑定因子
                if not inferred_ids:
                    evidence_by_factor.setdefault(FactorCode.F07_METACOGNITION, []).append(
                        f"[待分类] {answer.free_text}"
                    )

        raw_scores = accumulate_scores(session.subject, option_ids)
        if not raw_scores:
            raw_scores = {FactorCode.F07_METACOGNITION: 1.0}

        max_score = max(max(raw_scores.values()), 1.0)
        factor_scores = [
            FactorScore(
                factor=factor,
                raw_score=score,
                normalized_score=round(score / max_score, 3),
                evidence=evidence_by_factor.get(factor, []),
            )
            for factor, score in sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)
        ]
        top = [item.factor for item in factor_scores[:3]]
        confidence = self._confidence(factor_scores)
        risk_flags = self._risk_flags(raw_scores)
        return FactorScoringResult(
            subject=session.subject,
            scores=factor_scores,
            top_factors=top,
            confidence=confidence,
            risk_flags=risk_flags,
        )

    def compose_result(self, session: DiagnosticSession) -> DiagnosisResult:
        scoring = self.score_session(session)
        primary = scoring.top_factors[0]
        secondary = scoring.top_factors[1:3]
        action = FACTOR_ACTIONS[primary]
        evidence = self._public_evidence(session, scoring)
        recommended_path = self._recommended_path(primary, secondary, scoring.risk_flags)
        label = FACTOR_PUBLIC_LABELS[primary]

        return DiagnosisResult(
            session_id=session.session_id,
            subject=session.subject,
            primary_factor=primary,
            secondary_factors=secondary,
            confidence=scoring.confidence,
            evidence=evidence,
            missing_information=self._missing_information(session),
            parent_common_mistake=action["mistake"],
            next_7_days_stop=action["stop"],
            next_7_days_start=action["start"],
            recommended_path=recommended_path,
            human_review_needed=recommended_path == RecommendedPath.HUMAN_REVIEW,
            public_summary=f"目前更像是「{label}」在优先影响学习稳定性。这个判断需要结合最近一次具体学习事件继续校准。",
        )

    def _confidence(self, scores: list[FactorScore]) -> Confidence:
        if len(scores) < 2:
            return Confidence.LOW
        gap = scores[0].raw_score - scores[1].raw_score
        if scores[0].raw_score >= 5 and gap >= 2:
            return Confidence.HIGH
        if scores[0].raw_score >= 3:
            return Confidence.MEDIUM
        return Confidence.LOW

    def _risk_flags(self, raw_scores: dict[FactorCode, float]) -> list[str]:
        flags: list[str] = []
        if raw_scores.get(FactorCode.F09_EMOTION, 0) >= 3:
            flags.append("emotion_or_motivation_signal")
        if raw_scores.get(FactorCode.F10_SUPPORT_AI, 0) >= 4:
            flags.append("family_support_or_ai_misalignment")
        return flags

    def _recommended_path(
        self,
        primary: FactorCode,
        secondary: list[FactorCode],
        risk_flags: list[str],
    ) -> RecommendedPath:
        if "emotion_or_motivation_signal" in risk_flags and FactorCode.F10_SUPPORT_AI in secondary:
            return RecommendedPath.HUMAN_REVIEW
        if primary == FactorCode.F10_SUPPORT_AI:
            return RecommendedPath.P02
        if primary in {FactorCode.F04_REPRESENTATION, FactorCode.F05_MODEL_TRANSFER, FactorCode.F07_METACOGNITION}:
            return RecommendedPath.P03 if len(secondary) >= 2 else RecommendedPath.P02
        return RecommendedPath.P02

    def _public_evidence(self, session: DiagnosticSession, scoring: FactorScoringResult) -> list[str]:
        evidence: list[str] = []
        for answer in session.answers:
            if answer.free_text:
                evidence.append(f"家长描述：{answer.free_text}")
            if answer.selected_option_ids:
                labels = [OPTION_PUBLIC_LABELS.get(item, item) for item in answer.selected_option_ids]
                evidence.append(f"选择信号：{', '.join(labels)}")
        if not evidence:
            evidence.append("当前证据不足，需要继续补充最近一次具体学习事件。")
        return evidence[:6]

    def _missing_information(self, session: DiagnosticSession) -> list[str]:
        missing: list[str] = []
        completed = set(session.completed_question_ids)
        if "opening_story" not in completed:
            missing.append("还缺最近一次具体学习事件。")
        if "child_checkpoint" not in completed:
            missing.append("还缺孩子自己对卡住步骤的补充。")
        return missing
