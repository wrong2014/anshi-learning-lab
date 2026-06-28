from __future__ import annotations

import unittest

from science_diagnostic_agent.conversation_agent import ConversationAgent
from science_diagnostic_agent.factor_rules import (
    ALL_OPTION_IDS,
    AMPLIFIER_WEIGHTS,
    OPTION_PUBLIC_LABELS,
    OPTION_WEIGHTS,
    ranked_categories,
)
from science_diagnostic_agent.llm_providers import ALLOWED_OPTION_IDS
from science_diagnostic_agent.models import DiagnosticCategory, ExtractedSignals, Subject
from science_diagnostic_agent.question_bank import (
    category_candidate_question,
    category_detail_question,
    context_amplifier_question,
)
from science_diagnostic_agent.result_catalog import build_result_preview, list_result_catalog


class OfflineAdapter:
    def is_ready(self) -> bool:
        return False

    def polish_result(self, result_json):
        return None


class SemanticAdapter(OfflineAdapter):
    def is_ready(self) -> bool:
        return True

    def extract_signals(self, subject: str, free_text: str) -> ExtractedSignals:
        return ExtractedSignals(
            option_ids=["chem_symbol_equation_mismatch"],
            evidence_notes=["家长描述中同时出现了现象、粒子和方程式无法对应。"],
        )

    def polish_result(self, result_json):
        return "目前更像是题意理解与表征转换遇到了断点；先用今晚的小验证核对，再决定是否增加练习。"


def complete_flow(
    agent: ConversationAgent,
    story: str,
    category_option: str,
    detail_option: str,
    context_options: list[str],
):
    session, _ = agent.start_session()
    candidate = agent.process_user_input(session, text=story)
    assert candidate.messages[0].ui_block["id"] == "diagnostic_category_candidates"

    detail = agent.process_user_input(
        session,
        selected_option_ids=[category_option],
        ui_block_id="diagnostic_category_candidates",
    )
    assert detail.messages[0].ui_block["id"] == "diagnostic_category_detail"

    context = agent.process_user_input(
        session,
        selected_option_ids=[detail_option],
        ui_block_id="diagnostic_category_detail",
    )
    assert context.messages[0].ui_block["id"] == "diagnostic_context_check"

    result = agent.process_user_input(
        session,
        selected_option_ids=context_options,
        ui_block_id="diagnostic_context_check",
    )
    assert result.should_conclude
    return session, result.result


