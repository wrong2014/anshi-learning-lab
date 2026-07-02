from __future__ import annotations

import json

from .models import (
    ArtifactKind,
    EvidenceMode,
    ID_PATTERN,
    IssueSeverity,
    PlanBatch,
    ProductionRequest,
    ProductionRecipe,
    SourceCitation,
    ValidationIssue,
)
from .specialized_models import CoreThinkingArtifact, PsychologyArtifact, SpecializedArtifact
from .specialized_taxonomy import (
    PSYCHOLOGY_DIMENSION_TAXONOMY,
    PSYCHOLOGY_ID_TO_NAME,
)
from .validators import FORBIDDEN_LABELS


def _issue(code: str, message: str, *, warning: bool = False) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=IssueSeverity.WARNING if warning else IssueSeverity.ERROR,
        message=message,
    )


def _validate_citations(
    citations: list[SourceCitation],
    declared_sources: set[str],
    known_sources: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for citation in citations:
        if citation.source_id not in known_sources:
            issues.append(_issue("material.unknown_citation", f"unknown source {citation.source_id}"))
        elif citation.source_id not in declared_sources:
            issues.append(
                _issue("material.undeclared_citation", f"source {citation.source_id} is not declared")
            )
    return issues


def _find_cycle(graph: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(target) for target in graph.get(node, set()) if target in graph):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def validate_specialized_artifact(
    artifact: SpecializedArtifact,
    request: ProductionRequest,
    recipe: ProductionRecipe,
    batch: PlanBatch | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if request.evidence_mode != EvidenceMode.SOURCE_GROUNDED or request.source_pack is None:
        issues.append(_issue("material.source_required", "specialized materials require source_grounded mode"))
        return issues
    if artifact.request_id != request.id or artifact.recipe_id != request.recipe_id:
        issues.append(_issue("material.identity_mismatch", "artifact identity does not match request"))
    declared_sources = set(artifact.source_ids)
    known_sources = {source.id for source in request.source_pack.documents}
    if not declared_sources:
        issues.append(_issue("material.missing_sources", "artifact must declare sources"))
    if declared_sources - known_sources:
        issues.append(
            _issue("material.unknown_source", f"unknown sources: {sorted(declared_sources - known_sources)}")
        )

    if isinstance(artifact, CoreThinkingArtifact):
        if recipe.artifact_kind != ArtifactKind.CORE_THINKING:
            issues.append(_issue("material.kind_mismatch", "recipe does not produce core thinking"))
        if batch is not None:
            dimension_names = [dimension.name for dimension in artifact.dimensions]
            if len(dimension_names) != len(batch.module_names):
                issues.append(
                    _issue(
                        "thinking.batch_dimension_count",
                        f"batch {batch.id} requires {len(batch.module_names)} dimensions; "
                        f"got {len(dimension_names)}",
                    )
                )
            if set(dimension_names) != set(batch.module_names):
                issues.append(
                    _issue(
                        "thinking.batch_module_mismatch",
                        f"dimension names must exactly match batch modules; expected "
                        f"{sorted(batch.module_names)}, got {sorted(dimension_names)}",
                    )
                )
        ids = [dimension.id for dimension in artifact.dimensions]
        if len(ids) != len(set(ids)):
            issues.append(_issue("thinking.duplicate_id", "thinking dimension ids must be unique"))
        known_ids = set(ids)
        graph: dict[str, set[str]] = {}
        for dimension in artifact.dimensions:
            if not ID_PATTERN.fullmatch(dimension.id):
                issues.append(_issue("thinking.invalid_id", f"invalid dimension id {dimension.id}"))
            if dimension.subject != request.scope.subject:
                issues.append(_issue("thinking.subject_mismatch", f"{dimension.id} is outside subject scope"))
            if any(
                feature.grade_min < request.scope.grade_min
                or feature.grade_max > request.scope.grade_max
                for feature in dimension.stage_features
            ):
                issues.append(_issue("thinking.grade_mismatch", f"{dimension.id} exceeds grade scope"))
            relation_ids = set(dimension.depends_on) | set(dimension.supports)
            invalid_relation_ids = sorted(
                item for item in relation_ids if not ID_PATTERN.fullmatch(item)
            )
            if invalid_relation_ids:
                issues.append(
                    _issue(
                        "thinking.invalid_relation_id",
                        f"{dimension.id} relations must use stable ids: {invalid_relation_ids}",
                    )
                )
            unknown_relation_ids = sorted(relation_ids - known_ids)
            if unknown_relation_ids:
                issues.append(
                    _issue(
                        "thinking.unknown_relation",
                        f"{dimension.id} references dimensions outside this artifact: "
                        f"{unknown_relation_ids}",
                    )
                )
            if dimension.id in relation_ids:
                issues.append(
                    _issue(
                        "thinking.self_relation",
                        f"{dimension.id} cannot depend on or support itself",
                    )
                )
            observers = {signal.observer.value for signal in dimension.observable_deficits}
            required_observers = {"teacher", "parent", "learner"}
            if observers != required_observers:
                issues.append(
                    _issue(
                        "thinking.observer_coverage",
                        f"{dimension.id} must cover teacher, parent and learner; got "
                        f"{sorted(observers)}",
                    )
                )
            grade_counts = {
                grade: sum(
                    feature.grade_min <= grade <= feature.grade_max
                    for feature in dimension.stage_features
                )
                for grade in range(
                    min(feature.grade_min for feature in dimension.stage_features),
                    max(feature.grade_max for feature in dimension.stage_features) + 1,
                )
            }
            gaps = [grade for grade, count in grade_counts.items() if count == 0]
            overlaps = [grade for grade, count in grade_counts.items() if count > 1]
            if gaps:
                issues.append(
                    _issue(
                        "thinking.stage_gap",
                        f"{dimension.id} has uncovered grades: {gaps}",
                    )
                )
            if overlaps:
                issues.append(
                    _issue(
                        "thinking.stage_overlap",
                        f"{dimension.id} has overlapping stage features: {overlaps}",
                    )
                )
            graph[dimension.id] = {
                item for item in dimension.supports if item in known_ids
            }
            issues.extend(_validate_citations(dimension.citations, declared_sources, known_sources))
        if _find_cycle(graph):
            issues.append(_issue("thinking.support_cycle", "thinking support relations contain a cycle"))
    elif isinstance(artifact, PsychologyArtifact):
        if recipe.artifact_kind != ArtifactKind.PSYCHOLOGY_COGNITION:
            issues.append(_issue("material.kind_mismatch", "recipe does not produce psychology material"))
        if batch is not None:
            dimension_names = [dimension.name for dimension in artifact.dimensions]
            if len(dimension_names) != len(batch.module_names):
                issues.append(
                    _issue(
                        "psychology.batch_dimension_count",
                        f"batch {batch.id} requires {len(batch.module_names)} dimensions; "
                        f"got {len(dimension_names)}",
                    )
                )
            if set(dimension_names) != set(batch.module_names):
                issues.append(
                    _issue(
                        "psychology.batch_module_mismatch",
                        f"dimension names must exactly match batch modules; expected "
                        f"{sorted(batch.module_names)}, got {sorted(dimension_names)}",
                    )
                )
        ids = [dimension.id for dimension in artifact.dimensions]
        if len(ids) != len(set(ids)):
            issues.append(_issue("psychology.duplicate_id", "psychology dimension ids must be unique"))
        for dimension in artifact.dimensions:
            if not ID_PATTERN.fullmatch(dimension.id):
                issues.append(_issue("psychology.invalid_id", f"invalid dimension id {dimension.id}"))
            expected = PSYCHOLOGY_DIMENSION_TAXONOMY.get(dimension.name)
            if expected is None:
                issues.append(
                    _issue(
                        "psychology.unknown_dimension",
                        f"unknown psychology dimension name {dimension.name}",
                    )
                )
            elif (dimension.id, dimension.layer) != expected:
                issues.append(
                    _issue(
                        "psychology.taxonomy_mismatch",
                        f"{dimension.name} requires id/layer {expected}; got "
                        f"{(dimension.id, dimension.layer)}",
                    )
                )
            relation_ids = set(dimension.may_lead_to) | set(
                dimension.may_be_caused_by
            )
            unknown_relation_ids = sorted(relation_ids - set(PSYCHOLOGY_ID_TO_NAME))
            if unknown_relation_ids:
                issues.append(
                    _issue(
                        "psychology.unknown_relation",
                        f"{dimension.id} has unknown relation ids: {unknown_relation_ids}",
                    )
                )
            if dimension.id in relation_ids:
                issues.append(
                    _issue(
                        "psychology.self_relation",
                        f"{dimension.id} cannot reference itself",
                    )
                )
            theory_source_ids = {
                citation.source_id for citation in dimension.theory_citations
            }
            if not any(source_id.startswith("theory-") for source_id in theory_source_ids):
                issues.append(
                    _issue(
                        "psychology.missing_theory_source",
                        f"{dimension.id} requires at least one theory-* citation",
                    )
                )
            safety_source_ids = {citation.source_id for citation in dimension.citations}
            if not any(
                source_id.startswith("guideline-") for source_id in safety_source_ids
            ):
                issues.append(
                    _issue(
                        "psychology.missing_safety_source",
                        f"{dimension.id} requires at least one guideline-* citation",
                    )
                )
            if len(dimension.ai_support_scope) < 3:
                issues.append(
                    _issue(
                        "psychology.ai_scope_too_thin",
                        f"{dimension.id} requires at least three low-risk AI support items",
                    )
                )
            unsafe_ai_terms = ("诊断", "治疗", "治愈", "替代专业", "危机处置")
            unsafe_ai_items = [
                item
                for item in dimension.ai_support_scope
                if any(term in item for term in unsafe_ai_terms)
            ]
            if unsafe_ai_items:
                issues.append(
                    _issue(
                        "psychology.unsafe_ai_scope",
                        f"{dimension.id} contains unsafe AI support claims: {unsafe_ai_items}",
                    )
                )
            if len(dimension.referral_conditions) < 3:
                issues.append(
                    _issue(
                        "psychology.referral_too_thin",
                        f"{dimension.id} requires at least three referral conditions",
                    )
                )
            referral_text = " ".join(dimension.referral_conditions)
            safety_terms = ("自伤", "自杀", "伤害自己", "伤害他人", "安全风险")
            persistence_terms = ("持续", "数周", "功能", "日常", "学校生活")
            if not any(term in referral_text for term in safety_terms):
                issues.append(
                    _issue(
                        "psychology.missing_crisis_referral",
                        f"{dimension.id} referral conditions omit immediate safety risk",
                    )
                )
            if not any(term in referral_text for term in persistence_terms):
                issues.append(
                    _issue(
                        "psychology.missing_function_referral",
                        f"{dimension.id} referral conditions omit persistence or functional impairment",
                    )
                )
            issues.extend(
                _validate_citations(
                    dimension.theory_citations + dimension.citations,
                    declared_sources,
                    known_sources,
                )
            )

    serialized = json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False)
    for label in FORBIDDEN_LABELS:
        if label in serialized:
            issues.append(_issue("material.forbidden_label", f"forbidden subjective label: {label}"))
    return issues
