from __future__ import annotations

import pytest

from learning_problem_factory.models import (
    Decision,
    EvidenceMode,
    Observer,
    ProductionRequest,
    ProductionScope,
    SourceCitation,
    SourceDocument,
    SourceKind,
    SourcePack,
    Subject,
    SupervisionReport,
)
from learning_problem_factory.providers import ScriptedProvider
from learning_problem_factory.recipes import get_recipe
from learning_problem_factory.repository import FactoryRepository
from learning_problem_factory.specialized_models import (
    CoreThinkingArtifact,
    CoreThinkingDimension,
    MathThinkingProfile,
    PsychologyArtifact,
    PsychologyDimension,
    SeverityBoundary,
    SpecializedProductionOutcome,
    SpecializedProductionRun,
    StageFeature,
    SubjectLearningScenario,
    ThinkingObservableSignal,
)
from learning_problem_factory.specialized_pipeline import (
    SpecializedMaterialFactory,
    _normalize_supervision_score,
    _sanitize_subjective_labels,
    publish_specialized_outcome,
)
from learning_problem_factory.specialized_validators import validate_specialized_artifact


def source_pack() -> SourcePack:
    return SourcePack(
        id="source-pack-specialized",
        title="核心思维与心理认知来源",
        scope_note="测试来源",
        documents=[
            SourceDocument(
                id="source-theory-001",
                title="测试理论资料",
                kind=SourceKind.ACADEMIC_PAPER,
                publisher_or_author="测试作者",
                edition_or_year="2025",
                locator="page 1",
                content="这是一份经过人工核验的测试理论资料，用于支持核心思维和心理认知定义。",
                verified_by_human=True,
            )
        ],
    )


def request(recipe_id: str, subject: Subject) -> ProductionRequest:
    return ProductionRequest(
        id=f"request-{recipe_id}",
        recipe_id=recipe_id,
        evidence_mode=EvidenceMode.SOURCE_GROUNDED,
        source_pack=source_pack(),
        scope=ProductionScope(
            subject=subject,
            grade_min=1,
            grade_max=9,
            modules=["测试模块"],
        ),
    )


def core_artifact(provider: str = "executor-a") -> CoreThinkingArtifact:
    citation = SourceCitation(
        source_id="source-theory-001",
        locator="page 1",
        claim="definition of mathematical abstraction",
    )
    signals = [
        ThinkingObservableSignal(
            observer=observer,
            behavior="Cannot identify the same mathematical relation in a changed representation",
            context="When a familiar quantitative relation is presented in a new situation",
            likely_breakpoint="Has not extracted a stable mathematical structure from examples",
        )
        for observer in (Observer.TEACHER, Observer.PARENT, Observer.LEARNER)
    ]
    return CoreThinkingArtifact(
        recipe_id="math_core_thinking_v1",
        request_id="request-math_core_thinking_v1",
        batch_id="batch-thinking-01",
        candidate_id=f"candidate-{provider}",
        provider_name=provider,
        dimensions=[
            CoreThinkingDimension(
                id="thinking.math.abstraction",
                subject=Subject.MATH,
                name="测试模块",
                academic_definition=(
                    "A thinking process that extracts quantitative relations and spatial forms"
                ),
                plain_essence="Retain the mathematical structure while varying surface details",
                observable_deficits=signals,
                stage_features=[
                    StageFeature(
                        grade_min=1,
                        grade_max=9,
                        expectation="Progress from concrete quantities to symbols and general relations",
                        typical_transition="Move from objects to equations, letters and functional forms",
                    )
                ],
                development_path=[
                    "Compare multiple concrete examples",
                    "Mark their shared quantitative relation",
                ],
                profile=MathThinkingProfile(
                    mathematical_manifestations=["Represent changing relations with letters"],
                    related_knowledge_areas=["number and algebra"],
                ),
                citations=[citation],
            )
        ],
        source_ids=["source-theory-001"],
    )


