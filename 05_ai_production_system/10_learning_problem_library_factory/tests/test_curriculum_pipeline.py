from __future__ import annotations

import pytest

from learning_problem_factory.curriculum_models import (
    CurriculumCitation,
    CurriculumEvidencePack,
    CurriculumEvidencePage,
    CurriculumOutline,
    CurriculumPipelineRequest,
    CurriculumRelation,
    CurriculumRelationBatch,
    CurriculumRelationType,
    CurriculumSource,
    CurriculumSourceCatalog,
    ChemistryKnowledgeProfile,
    KnowledgePoint,
    MathKnowledgeProfile,
    OutlineLevel,
    OutlineNode,
    PhysicsKnowledgeProfile,
    PhysicsFormula,
    ScienceKnowledgeProfile,
)
from learning_problem_factory.curriculum_pipeline import CurriculumPipeline
from learning_problem_factory.curriculum_preview import render_curriculum_preview
from learning_problem_factory.curriculum_release import publish_curriculum_network
from learning_problem_factory.curriculum_validators import (
    build_coverage,
    validate_outline,
    validate_points,
    validate_relations,
)
from learning_problem_factory.models import Subject, stable_digest
from learning_problem_factory.official_seed import build_official_seed
from learning_problem_factory.providers import ScriptedProvider
from learning_problem_factory.repository import FactoryRepository


def catalog(*subjects: Subject) -> CurriculumSourceCatalog:
    source_ids = {
        Subject.MATH: "moe-math-2022",
        Subject.SCIENCE: "moe-science-2022",
        Subject.PHYSICS: "moe-physics-2022",
        Subject.CHEMISTRY: "moe-chemistry-2022",
    }
    return CurriculumSourceCatalog(
        notice_url="https://www.moe.gov.cn/notice",
        sources=[
            CurriculumSource(
                id=source_ids[subject],
                title=f"{subject.value} standard",
                subject=subject,
                authority="中华人民共和国教育部",
                edition="2022",
                official_url=f"https://www.moe.gov.cn/{subject.value}.pdf",
                sha256="a" * 64,
                page_count=200,
                text_layer="ocr_required",
                locally_verified=True,
            )
            for subject in subjects
        ],
    )


def request(*subjects: Subject) -> CurriculumPipelineRequest:
    return CurriculumPipelineRequest(
        id="curriculum-test",
        title="test curriculum",
        subjects=list(subjects),
        grade_min=1,
        grade_max=9,
    )


def test_official_seed_has_all_subjects_stages_and_science_core_concepts():
    req = request(Subject.MATH, Subject.SCIENCE, Subject.PHYSICS, Subject.CHEMISTRY)
    source_catalog = catalog(*req.subjects)
    outline = build_official_seed(req, source_catalog)

    assert validate_outline(outline, req, source_catalog) == []
    science_themes = [
        node
        for node in outline.nodes
        if node.subject == Subject.SCIENCE and node.level == OutlineLevel.THEME
    ]
    assert len(science_themes) == 13
    stage_tasks = [node for node in outline.nodes if node.level == OutlineLevel.STAGE_TASK]
    assert len(stage_tasks) == 65
    assert {(node.grade_min, node.grade_max) for node in stage_tasks if node.subject == Subject.MATH} == {
        (1, 2),
        (3, 4),
        (5, 6),
        (7, 9),
    }


def test_curriculum_preview_renders_auditable_summary():
    req = request(Subject.MATH)
    source_catalog = catalog(Subject.MATH)
    outline = build_official_seed(req, source_catalog)
    evidence = CurriculumEvidencePack(
        ocr_engine="test-ocr",
        pages=[
            CurriculumEvidencePage(
                source_id="moe-math-2022",
                pdf_page=24,
                logical_page=17,
                text="数学课程内容包括数与代数、图形与几何、统计与概率和综合与实践。",
                image_sha256="c" * 64,
            )
        ],
    )
    html = render_curriculum_preview(outline, source_catalog, evidence)
    assert "中国义务教育数理化" in html
    assert "官方哈希已核验" in html
    assert "16" in html
    assert "PREVIEW ONLY" in html


def test_point_validator_detects_uncovered_task():
    req = request(Subject.MATH)
    source_catalog = catalog(Subject.MATH)
    outline = build_official_seed(req, source_catalog)
    issues = validate_points(outline, [])
    assert any(issue.code == "points.incomplete_task" for issue in issues)


def test_subject_profiles_enforce_physics_and_chemistry_semantics():
    with pytest.raises(ValueError, match="concept_formula_links"):
        PhysicsKnowledgeProfile(
            concept_definition="速度描述物体位置变化的快慢",
            formulae=[
                PhysicsFormula(
                    expression="v=s/t",
                    quantity_meanings="v速度、s路程、t时间",
                    conditions="平均速度定义适用",
                )
            ],
            physical_contexts=["物体沿直线运动"],
        )

    with pytest.raises(ValueError, match="representation_links"):
        ChemistryKnowledgeProfile(
            knowledge_type="mixed",
            macro_micro_symbolic=True,
            representation_links=[],
        )


