from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from science_diagnostic_agent import Actor, AnswerEvent, DiagnosticEngine


def main() -> None:
    engine = DiagnosticEngine()
    session, first_question = engine.start_session()
    print("FIRST_QUESTION")
    print(first_question.model_dump_json(indent=2, ensure_ascii=False))

    answers = [
        AnswerEvent(
            question_id="opening_story",
            free_text="孩子说物理课堂能听懂，但一到综合题就不知道先画图还是先套公式。我通常会直接讲完整解法。",
        ),
        AnswerEvent(question_id="stuck_step", selected_option_ids=["stuck_select_method"]),
        AnswerEvent(question_id="physics_probe", selected_option_ids=["physics_no_diagram"]),
        AnswerEvent(
            question_id="parent_support",
            selected_option_ids=["parent_explain_full_solution", "parent_ai_gives_answer"],
        ),
        AnswerEvent(
            question_id="child_checkpoint",
            actor=Actor.CHILD,
            selected_option_ids=["child_cannot_choose_formula"],
        ),
    ]

    for answer in answers:
        session = engine.record_answer(session, answer)

    scoring = engine.score_session(session)
    result = engine.compose_result(session)
    print("\nSCORING")
    print(json.dumps(scoring.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print("\nRESULT")
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
