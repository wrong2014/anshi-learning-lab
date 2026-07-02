from __future__ import annotations

from .curriculum_models import CurriculumRelation, CurriculumRelationBatch


def _key(relation: CurriculumRelation) -> tuple[str, str, str]:
    return (
        relation.source_point_id,
        relation.target_point_id,
        relation.relation_type.value,
    )


def sanitize_relation_batch(
    batch: CurriculumRelationBatch,
    *,
    allowed_point_ids: set[str],
    existing_relations: list[CurriculumRelation] | None = None,
) -> tuple[CurriculumRelationBatch, list[dict]]:
    """Remove only objectively invalid dangling or duplicate relations."""

    seen = {_key(relation) for relation in (existing_relations or [])}
    accepted: list[CurriculumRelation] = []
    repairs: list[dict] = []
    for relation in batch.relations:
        relation_key = _key(relation)
        if (
            relation.source_point_id not in allowed_point_ids
            or relation.target_point_id not in allowed_point_ids
        ):
            repairs.append(
                {
                    "action": "remove_relation",
                    "reason": "dangling_endpoint",
                    "relation": relation.model_dump(mode="json"),
                }
            )
            continue
        if relation_key in seen:
            repairs.append(
                {
                    "action": "remove_relation",
                    "reason": "duplicate_relation",
                    "relation": relation.model_dump(mode="json"),
                }
            )
            continue
        seen.add(relation_key)
        accepted.append(relation)
    return CurriculumRelationBatch(relations=accepted), repairs
