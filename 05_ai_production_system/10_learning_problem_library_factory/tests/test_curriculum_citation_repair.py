from learning_problem_factory.curriculum_citation_repair import repair_point_citations
from learning_problem_factory.curriculum_models import (
    CurriculumCitation,
    CurriculumEvidencePage,
    KnowledgePoint,
    KnowledgePointBatch,
    MathKnowledgeProfile,
)
from learning_problem_factory.curriculum_validators import validate_points
from learning_problem_factory.models import Subject


def test_repairs_cross_page_excerpt_to_continuous_single_page_source() -> None:
    page = CurriculumEvidencePage(
        source_id="moe-math-2022",
        pdf_page=52,
        logical_page=45,
        text="能结合生活经验，编写含有数学知识的小故事；能用自己的语言表达数量关系。",
        image_sha256="a" * 64,
    )
    point = KnowledgePoint(
        id="math.story",
        outline_node_id="math.task",
        subject=Subject.MATH,
        grade_min=1,
        grade_max=2,
        name="数学故事表达",
        definition="运用数学知识编写故事并表达其中的数量关系",
        learning_expectation="能够编写数学故事并清楚表达其中的数量关系",
        concept_kind="application",
        core_thinking=["应用意识"],
        subject_profile=MathKnowledgeProfile(
            representations=["数学故事"],
            application_contexts=["生活经历"],
        ),
        citations=[
            CurriculumCitation(
                source_id="moe-math-2022",
                locator="课程内容第44-45页",
                excerpt=(
                    "数学连环画。能结合生活经验，编写含有数学知识的小故事；"
                    "能用自己的语言表达数量关系。"
                ),
                page_start=44,
                page_end=45,
            )
        ],
    )

    repaired, repairs = repair_point_citations(
        KnowledgePointBatch(outline_node_id="math.task", points=[point]),
        [page],
    )

    citation = repaired.points[0].citations[0]
    assert citation.page_start == citation.page_end == 45
    assert citation.excerpt in page.text
    assert repairs[0]["original_page_start"] == 44
    assert repairs[0]["matched_characters"] >= 16


def test_does_not_repair_low_similarity_excerpt() -> None:
    page = CurriculumEvidencePage(
        source_id="moe-math-2022",
        pdf_page=52,
        logical_page=45,
        text="认识时分秒并体会时间长短。",
        image_sha256="b" * 64,
    )
    citation = CurriculumCitation(
        source_id="moe-math-2022",
        locator="第45页",
        excerpt="完全无关的化学反应方程式知识内容",
        page_start=45,
        page_end=45,
    )
    point = KnowledgePoint(
        id="math.unrelated",
        outline_node_id="math.task",
        subject=Subject.MATH,
        grade_min=1,
        grade_max=2,
        name="无关候选",
        definition="这是一个不应被引用校正器错误修复的候选知识点",
        learning_expectation="能够验证低相似度引用不会被系统自动替换",
        concept_kind="concept",
        core_thinking=["验证"],
        subject_profile=MathKnowledgeProfile(representations=["文本"]),
        citations=[citation],
    )

    repaired, repairs = repair_point_citations(
        KnowledgePointBatch(outline_node_id="math.task", points=[point]),
        [page],
    )

    assert repaired.points[0].citations[0] == citation
    assert repairs == []


def test_repairs_exact_excerpt_reported_on_adjacent_authorized_page() -> None:
    page14 = CurriculumEvidencePage(
        source_id="moe-chemistry-2022",
        pdf_page=21,
        logical_page=14,
        text="通过具体的实验活动初步形成化学实验探究的一般思路与方法。",
        image_sha256="c" * 64,
    )
    page15 = CurriculumEvidencePage(
        source_id="moe-chemistry-2022",
        pdf_page=22,
        logical_page=15,
        text="学生必做实验及实践活动包括氧气的制取与性质。",
        image_sha256="d" * 64,
    )
    point = KnowledgePoint(
        id="chemistry.inquiry",
        outline_node_id="chemistry.task",
        subject=Subject.CHEMISTRY,
        grade_min=9,
        grade_max=9,
        name="实验探究思路",
        definition="围绕实验目的设计并实施实验后依据事实形成结论",
        learning_expectation="能够说明化学实验探究的一般思路与基本方法",
        concept_kind="practice",
        core_thinking=["证据推理"],
        subject_profile={
            "kind": "chemistry",
            "knowledge_type": "reasoning",
            "macro_micro_symbolic": False,
        },
        citations=[
            CurriculumCitation(
                source_id="moe-chemistry-2022",
                locator="课程内容第15页",
                excerpt="通过具体的实验活动初步形成化学实验探究的一般思路与方法。",
                page_start=15,
                page_end=15,
            )
        ],
    )

    repaired, repairs = repair_point_citations(
        KnowledgePointBatch(outline_node_id="chemistry.task", points=[point]),
        [page14, page15],
    )

    citation = repaired.points[0].citations[0]
    assert citation.page_start == citation.page_end == 14
    assert citation.excerpt in page14.text
    assert repairs[0]["match_ratio"] == 1.0
