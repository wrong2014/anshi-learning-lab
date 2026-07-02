from learning_problem_factory.curriculum_models import (
    CurriculumRelation,
    CurriculumRelationBatch,
    CurriculumRelationType,
)
from learning_problem_factory.curriculum_relation_repair import sanitize_relation_batch


def relation(source: str, target: str) -> CurriculumRelation:
    return CurriculumRelation(
        source_point_id=source,
        target_point_id=target,
        relation_type=CurriculumRelationType.SUPPORTS,
        rationale="该关系用于测试图关系清洗器的确定性行为",
    )


def test_removes_dangling_and_duplicate_relations_without_changing_valid_edges() -> None:
    existing = relation("point-a", "point-b")
    valid = relation("point-b", "point-c")
    dangling = relation("point-c", "invented-point")
    batch = CurriculumRelationBatch(relations=[existing, valid, valid, dangling])

    sanitized, repairs = sanitize_relation_batch(
        batch,
        allowed_point_ids={"point-a", "point-b", "point-c"},
        existing_relations=[existing],
    )

    assert sanitized.relations == [valid]
    assert [item["reason"] for item in repairs] == [
        "duplicate_relation",
        "duplicate_relation",
        "dangling_endpoint",
    ]