def test_core_thinking_validator_rejects_dangling_name_relations():
    artifact = core_artifact()
    dimension = artifact.dimensions[0].model_copy(
        update={"supports": ["数学抽象思维"]}
    )
    artifact = artifact.model_copy(update={"dimensions": [dimension]})

    issues = validate_specialized_artifact(
        artifact,
        request("math_core_thinking_v1", Subject.MATH),
        get_recipe("math_core_thinking_v1"),
    )

    assert {issue.code for issue in issues} >= {
        "thinking.invalid_relation_id",
        "thinking.unknown_relation",
    }


def test_core_thinking_validator_requires_all_observers_and_nonoverlapping_stages():
    artifact = core_artifact()
    original = artifact.dimensions[0]
    overlapping = original.stage_features[0].model_copy(
        update={"grade_min": 5, "grade_max": 9}
    )
    dimension = original.model_copy(
        update={
            "observable_deficits": [original.observable_deficits[0]],
            "stage_features": original.stage_features + [overlapping],
        }
    )
    artifact = artifact.model_copy(update={"dimensions": [dimension]})

    issues = validate_specialized_artifact(
        artifact,
        request("math_core_thinking_v1", Subject.MATH),
        get_recipe("math_core_thinking_v1"),
    )

    assert {issue.code for issue in issues} >= {
        "thinking.observer_coverage",
        "thinking.stage_overlap",
    }


def test_specialized_pipeline_rewrites_subjective_labels_before_validation():
    artifact = core_artifact()
    dimension = artifact.dimensions[0].model_copy(
        update={"plain_essence": "不是笨拙，而是操作步骤尚不熟悉"}
    )
    artifact = artifact.model_copy(update={"dimensions": [dimension]})

    repaired, issues = _sanitize_subjective_labels(artifact)

    assert repaired.dimensions[0].plain_essence == (
        "不是操作不熟练，而是操作步骤尚不熟悉"
    )
    assert [issue.code for issue in issues] == [
        "material.subjective_label_rewritten"
    ]


def passing_report(selected_id: str, recipe_id: str) -> dict:
    dimensions = [item.name for item in get_recipe(recipe_id).rubric]
    return {
        "selected_candidate_id": selected_id,
        "scores": [
            {"dimension": name, "score": 95, "rationale": "通过"}
            for name in dimensions
        ],
        "issues": [],
        "final_score": 95,
        "decision": Decision.PASS.value,
        "rerun_instructions": [],
    }


def test_specialized_pipeline_recomputes_weighted_supervision_score():
    report = SupervisionReport.model_validate(
        passing_report("candidate-a", "math_core_thinking_v1")
    ).model_copy(update={"final_score": 93})

    normalized = _normalize_supervision_score(
        report,
        get_recipe("math_core_thinking_v1"),
    )

    assert normalized.final_score == 95
    assert normalized.issues[-1].code == "supervisor.score_recomputed"


def test_core_thinking_factory_runs_supervises_and_publishes(tmp_path):
    production_request = request("math_core_thinking_v1", Subject.MATH)
    plan = {
        "request_id": production_request.id,
        "rationale": "按来源生产数学抽象思维资料",
        "batches": [
            {
                "id": "batch-thinking-01",
                "title": "测试模块",
                "module_names": ["测试模块"],
                "expected_node_count": 1,
                "depends_on": [],
                "source_ids": ["source-theory-001"],
            }
        ],
    }
    repository = FactoryRepository(tmp_path / "factory.db")
    factory = SpecializedMaterialFactory(
        planner=ScriptedProvider("planner", [plan]),
        executors=[
            ScriptedProvider("executor-a", [core_artifact("executor-a").model_dump(mode="json")]),
            ScriptedProvider("executor-b", [core_artifact("executor-b").model_dump(mode="json")]),
        ],
        supervisor=ScriptedProvider(
            "supervisor",
            [
                passing_report(
                    "batch-thinking-01-executor-a-attempt-1",
                    "math_core_thinking_v1",
                )
            ],
        ),
        recipe=get_recipe("math_core_thinking_v1"),
        repository=repository,
    )

    outcome = factory.run(production_request)
    assert outcome.run.status == "completed"
    release = publish_specialized_outcome(
        outcome,
        recipe=get_recipe("math_core_thinking_v1"),
        version="math-thinking-v1",
        repository=repository,
    )
    assert repository.load_specialized_release("math-thinking-v1") == release