class ConversationAgentTests(unittest.TestCase):
    def test_opening_uses_non_submitting_prompt_starters(self):
        _, result = ConversationAgent(OfflineAdapter()).start_session()

        block = result.messages[0].ui_block
        self.assertEqual(block["type"], "opening_prompt")
        self.assertEqual(len(block["starters"]), 3)
        self.assertTrue(all(item["text"] for item in block["starters"]))

    def test_math_modeling_flow_keeps_exam_context_as_amplifier(self):
        _, result = complete_flow(
            ConversationAgent(OfflineAdapter()),
            "孩子初二数学应用题能复述题意，但不会列关系式，例题会做，换个场景就完全不会。",
            "category_hint_modeling",
            "probe_modeling_variant",
            ["context_exam_drop"],
        )

        self.assertEqual(result["subject_label"], "数学")
        self.assertEqual(result["grade_label"], "初二")
        self.assertEqual(result["primary_category"], DiagnosticCategory.C_MODELING.value)
        self.assertEqual(result["amplifier"], "G_exam_context_and_pace")
        self.assertIn("遮住数字", result["verification_action"]["title"])
        self.assertEqual(result["branch_id"], "math.c_modeling.v1")

    def test_candidate_and_detail_answers_can_change_the_initial_direction(self):
        agent = ConversationAgent(OfflineAdapter())
        session, _ = agent.start_session()
        agent.process_user_input(
            session,
            text="孩子初二数学一遇到条件多的题就乱，经常漏条件，做到中间也记不住前面写了什么。",
        )
        initial = ranked_categories(session.fallback_subject, session.fallback_option_ids)[0]
        self.assertEqual(initial, DiagnosticCategory.D_EXECUTION)

        agent.process_user_input(
            session,
            selected_option_ids=["category_hint_representation"],
            ui_block_id="diagnostic_category_candidates",
        )
        agent.process_user_input(
            session,
            selected_option_ids=["probe_representation_convert"],
            ui_block_id="diagnostic_category_detail",
        )
        final = agent.process_user_input(
            session,
            selected_option_ids=["context_none_obvious"],
            ui_block_id="diagnostic_context_check",
        )

        self.assertEqual(final.result["primary_category"], DiagnosticCategory.B_REPRESENTATION.value)
        self.assertIsNone(final.result["amplifier"])

    def test_physics_concept_flow_uses_physics_verification(self):
        _, result = complete_flow(
            ConversationAgent(OfflineAdapter()),
            "孩子初二物理公式会背，但每个物理量是什么意思说不清，有时做错了还特别确定。",
            "category_hint_foundation",
            "probe_foundation_confident_wrong",
            ["context_none_obvious"],
        )

        self.assertEqual(result["subject_label"], "物理")
        self.assertEqual(result["primary_category"], DiagnosticCategory.A_FOUNDATION.value)
        self.assertIn("公式", result["verification_action"]["title"])
        self.assertNotIn("数学", result["diagnostic_upgrade"])

    def test_chemistry_is_not_collapsed_into_physics(self):
        _, result = complete_flow(
            ConversationAgent(OfflineAdapter()),
            "孩子初三化学总是把实验现象、微观粒子变化和方程式弄混，三者怎么都对不上。",
            "category_hint_representation",
            "probe_representation_convert",
            ["context_fatigue"],
        )

        self.assertEqual(result["subject"], Subject.CHEMISTRY.value)
        self.assertEqual(result["subject_label"], "化学")
        self.assertIn("现象", result["verification_action"]["title"])
        self.assertIn("化学试卷", result["diagnostic_upgrade"])

    def test_llm_only_adds_evidence_and_polishes_summary(self):
        _, result = complete_flow(
            ConversationAgent(SemanticAdapter()),
            "孩子初三化学最近做实验题总是不对，我说不清具体卡在哪里。",
            "category_hint_representation",
            "probe_representation_misread",
            ["context_none_obvious"],
        )

        self.assertEqual(result["primary_category"], DiagnosticCategory.B_REPRESENTATION.value)
        self.assertTrue(result["public_summary"].startswith("目前更像是"))
        self.assertTrue(any("现象、粒子" in item for item in result["evidence"]))

    def test_every_generated_option_is_registered(self):
        option_ids: set[str] = set()
        for category in DiagnosticCategory:
            option_ids.update(option.id for option in category_detail_question(category).options)
        option_ids.update(
            option.id
            for option in category_candidate_question(Subject.MATH, list(DiagnosticCategory)).options
        )
        option_ids.update(option.id for option in context_amplifier_question().options)

        ignored = {"category_hint_unsure", "category_detail_unsure", "context_none_obvious"}
        diagnostic_ids = option_ids - ignored
        self.assertTrue(diagnostic_ids.issubset(set(OPTION_WEIGHTS) | set(AMPLIFIER_WEIGHTS)))
        self.assertTrue(diagnostic_ids.issubset(OPTION_PUBLIC_LABELS))
        self.assertEqual(ALLOWED_OPTION_IDS, ALL_OPTION_IDS)

    def test_grade_extraction_covers_middle_and_high_school(self):
        self.assertEqual(ConversationAgent._extract_grade("孩子初二数学"), 8)
        self.assertEqual(ConversationAgent._extract_grade("高中二年级物理"), 11)
        self.assertEqual(ConversationAgent._extract_grade("九年级化学"), 9)

    def test_result_catalog_has_15_previewable_branches(self):
        catalog = list_result_catalog()
        self.assertEqual(len(catalog["branches"]), 15)
        for subject in ("math", "physics", "chemistry"):
            preview = build_result_preview(
                subject_value=subject,
                category_value=DiagnosticCategory.C_MODELING.value,
            )
            self.assertEqual(preview["subject"], subject)
            self.assertTrue(preview["branch_id"].startswith(f"{subject}."))


if __name__ == "__main__":
    unittest.main()

