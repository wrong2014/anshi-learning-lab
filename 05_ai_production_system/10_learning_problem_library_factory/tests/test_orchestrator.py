from __future__ import annotations

import pytest

from learning_problem_factory.models import Decision, ProductionOutcome
from learning_problem_factory.orchestrator import ProductionFactory, publish_outcome
from learning_problem_factory.providers import ScriptedProvider
from learning_problem_factory.recipes import get_recipe
from learning_problem_factory.repository import FactoryRepository

from conftest import make_artifact, make_distilled_artifact


def test_multi_model_run_and_publish(tmp_path, production_request) -> None:
    plan = {
        "request_id": production_request.id,
        "rationale": "先完成单模块竖切",
        "batches": [
            {
                "id": "batch-math-01",
                "title": "一元一次方程基础",
                "module_names": ["一元一次方程"],
                "expected_node_count": 1,
                "depends_on": [],
                "source_ids": ["source-math-demo-01"],
            }
        ],
    }
    artifact_a = make_artifact("executor-a").model_dump(mode="json")
    artifact_b = make_artifact("executor-b").model_dump(mode="json")
    selected_id = "batch-math-01-executor-a-attempt-1"
    report = {
        "selected_candidate_id": selected_id,
        "scores": [
            {"dimension": "completeness", "score": 95, "rationale": "结构完整"},
            {"dimension": "accuracy", "score": 94, "rationale": "引用支持"},
            {"dimension": "depth", "score": 92, "rationale": "解释到位"},
            {"dimension": "observability", "score": 93, "rationale": "信号可观察"},
            {"dimension": "consistency", "score": 96, "rationale": "术语一致"},
        ],
        "issues": [],
        "final_score": 94,
        "decision": Decision.PASS.value,
        "rerun_instructions": [],
    }
    repository = FactoryRepository(tmp_path / "factory.db")
    factory = ProductionFactory(
        planner=ScriptedProvider("planner", [plan]),
        executors=[
            ScriptedProvider("executor-a", [artifact_a]),
            ScriptedProvider("executor-b", [artifact_b]),
        ],
        supervisor=ScriptedProvider("supervisor", [report]),
        recipe=get_recipe("math_knowledge_graph_v1"),
        repository=repository,
    )

    outcome = factory.run(production_request)
    assert isinstance(outcome, ProductionOutcome)
    assert outcome.run.status == "completed"
    assert outcome.run.accepted_candidate_ids == [selected_id]
    assert len(outcome.artifacts) == 1

    bundle = publish_outcome(
        outcome,
        recipe=get_recipe("math_knowledge_graph_v1"),
        version="0.1.0-test",
        repository=repository,
    )
    loaded = repository.load_release("0.1.0-test")
    assert loaded is not None
    assert loaded.manifest.artifact_digest == bundle.manifest.artifact_digest
    assert len(loaded.probes) == 1


def test_unverified_source_cannot_be_published(tmp_path, production_request) -> None:
    production_request.source_pack.documents[0].verified_by_human = False
    outcome = ProductionOutcome(
        run={
            "request": production_request,
            "status": "completed",
            "accepted_candidate_ids": ["batch-math-01-executor-a-attempt-1"],
        },
        artifacts=[make_artifact("executor-a")],
    )
    repository = FactoryRepository(tmp_path / "factory.db")
    import pytest

    with pytest.raises(ValueError, match="human-verified"):
        publish_outcome(
            outcome,
            recipe=get_recipe("math_knowledge_graph_v1"),
            version="0.1.0-unverified",
            repository=repository,
        )


def test_model_distillation_cannot_define_knowledge_graph_scope(tmp_path, distillation_request) -> None:
    plan = {
        "request_id": distillation_request.id,
        "rationale": "先榨取一元一次方程的核心知识与学习卡点",
        "batches": [
            {
                "id": "batch-math-01",
                "title": "一元一次方程基础蒸馏",
                "module_names": ["一元一次方程"],
                "expected_node_count": 1,
                "depends_on": [],
                "source_ids": [],
            }
        ],
    }
    artifact_a = make_distilled_artifact("executor-a").model_dump(mode="json")
    artifact_b = make_distilled_artifact("executor-b").model_dump(mode="json")
    selected_id = "batch-math-01-executor-a-attempt-1"
    report = {
        "selected_candidate_id": selected_id,
        "scores": [
            {"dimension": "completeness", "score": 95, "rationale": "覆盖到知识点和卡点"},
            {"dimension": "accuracy", "score": 92, "rationale": "学科表述内部一致"},
            {"dimension": "depth", "score": 94, "rationale": "解释到学习本质"},
            {"dimension": "observability", "score": 93, "rationale": "信号可观察"},
            {"dimension": "consistency", "score": 96, "rationale": "术语一致"},
        ],
        "issues": [],
        "final_score": 94,
        "decision": Decision.PASS.value,
        "rerun_instructions": [],
    }
    repository = FactoryRepository(tmp_path / "factory.db")
    factory = ProductionFactory(
        planner=ScriptedProvider("planner", [plan]),
        executors=[
            ScriptedProvider("executor-a", [artifact_a]),
            ScriptedProvider("executor-b", [artifact_b]),
        ],
        supervisor=ScriptedProvider("supervisor", [report]),
        recipe=get_recipe("math_knowledge_graph_v1"),
        repository=repository,
    )

    with pytest.raises(ValueError, match="official curriculum pipeline"):
        factory.run(distillation_request)
