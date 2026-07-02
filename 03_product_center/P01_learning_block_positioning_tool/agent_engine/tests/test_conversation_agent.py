import pytest
from unittest.mock import MagicMock

from science_diagnostic_agent.conversation_agent import ConversationAgent, ConversationSession, AgentTurnResult
from science_diagnostic_agent.models import DiagnosticCategory, Subject, FactorCode


class MockLLMAdapter:
    def is_ready(self):
        return True

    def text_client(self):
        client = MagicMock()
        # default response
        client.chat_text.return_value = '{"response_text": "mocked response", "ui_block": null, "should_conclude": false}'
        return client


@pytest.fixture
def agent():
    adapter = MockLLMAdapter()
    return ConversationAgent(adapter)


def test_advance_stage(agent):
    session = ConversationSession()
    assert session.stage == "opening"

    # Turn 0 -> 1
    session.turn_count = 0
    agent._advance_stage(session)
    assert session.stage == "story"

    # Turn 1 -> 2
    session.turn_count = 2
    agent._advance_stage(session)
    assert session.stage == "narrow"

    # Turn 3 -> 4
    session.turn_count = 4
    agent._advance_stage(session)
    assert session.stage == "probe"

    # Turn 4 -> 5
    session.turn_count = 5
    agent._advance_stage(session)
    assert session.stage == "conclude"


def test_record_rule_signals(agent):
    session = ConversationSession()
    agent._record_rule_signals(
        session=session,
        text="初二上学期，物理公式背下来了但是不会用",
        selected_option_ids=["F02_concept_understanding_unstable"],
        selected_labels=[]
    )

    # grade extracted
    assert session.grade == 8
    assert session.grade_label == "初二"
    # subject inferred
    assert session.rule_subject == Subject.PHYSICS
    # options added
    assert "F02_concept_understanding_unstable" in session.rule_option_ids


def test_ground_with_rules_no_conflict(agent):
    session = ConversationSession()
    session.rule_subject = Subject.PHYSICS
    # Option that maps strongly to F06_EXECUTION (D_EXECUTION)
    session.rule_option_ids = ["stuck_execution"]

    # LLM also outputs D_EXECUTION
    result = AgentTurnResult(
        messages=[],
        should_conclude=True,
        result={
            "primary_category": "D",
            "confidence": "high",
            "uncertainties": []
        }
    )

    grounded = agent._ground_with_rules(session, result)
    assert grounded.result["confidence"] == "high"
    # No uncertainty added because they match (both are D)
    assert len(grounded.result["uncertainties"]) == 0


def test_ground_with_rules_with_conflict(agent):
    session = ConversationSession()
    session.rule_subject = Subject.PHYSICS
    # Option maps to Execution (D)
    session.rule_option_ids = ["stuck_execution"]

    # LLM incorrectly outputs Foundation (A)
    result = AgentTurnResult(
        messages=[],
        should_conclude=True,
        result={
            "primary_category": "A",
            "confidence": "high",
            "uncertainties": []
        }
    )

    grounded = agent._ground_with_rules(session, result)
    # Confidence should be downgraded to medium due to conflict
    assert grounded.result["confidence"] == "medium"
    assert len(grounded.result["uncertainties"]) == 1
    assert "规则评分更倾向" in grounded.result["uncertainties"][0]


def test_graceful_fallback(agent):
    session = ConversationSession()
    session.stage = "opening"

    # Simulate LLM completely offline
    adapter = MockLLMAdapter()
    adapter.is_ready = lambda: False
    agent.adapter = adapter

    result = agent.process_user_input(session, text="hello")
    assert len(result.messages) == 1
    assert "大模型网络开小差了" in result.messages[0].text
    assert result.messages[0].ui_block["id"] == "fallback_subject"

    # Test fallback in later stage
    session.stage = "narrow"
    result = agent.process_user_input(session, text="hello")
    assert "刚才网络好像断了一下" in result.messages[0].text
    assert result.messages[0].ui_block["id"] == "fallback_category"
