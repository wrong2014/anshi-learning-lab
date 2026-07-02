from __future__ import annotations

import pytest
from pydantic import ValidationError

from learning_problem_factory.models import (
    Decision,
    KnowledgeRelation,
    RelationType,
    RubricScore,
    SourceCitation,
    SupervisionReport,
)
from learning_problem_factory.recipes import get_recipe
from learning_problem_factory.validators import (
    has_errors,
    validate_artifact,
    validate_supervision_report,
)


def test_supervision_thresholds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        SupervisionReport(
            selected_candidate_id="candidate-1",
            scores=[RubricScore(dimension="accuracy", score=80, rationale="尚有缺口")],
            final_score=80,
            decision=Decision.PASS,
        )


def test_valid_artifact_passes_hard_validation(production_request, valid_artifact) -> None:
    issues = validate_artifact(valid_artifact, production_request)
    assert not has_errors(issues)


def test_model_distillation_artifact_does_not_need_sources(distillation_request, distilled_artifact) -> None:
    issues = validate_artifact(distilled_artifact, distillation_request)
    assert not has_errors(issues)
    assert any(issue.code == "artifact.model_distilled" for issue in issues)


def test_model_distillation_rejects_fabricated_citation(distillation_request, distilled_artifact) -> None:
    distilled_artifact.nodes[0].citations = [
        SourceCitation(source_id="fake-textbook", locator="page 1", claim="伪造引用")
    ]
    issues = validate_artifact(distilled_artifact, distillation_request)
    assert any(issue.code == "artifact.citation_in_distillation_mode" for issue in issues)


def test_prerequisite_cycle_is_rejected(production_request, valid_artifact) -> None:
    node = valid_artifact.nodes[0].model_copy(update={"id": "math.g7.linear-equation.second-node"})
    valid_artifact.nodes.append(node)
    valid_artifact.learning_blocks.append(
        valid_artifact.learning_blocks[0].model_copy(
            update={
                "id": "block.math.g7.second-block",
                "node_id": node.id,
                "observable_signals": [
                    valid_artifact.learning_blocks[0].observable_signals[0].model_copy(
                        update={"id": "signal.math.g7.second-signal"}
                    )
                ],
            }
        )
    )
    citation = valid_artifact.nodes[0].citations
    valid_artifact.relations = [
        KnowledgeRelation(
            source_node_id=valid_artifact.nodes[0].id,
            target_node_id=node.id,
            relation_type=RelationType.PREREQUISITE,
            rationale="测试前置关系一",
            citations=citation,
        ),
        KnowledgeRelation(
            source_node_id=node.id,
            target_node_id=valid_artifact.nodes[0].id,
            relation_type=RelationType.PREREQUISITE,
            rationale="测试前置关系二",
            citations=citation,
        ),
    ]
    issues = validate_artifact(valid_artifact, production_request)
    assert any(issue.code == "artifact.prerequisite_cycle" for issue in issues)


def test_supervisor_weighted_score_is_recalculated() -> None:
    report = SupervisionReport(
        selected_candidate_id="candidate-1",
        scores=[
            RubricScore(dimension="completeness", score=100, rationale="完整"),
            RubricScore(dimension="accuracy", score=100, rationale="准确"),
            RubricScore(dimension="depth", score=100, rationale="深入"),
            RubricScore(dimension="observability", score=100, rationale="可观察"),
            RubricScore(dimension="consistency", score=100, rationale="一致"),
        ],
        final_score=99,
        decision=Decision.PASS,
    )
    issues = validate_supervision_report(
        report,
        get_recipe("math_knowledge_graph_v1"),
        {"candidate-1"},
        {"candidate-1"},
    )
    assert any(issue.code == "supervisor.score_mismatch" for issue in issues)
