from __future__ import annotations

from copy import deepcopy

import pytest

from learning_problem_factory.models import (
    EvidenceDirection,
    EvidenceMode,
    KnowledgeArtifact,
    LearningBlock,
    Observer,
    ObservableSignal,
    ProbeBlueprint,
    ProbeOptionDraft,
    ProductionRequest,
    ProductionScope,
    SourceCitation,
    SourceDocument,
    SourceKind,
    SourcePack,
    Subject,
    KnowledgeNode,
)


@pytest.fixture
def production_request() -> ProductionRequest:
    source = SourceDocument(
        id="source-math-demo-01",
        title="一元一次方程来源样例",
        kind=SourceKind.CURRICULUM_STANDARD,
        publisher_or_author="测试来源",
        edition_or_year="2026",
        locator="section-1",
        content="本测试来源用于验证流水线，不作为真实课程资料发布。它说明一元一次方程与等式性质的关联。",
        verified_by_human=True,
    )
    return ProductionRequest(
        id="request-math-demo-01",
        recipe_id="math_knowledge_graph_v1",
        evidence_mode=EvidenceMode.SOURCE_GROUNDED,
        source_pack=SourcePack(
            id="pack-math-demo-01",
            title="数学测试来源包",
            scope_note="仅用于自动化测试",
            documents=[source],
        ),
        scope=ProductionScope(
            subject=Subject.MATH,
            grade_min=7,
            grade_max=7,
            modules=["一元一次方程"],
        ),
        max_reruns=1,
    )


@pytest.fixture
def distillation_request() -> ProductionRequest:
    return ProductionRequest(
        id="request-math-distill-01",
        recipe_id="math_knowledge_graph_v1",
        evidence_mode=EvidenceMode.MODEL_DISTILLATION,
        source_pack=None,
        scope=ProductionScope(
            subject=Subject.MATH,
            grade_min=7,
            grade_max=7,
            modules=["一元一次方程"],
        ),
        max_reruns=1,
    )


def make_artifact(provider_name: str = "executor-a") -> KnowledgeArtifact:
    citation = SourceCitation(
        source_id="source-math-demo-01",
        locator="section-1",
        claim="等式性质是一元一次方程变形的依据",
    )
    node = KnowledgeNode(
        id="math.g7.linear-equation.equality-property",
        subject=Subject.MATH,
        grade_min=7,
        grade_max=7,
        module="一元一次方程",
        name="等式的基本性质",
        definition="等式两边同时加上或减去同一个数，所得结果仍然是等式。",
        core_thinking=["等价变形"],
        citations=[citation],
    )
    block = LearningBlock(
        id="block.math.g7.equality-transform-loss",
        node_id=node.id,
        title="只记移项口诀，不能解释等价变形",
        description="学生会套用移项口诀，但不能说明每一步为什么保持方程同解。",
        essence="等式性质没有成为变形依据，符号变化停留在口诀记忆层。",
        block_type="concept_understanding",
        observable_signals=[
            ObservableSignal(
                id="signal.math.g7.cannot-explain-sign-change",
                observer=Observer.LEARNER,
                behavior="能写出移项结果，却说不出符号改变的依据",
                context="口头解释一道一步方程的变形过程时",
                non_example="偶尔发生一次抄写错误不能单独支持该假设",
            )
        ],
        probe_blueprints=[
            ProbeBlueprint(
                audience=Observer.LEARNER,
                stem="如果不使用“移项变号”这句话，你能解释这一步为什么成立吗？",
                options=[
                    ProbeOptionDraft(
                        id="can-explain-with-equality-property",
                        label="能用等式两边做相同运算来解释",
                        direction=EvidenceDirection.CONTRADICTS,
                        evidence_tag="explains_equivalent_transformation",
                        strength=0.8,
                    ),
                    ProbeOptionDraft(
                        id="only-remembers-sign-change",
                        label="只记得移过去要变号",
                        direction=EvidenceDirection.SUPPORTS,
                        evidence_tag="rote_sign_change_rule",
                        strength=0.9,
                    ),
                ],
                evidence_needed=["学生口头解释", "独立变形过程"],
            )
        ],
        citations=[citation],
    )
    return KnowledgeArtifact(
        recipe_id="math_knowledge_graph_v1",
        request_id="request-math-demo-01",
        batch_id="batch-math-01",
        candidate_id=f"batch-math-01-{provider_name}-attempt-1",
        provider_name=provider_name,
        nodes=[node],
        learning_blocks=[block],
        source_ids=["source-math-demo-01"],
    )


def make_distilled_artifact(provider_name: str = "executor-a") -> KnowledgeArtifact:
    node = KnowledgeNode(
        id="math.g7.linear-equation.equality-property",
        subject=Subject.MATH,
        grade_min=7,
        grade_max=7,
        module="一元一次方程",
        name="等式的基本性质",
        definition="等式两边同时进行相同运算，是方程同解变形的核心依据。",
        core_thinking=["等价变形", "运算保持关系"],
        citations=[],
    )
    block = LearningBlock(
        id="block.math.g7.equality-transform-loss",
        node_id=node.id,
        title="只记移项口诀，不能解释等价变形",
        description="学生会套用移项口诀，但不能说明每一步为什么保持方程同解。",
        essence="等式性质没有成为变形依据，符号变化停留在口诀记忆层。",
        block_type="concept_understanding",
        observable_signals=[
            ObservableSignal(
                id="signal.math.g7.cannot-explain-sign-change",
                observer=Observer.LEARNER,
                behavior="能写出移项结果，却说不出符号改变的依据",
                context="口头解释一道一步方程的变形过程时",
                non_example="偶尔发生一次抄写错误不能单独支持该假设",
            )
        ],
        probe_blueprints=[
            ProbeBlueprint(
                audience=Observer.LEARNER,
                stem="如果不使用“移项变号”这句话，你能解释这一步为什么成立吗？",
                options=[
                    ProbeOptionDraft(
                        id="can-explain-with-equality-property",
                        label="能用等式两边做相同运算来解释",
                        direction=EvidenceDirection.CONTRADICTS,
                        evidence_tag="explains_equivalent_transformation",
                        strength=0.8,
                    ),
                    ProbeOptionDraft(
                        id="only-remembers-sign-change",
                        label="只记得移过去要变号",
                        direction=EvidenceDirection.SUPPORTS,
                        evidence_tag="rote_sign_change_rule",
                        strength=0.9,
                    ),
                ],
                evidence_needed=["学生口头解释", "独立变形过程"],
            )
        ],
        citations=[],
    )
    return KnowledgeArtifact(
        recipe_id="math_knowledge_graph_v1",
        request_id="request-math-distill-01",
        batch_id="batch-math-01",
        candidate_id=f"batch-math-01-{provider_name}-attempt-1",
        provider_name=provider_name,
        nodes=[node],
        learning_blocks=[block],
        source_ids=[],
    )


@pytest.fixture
def valid_artifact() -> KnowledgeArtifact:
    return deepcopy(make_artifact())


@pytest.fixture
def distilled_artifact() -> KnowledgeArtifact:
    return deepcopy(make_distilled_artifact())