def psychology_artifact() -> PsychologyArtifact:
    citation = SourceCitation(
        source_id="source-theory-001",
        locator="page 1",
        claim="自我效能感理论定义",
    )
    return PsychologyArtifact(
        recipe_id="learning_psychology_cognition_v1",
        request_id="request-learning_psychology_cognition_v1",
        batch_id="batch-psychology-01",
        candidate_id="psychology-candidate",
        provider_name="executor-a",
        dimensions=[
            PsychologyDimension(
                id="psychology.self-efficacy",
                layer="motivation",
                name="学习自我效能感",
                theory_name="自我效能理论",
                academic_definition="学习者对自己能否组织并完成特定学习任务的能力判断",
                theory_citations=[citation],
                subject_scenarios=[
                    SubjectLearningScenario(subject="math", manifestation="面对新题时预期自己能够找到关系"),
                    SubjectLearningScenario(subject="physics", manifestation="面对实验任务时愿意提出并验证假设"),
                    SubjectLearningScenario(subject="chemistry", manifestation="面对陌生反应时愿意尝试证据推理"),
                ],
                parent_signals=["开始任务前反复说肯定不会", "遇到第一处困难立刻退出", "只选择明显简单的任务"],
                learner_signals=["认为练习不会改善表现", "把一次失败解释成永远不会", "不愿描述自己卡住的位置"],
                achievement_mechanism="能力判断影响任务选择、努力持续时间以及遇到困难后的恢复行为",
                severity=SeverityBoundary(
                    normal_range="在困难任务前短暂担心，但仍愿意尝试并接受提示",
                    support_needed="持续回避多数学习任务，并明显影响日常练习和课堂参与",
                    professional_help="长期广泛回避并伴随显著情绪痛苦或生活功能受损",
                ),
                ai_support_scope=["帮助拆小任务", "记录可验证的小进步"],
                referral_conditions=["出现自伤表达", "情绪痛苦持续并影响睡眠与日常生活"],
                citations=[citation],
            )
        ],
        source_ids=["source-theory-001"],
    )


def test_psychology_validator_enforces_taxonomy_sources_and_boundaries():
    production_request = request(
        "learning_psychology_cognition_v1",
        Subject.CROSS_SUBJECT,
    )
    issues = validate_specialized_artifact(
        psychology_artifact(),
        production_request,
        get_recipe("learning_psychology_cognition_v1"),
    )

    assert {issue.code for issue in issues} >= {
        "psychology.unknown_dimension",
        "psychology.missing_theory_source",
        "psychology.missing_safety_source",
        "psychology.ai_scope_too_thin",
        "psychology.referral_too_thin",
    }


def test_psychology_release_requires_human_approval(tmp_path):
    production_request = request("learning_psychology_cognition_v1", Subject.CROSS_SUBJECT)
    outcome = SpecializedProductionOutcome(
        run=SpecializedProductionRun(
            id="specialized-run-psychology",
            request=production_request,
            status="completed",
            accepted_candidate_ids=["psychology-candidate"],
        ),
        artifacts=[psychology_artifact()],
    )
    repository = FactoryRepository(tmp_path / "factory.db")
    recipe = get_recipe("learning_psychology_cognition_v1")
    with pytest.raises(ValueError, match="human approver"):
        publish_specialized_outcome(
            outcome,
            recipe=recipe,
            version="psychology-v1",
            repository=repository,
        )
    bundle = publish_specialized_outcome(
        outcome,
        recipe=recipe,
        version="psychology-v1",
        repository=repository,
        approved_by="human-reviewer",
    )
    assert bundle.manifest.approved_by == "human-reviewer"
