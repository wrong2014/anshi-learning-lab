from __future__ import annotations

import re

from .curriculum_models import (
    CurriculumCitation,
    CurriculumOutline,
    CurriculumPipelineRequest,
    CurriculumSourceCatalog,
    OutlineLevel,
    OutlineNode,
)
from .models import Subject


SUBJECT_STRUCTURE: dict[Subject, dict[str, object]] = {
    Subject.MATH: {
        "source_id": "moe-math-2022",
        "course_title": "义务教育数学",
        "locator": "课程内容，第16页；目录与表2",
        "excerpt": "课程内容由数与代数、图形与几何、统计与概率、综合与实践四个学习领域组成。",
        "content_pages": (16, 79),
        "grades": [(1, 2), (3, 4), (5, 6), (7, 9)],
        "themes": ["数与代数", "图形与几何", "统计与概率", "综合与实践"],
    },
    Subject.SCIENCE: {
        "source_id": "moe-science-2022",
        "course_title": "义务教育科学",
        "locator": "目录第1-2页；课程内容第16-111页",
        "excerpt": "科学课程设置13个学科核心概念，并按三个小学学段组织内容。",
        "content_pages": (16, 111),
        "grades": [(1, 2), (3, 4), (5, 6)],
        "themes": [
            "物质的结构与性质",
            "物质的变化与化学反应",
            "物质的运动与相互作用",
            "能的转化与能量守恒",
            "生命系统的构成层次",
            "生物体的稳态与调节",
            "生物与环境的相互关系",
            "生命的延续与进化",
            "宇宙中的地球",
            "地球系统",
            "人类活动与环境",
            "技术、工程与社会",
            "工程设计与物化",
        ],
    },
    Subject.PHYSICS: {
        "source_id": "moe-physics-2022",
        "course_title": "义务教育物理",
        "locator": "目录第1页；课程内容第7-38页",
        "excerpt": "课程内容由物质、运动和相互作用、能量、实验探究、跨学科实践五个一级主题构成。",
        "content_pages": (7, 38),
        "grades": [(8, 9)],
        "themes": ["物质", "运动和相互作用", "能量", "实验探究", "跨学科实践"],
    },
    Subject.CHEMISTRY: {
        "source_id": "moe-chemistry-2022",
        "course_title": "义务教育化学",
        "locator": "目录第1页；课程内容第10-36页",
        "excerpt": "课程内容包含科学探究与化学实验、物质的性质与应用、物质的组成与结构、物质的化学变化、化学与社会·跨学科实践。",
        "content_pages": (10, 36),
        "grades": [(9, 9)],
        "themes": [
            "科学探究与化学实验",
            "物质的性质与应用",
            "物质的组成与结构",
            "物质的化学变化",
            "化学与社会·跨学科实践",
        ],
    },
}


# (grade_min, grade_max, logical_page_start, logical_page_end), indexed by theme order.
THEME_PAGE_RANGES: dict[Subject, list[list[tuple[int, int, int, int]]]] = {
    Subject.MATH: [
        [(1, 6, 17, 26), (7, 9, 53, 61)],
        [(1, 6, 27, 35), (7, 9, 62, 72)],
        [(1, 6, 36, 41), (7, 9, 73, 76)],
        [(1, 6, 42, 52), (7, 9, 77, 79)],
    ],
    Subject.SCIENCE: [
        [(1, 6, 19, 27)],
        [(1, 6, 28, 33)],
        [(1, 6, 34, 42)],
        [(1, 6, 43, 47)],
        [(1, 6, 48, 55)],
        [(1, 6, 56, 60)],
        [(1, 6, 61, 66)],
        [(1, 6, 67, 71)],
        [(1, 6, 72, 77)],
        [(1, 6, 78, 83)],
        [(1, 6, 84, 89)],
        [(1, 6, 90, 101)],
        [(1, 6, 102, 111)],
    ],
    Subject.PHYSICS: [
        [(8, 9, 8, 13)],
        [(8, 9, 14, 20)],
        [(8, 9, 21, 27)],
        [(8, 9, 28, 32)],
        [(8, 9, 33, 38)],
    ],
    Subject.CHEMISTRY: [
        [(9, 9, 12, 17)],
        [(9, 9, 18, 22)],
        [(9, 9, 23, 25)],
        [(9, 9, 26, 30)],
        [(9, 9, 31, 36)],
    ],
}