def test_relation_validator_requires_primary_science_bridge():
    citation = CurriculumCitation(source_id="source", locator="page 1", excerpt="课程内容")
    profiles = {
        Subject.SCIENCE: ScienceKnowledgeProfile(inquiry_practices=["观察与解释"]),
        Subject.PHYSICS: PhysicsKnowledgeProfile(
            concept_definition="用于描述物理世界中的基本概念",
            physical_contexts=["日常运动情境"],
        ),
        Subject.CHEMISTRY: ChemistryKnowledgeProfile(
            knowledge_type="reasoning",
            macro_micro_symbolic=False,
        ),
    }
    points = [
        KnowledgePoint(
            id=f"{subject.value}.point",
            outline_node_id=f"{subject.value}.task",
            subject=subject,
            grade_min=5 if subject == Subject.SCIENCE else 8,
            grade_max=6 if subject == Subject.SCIENCE else 9,
            name=subject.value,
            definition="这是一个用于测试关系校验的学科知识点",
            learning_expectation="能够解释一个核心科学概念",
            concept_kind="concept",
            core_thinking=["模型思维"],
            subject_profile=profiles[subject],
            citations=[citation],
        )
        for subject in (Subject.SCIENCE, Subject.PHYSICS, Subject.CHEMISTRY)
    ]
    issues = validate_relations(points, [])
    assert any(issue.code == "graph.missing_science_bridge" for issue in issues)

    relations = [
        CurriculumRelation(
            source_point_id="science.point",
            target_point_id="physics.point",
            relation_type=CurriculumRelationType.BRIDGES_TO,
            rationale="小学科学概念承接初中物理概念学习",
        ),
        CurriculumRelation(
            source_point_id="science.point",
            target_point_id="chemistry.point",
            relation_type=CurriculumRelationType.BRIDGES_TO,
            rationale="小学科学物质概念承接初中化学概念学习",
        ),
    ]
    assert validate_relations(points, relations) == []


