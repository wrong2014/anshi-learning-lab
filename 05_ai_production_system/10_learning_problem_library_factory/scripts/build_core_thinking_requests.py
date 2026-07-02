from __future__ import annotations

from pathlib import Path

from learning_problem_factory.curriculum_models import CurriculumEvidencePack
from learning_problem_factory.models import (
    EvidenceMode,
    ProductionRequest,
    ProductionScope,
    SourceDocument,
    SourceKind,
    SourcePack,
    Subject,
)


ROOT = Path(__file__).resolve().parents[1]


def extract_pages(
    evidence: CurriculumEvidencePack,
    source_id: str,
    ranges: list[tuple[int, int]],
) -> str:
    selected = []
    for page in evidence.pages:
        if page.source_id != source_id or page.logical_page is None:
            continue
        if any(start <= page.logical_page <= end for start, end in ranges):
            selected.append(page)
    selected.sort(key=lambda page: page.logical_page or 0)
    if not selected:
        raise ValueError(f"no evidence pages selected for {source_id}: {ranges}")
    return "\n\n".join(
        f"【逻辑页 {page.logical_page}】\n{page.text}" for page in selected
    )


def document(
    evidence: CurriculumEvidencePack,
    *,
    id: str,
    title: str,
    source_id: str,
    ranges: list[tuple[int, int]],
) -> SourceDocument:
    range_text = "、".join(
        str(start) if start == end else f"{start}-{end}" for start, end in ranges
    )
    return SourceDocument(
        id=id,
        title=title,
        kind=SourceKind.CURRICULUM_STANDARD,
        publisher_or_author="中华人民共和国教育部",
        edition_or_year="2022",
        locator=f"《义务教育课程标准（2022年版）》逻辑页 {range_text}",
        content=extract_pages(evidence, source_id, ranges),
        verified_by_human=False,
    )


def main() -> None:
    evidence = CurriculumEvidencePack.model_validate_json(
        (ROOT / "artifacts/ocr/official-curriculum-2022.json").read_text(
            encoding="utf-8-sig"
        )
    )
    science_precursor = document(
        evidence,
        id="moe-science-2022-thinking-pages-4-13",
        title="义务教育科学课程核心素养、科学思维与学段特征",
        source_id="moe-science-2022",
        ranges=[(4, 13)],
    )
    requests = [
        ProductionRequest(
            id="core-thinking-math-k9-2022-v1",
            recipe_id="math_core_thinking_v1",
            evidence_mode=EvidenceMode.SOURCE_GROUNDED,
            source_pack=SourcePack(
                id="source-pack-math-core-thinking-2022-v1",
                title="数学核心思维官方课标来源包",
                scope_note=(
                    "只依据教育部2022版数学课程标准中的核心素养构成、内涵、"
                    "学段表现和学业质量描述。"
                ),
                documents=[
                    document(
                        evidence,
                        id="moe-math-2022-thinking-pages-5-11",
                        title="义务教育数学课程核心素养构成与主要表现",
                        source_id="moe-math-2022",
                        ranges=[(5, 11)],
                    ),
                    document(
                        evidence,
                        id="moe-math-2022-quality-pages-81-85",
                        title="义务教育数学学业质量与学段表现",
                        source_id="moe-math-2022",
                        ranges=[(81, 85)],
                    ),
                    document(
                        evidence,
                        id="moe-math-2022-progression-page-93",
                        title="数学核心素养小学到初中的螺旋进阶说明",
                        source_id="moe-math-2022",
                        ranges=[(93, 93)],
                    ),
                ],
            ),
            scope=ProductionScope(
                subject=Subject.MATH,
                grade_min=1,
                grade_max=9,
                modules=[
                    "数学眼光与抽象",
                    "数学思维与推理论证",
                    "数学语言与模型应用",
                ],
                granularity="module",
            ),
            requested_by="local-production",
            max_reruns=5,
        ),
        ProductionRequest(
            id="core-thinking-physics-k9-2022-v1",
            recipe_id="physics_core_thinking_v1",
            evidence_mode=EvidenceMode.SOURCE_GROUNDED,
            source_pack=SourcePack(
                id="source-pack-physics-core-thinking-2022-v1",
                title="物理核心思维与小学科学前置官方来源包",
                scope_note=(
                    "小学阶段依据科学课标的科学思维进阶，初中阶段依据物理课标"
                    "的模型建构、推理、论证和质疑创新。"
                ),
                documents=[
                    science_precursor,
                    document(
                        evidence,
                        id="moe-physics-2022-thinking-pages-4-6",
                        title="义务教育物理核心素养与科学思维要素",
                        source_id="moe-physics-2022",
                        ranges=[(4, 6)],
                    ),
                    document(
                        evidence,
                        id="moe-physics-2022-quality-pages-39-40",
                        title="义务教育物理学业质量中的思维表现",
                        source_id="moe-physics-2022",
                        ranges=[(39, 40)],
                    ),
                    document(
                        evidence,
                        id="moe-physics-2022-evaluation-pages-45-46",
                        title="义务教育物理核心素养的可观察评价证据",
                        source_id="moe-physics-2022",
                        ranges=[(45, 46)],
                    ),
                ],
            ),
            scope=ProductionScope(
                subject=Subject.PHYSICS,
                grade_min=1,
                grade_max=9,
                modules=[
                    "模型建构",
                    "科学推理",
                    "科学论证",
                    "质疑创新",
                    "小学科学前置",
                ],
                granularity="module",
            ),
            requested_by="local-production",
            max_reruns=5,
        ),
        ProductionRequest(
            id="core-thinking-chemistry-k9-2022-v1",
            recipe_id="chemistry_core_thinking_v1",
            evidence_mode=EvidenceMode.SOURCE_GROUNDED,
            source_pack=SourcePack(
                id="source-pack-chemistry-core-thinking-2022-v1",
                title="化学核心思维与小学科学前置官方来源包",
                scope_note=(
                    "小学阶段依据科学课标的科学思维进阶，初中阶段依据化学课标"
                    "的宏观—微观—符号、证据推理与模型建构。"
                ),
                documents=[
                    science_precursor,
                    document(
                        evidence,
                        id="moe-chemistry-2022-thinking-pages-5-7",
                        title="义务教育化学核心素养与科学思维内涵",
                        source_id="moe-chemistry-2022",
                        ranges=[(5, 7)],
                    ),
                    document(
                        evidence,
                        id="moe-chemistry-2022-quality-pages-38-40",
                        title="义务教育化学学业质量中的思维表现",
                        source_id="moe-chemistry-2022",
                        ranges=[(38, 40)],
                    ),
                    document(
                        evidence,
                        id="moe-chemistry-2022-teaching-page-45",
                        title="化学高阶思维活动与可观察学习表现",
                        source_id="moe-chemistry-2022",
                        ranges=[(45, 45)],
                    ),
                ],
            ),
            scope=ProductionScope(
                subject=Subject.CHEMISTRY,
                grade_min=1,
                grade_max=9,
                modules=[
                    "宏观—微观—符号表征",
                    "证据推理",
                    "模型建构",
                    "分类与守恒",
                    "质疑创新",
                    "小学科学前置",
                ],
                granularity="module",
            ),
            requested_by="local-production",
            max_reruns=5,
        ),
    ]
    output_dir = ROOT / "artifacts/core-thinking/requests"
    output_dir.mkdir(parents=True, exist_ok=True)
    for request in requests:
        target = output_dir / f"{request.scope.subject.value}.json"
        target.write_text(request.model_dump_json(indent=2), encoding="utf-8")
        print(target.resolve())


if __name__ == "__main__":
    main()