def _slug(index: int, title: str) -> str:
    ascii_hint = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return ascii_hint or f"topic-{index:02d}"


def build_official_seed(
    request: CurriculumPipelineRequest,
    catalog: CurriculumSourceCatalog,
) -> CurriculumOutline:
    source_ids = {source.id for source in catalog.sources}
    nodes: list[OutlineNode] = []
    for subject in request.subjects:
        if subject not in SUBJECT_STRUCTURE:
            raise ValueError(f"no official curriculum seed is registered for {subject.value}")
        spec = SUBJECT_STRUCTURE[subject]
        source_id = str(spec["source_id"])
        if source_id not in source_ids:
            raise ValueError(f"official source catalog is missing {source_id}")
        citation = CurriculumCitation(
            source_id=source_id,
            locator=str(spec["locator"]),
            excerpt=str(spec["excerpt"]),
            page_start=spec["content_pages"][0],  # type: ignore[index]
            page_end=spec["content_pages"][1],  # type: ignore[index]
        )
        grade_ranges = [
            (max(start, request.grade_min), min(end, request.grade_max))
            for start, end in spec["grades"]  # type: ignore[union-attr]
            if max(start, request.grade_min) <= min(end, request.grade_max)
        ]
        if not grade_ranges:
            continue
        subject_min = min(start for start, _ in grade_ranges)
        subject_max = max(end for _, end in grade_ranges)
        course_id = f"{subject.value}.course"
        nodes.append(
            OutlineNode(
                id=course_id,
                level=OutlineLevel.COURSE,
                subject=subject,
                title=str(spec["course_title"]),
                grade_min=subject_min,
                grade_max=subject_max,
                expected_min_points=0,
                citations=[citation],
            )
        )
        for index, theme in enumerate(spec["themes"], start=1):  # type: ignore[union-attr]
            ranges = THEME_PAGE_RANGES[subject][index - 1]
            theme_page_start = min(item[2] for item in ranges)
            theme_page_end = max(item[3] for item in ranges)
            theme_citation = citation.model_copy(
                update={
                    "locator": f"课程内容第{theme_page_start}-{theme_page_end}页",
                    "excerpt": f"课标课程内容主题：{theme}",
                    "page_start": theme_page_start,
                    "page_end": theme_page_end,
                }
            )
            theme_id = f"{subject.value}.theme-{index:02d}-{_slug(index, str(theme))}"
            nodes.append(
                OutlineNode(
                    id=theme_id,
                    parent_id=course_id,
                    level=OutlineLevel.THEME,
                    subject=subject,
                    title=str(theme),
                    grade_min=subject_min,
                    grade_max=subject_max,
                    expected_min_points=0,
                    citations=[theme_citation],
                )
            )
            for grade_min, grade_max in grade_ranges:
                page_range = next(
                    item
                    for item in ranges
                    if item[0] <= grade_min and item[1] >= grade_max
                )
                task_citation = theme_citation.model_copy(
                    update={
                        "locator": f"课程内容第{page_range[2]}-{page_range[3]}页",
                        "page_start": page_range[2],
                        "page_end": page_range[3],
                    }
                )
                nodes.append(
                    OutlineNode(
                        id=f"{theme_id}.g{grade_min}-{grade_max}",
                        parent_id=theme_id,
                        level=OutlineLevel.STAGE_TASK,
                        subject=subject,
                        title=f"{theme}（{grade_min}-{grade_max}年级）",
                        grade_min=grade_min,
                        grade_max=grade_max,
                        expected_min_points=3,
                        citations=[task_citation],
                    )
                )
    return CurriculumOutline(
        title=request.title,
        subjects=request.subjects,
        nodes=nodes,
    )