def test_three_stage_pipeline_keeps_phase_boundaries_and_resumes(tmp_path):
    req = request(Subject.MATH)
    source_catalog = catalog(Subject.MATH)
    citation = CurriculumCitation(
        source_id="moe-math-2022",
        locator="课程内容第16页",
        excerpt="数与代数",
        page_start=16,
        page_end=16,
    )
    course = OutlineNode(
        id="math.course",
        level=OutlineLevel.COURSE,
        subject=Subject.MATH,
        title="数学",
        grade_min=1,
        grade_max=2,
        expected_min_points=0,
        citations=[citation],
    )
    task = OutlineNode(
        id="math.task.g1-2",
        parent_id=course.id,
        level=OutlineLevel.STAGE_TASK,
        subject=Subject.MATH,
        title="数与运算（1-2年级）",
        grade_min=1,
        grade_max=2,
        expected_min_points=1,
        citations=[citation],
    )
    seed = CurriculumOutline(title=req.title, subjects=[Subject.MATH], nodes=[course, task])
    point = KnowledgePoint(
        id="math.natural-number-counting",
        outline_node_id=task.id,
        subject=Subject.MATH,
        grade_min=1,
        grade_max=2,
        name="自然数计数",
        definition="自然数计数是用自然数表示对象数量与顺序的方法",
        learning_expectation="能够用自然数表示物体的数量和顺序",
        concept_kind="concept",
        core_thinking=["数感", "符号意识"],
        subject_profile=MathKnowledgeProfile(
            representations=["实物数量", "自然数符号"],
            key_procedures=["逐一对应计数"],
        ),
        citations=[citation],
    )
    evidence = CurriculumEvidencePack(
        ocr_engine="test-ocr",
        pages=[
            CurriculumEvidencePage(
                source_id="moe-math-2022",
                pdf_page=23,
                logical_page=16,
                text="课程内容包含数与代数，自然数可以表示物体的数量和顺序。",
                image_sha256="b" * 64,
            )
        ],
    )
    outline_agents = [
        ScriptedProvider("outline-a", [seed.model_dump(mode="json")]),
        ScriptedProvider("outline-b", [seed.model_dump(mode="json")]),
    ]
    point_agents = [
        ScriptedProvider(
            "point-a",
            [{"outline_node_id": task.id, "points": [point.model_dump(mode="json")]}],
        ),
        ScriptedProvider(
            "point-b",
            [{"outline_node_id": task.id, "points": [point.model_dump(mode="json")]}],
        ),
    ]
    graph_agents = [
        ScriptedProvider("graph-a", [{"relations": []}, {"relations": []}]),
        ScriptedProvider("graph-b", [{"relations": []}, {"relations": []}]),
    ]

    def passing_report(selected_candidate_id: str) -> dict:
        return {
            "selected_candidate_id": selected_candidate_id,
            "scores": [
                {"dimension": name, "score": 95, "rationale": "通过"}
                for name in (
                    "completeness",
                    "accuracy",
                    "source_grounding",
                    "consistency",
                    "subject_fidelity",
                )
            ],
            "issues": [],
            "final_score": 95,
            "decision": "pass",
            "rerun_instructions": [],
        }

    supervisor = ScriptedProvider(
        "supervisor",
        [
            passing_report("outline-curriculum-test-outline-a-attempt-1"),
            passing_report("knowledge-point-math.task.g1-2-point-a-attempt-1"),
            passing_report("graph-theme-math.course-graph-a-attempt-1"),
            passing_report("graph-cross-scope-within-math-graph-a-attempt-1"),
        ],
    )
    repository = FactoryRepository(tmp_path / "factory.db")

    network = CurriculumPipeline(
        outline_agents=outline_agents,
        knowledge_point_agents=point_agents,
        graph_agents=graph_agents,
        supervisor=supervisor,
        checkpoint_dir=tmp_path / "checkpoints",
        repository=repository,
    ).run(req, source_catalog, seed, evidence)

    assert network.points == [point]
    assert network.coverage == build_coverage(seed, [point])
    assert all(len(agent.calls) == 1 for agent in outline_agents)
    assert all(len(agent.calls) == 1 for agent in point_agents)
    assert all(len(agent.calls) == 2 for agent in graph_agents)
    assert len(supervisor.calls) == 4
    input_digest = stable_digest(
        {
            "pipeline_version": "1.1",
            "request": req,
            "catalog": source_catalog,
            "seed": seed,
            "evidence": evidence,
        }
    )
    assert repository.load_curriculum_network(
        f"curriculum-curriculum-test-{input_digest[:12]}"
    ) == network
    release = publish_curriculum_network(
        network,
        request=req,
        catalog=source_catalog,
        evidence=evidence,
        version="curriculum-test-v1",
        repository=repository,
    )
    assert repository.load_curriculum_release("curriculum-test-v1") == release

    resumed_outline = [ScriptedProvider("outline-a", []), ScriptedProvider("outline-b", [])]
    resumed_points = [ScriptedProvider("point-a", []), ScriptedProvider("point-b", [])]
    resumed_graph = [ScriptedProvider("graph-a", []), ScriptedProvider("graph-b", [])]
    resumed_supervisor = ScriptedProvider("supervisor", [])
    resumed = CurriculumPipeline(
        outline_agents=resumed_outline,
        knowledge_point_agents=resumed_points,
        graph_agents=resumed_graph,
        supervisor=resumed_supervisor,
        checkpoint_dir=tmp_path / "checkpoints",
    ).run(req, source_catalog, seed, evidence)
    assert resumed == network
    assert all(agent.calls == [] for agent in resumed_outline)
    assert all(agent.calls == [] for agent in resumed_points)
    assert all(agent.calls == [] for agent in resumed_graph)
    assert resumed_supervisor.calls == []


def test_curriculum_stage_supervisor_can_request_bounded_rerun():
    graph_agents = [
        ScriptedProvider("graph-a", [{"relations": []}, {"relations": []}]),
        ScriptedProvider("graph-b", [{"relations": []}, {"relations": []}]),
    ]

    def report(score: int, decision: str, selected: str | None, instructions: list[str]) -> dict:
        return {
            "selected_candidate_id": selected,
            "scores": [
                {"dimension": name, "score": score, "rationale": "审查"}
                for name in (
                    "completeness",
                    "accuracy",
                    "source_grounding",
                    "consistency",
                    "subject_fidelity",
                )
            ],
            "issues": [],
            "final_score": score,
            "decision": decision,
            "rerun_instructions": instructions,
        }

    supervisor = ScriptedProvider(
        "supervisor",
        [
            report(80, "partial_rerun", None, ["补齐关系依据"]),
            report(95, "pass", "graph-unit-graph-a-attempt-2", []),
        ],
    )
    pipeline = CurriculumPipeline(
        outline_agents=[ScriptedProvider("outline-a", []), ScriptedProvider("outline-b", [])],
        knowledge_point_agents=[ScriptedProvider("point-a", []), ScriptedProvider("point-b", [])],
        graph_agents=graph_agents,
        supervisor=supervisor,
    )

    selected = pipeline._select_stage_candidate(
        run_id="curriculum-rerun-test",
        stage="graph",
        unit_id="unit",
        providers=graph_agents,
        max_reruns=1,
        produce=lambda provider, _attempt, _feedback: CurriculumRelationBatch.model_validate(
            provider.complete_json("system", "user")
        ),
        validate=lambda _candidate: [],
    )

    assert selected == CurriculumRelationBatch(relations=[])
    assert all(len(agent.calls) == 2 for agent in graph_agents)
    assert len(supervisor.calls) == 2
