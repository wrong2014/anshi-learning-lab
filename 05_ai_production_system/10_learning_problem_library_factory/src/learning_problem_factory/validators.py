from __future__ import annotations

import json
from typing import Iterable

from .models import (
    EvidenceMode,
    ID_PATTERN,
    ExecutionPlan,
    IssueSeverity,
    KnowledgeArtifact,
    ProductionRequest,
    ProductionRecipe,
    RelationType,
    SupervisionReport,
    ValidationIssue,
)


FORBIDDEN_LABELS = ("粗心", "不努力", "态度不端正", "笨", "智商低", "家长做错了")


def _issue(code: str, message: str, path: str | None = None, *, warning: bool = False) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=IssueSeverity.WARNING if warning else IssueSeverity.ERROR,
        message=message,
        path=path,
    )


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = path.index(node)
            return path[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        path.append(node)
        for target in graph.get(node, set()):
            cycle = visit(target)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def validate_plan(plan: ExecutionPlan, request: ProductionRequest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if plan.request_id != request.id:
        issues.append(_issue("plan.request_mismatch", "plan request_id does not match the production request"))
    source_ids = {item.id for item in request.source_pack.documents} if request.source_pack else set()
    batch_ids = {item.id for item in plan.batches}

    for index, batch in enumerate(plan.batches):
        if request.evidence_mode == EvidenceMode.MODEL_DISTILLATION and batch.source_ids:
            issues.append(
                _issue(
                    "plan.source_ids_in_distillation_mode",
                    "model_distillation batches must not reference source_ids; use empty arrays",
                    f"batches[{index}].source_ids",
                )
            )
        unknown_sources = set(batch.source_ids) - source_ids
        if unknown_sources:
            issues.append(
                _issue(
                    "plan.unknown_source",
                    f"batch references unknown sources: {sorted(unknown_sources)}",
                    f"batches[{index}].source_ids",
                )
            )
        unknown_dependencies = set(batch.depends_on) - batch_ids
        if unknown_dependencies:
            issues.append(
                _issue(
                    "plan.unknown_dependency",
                    f"batch references unknown dependencies: {sorted(unknown_dependencies)}",
                    f"batches[{index}].depends_on",
                )
            )

    graph = {batch.id: set(batch.depends_on) for batch in plan.batches}
    cycle = _find_cycle(graph)
    if cycle:
        issues.append(_issue("plan.dependency_cycle", f"batch dependency cycle: {' -> '.join(cycle)}"))
    return issues


def _all_citations(artifact: KnowledgeArtifact) -> Iterable[tuple[str, str]]:
    for node_index, node in enumerate(artifact.nodes):
        for citation in node.citations:
            yield citation.source_id, f"nodes[{node_index}].citations"
    for relation_index, relation in enumerate(artifact.relations):
        for citation in relation.citations:
            yield citation.source_id, f"relations[{relation_index}].citations"
    for block_index, block in enumerate(artifact.learning_blocks):
        for citation in block.citations:
            yield citation.source_id, f"learning_blocks[{block_index}].citations"


def validate_artifact(artifact: KnowledgeArtifact, request: ProductionRequest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    known_sources = {item.id for item in request.source_pack.documents} if request.source_pack else set()
    declared_sources = set(artifact.source_ids)

    if artifact.request_id != request.id:
        issues.append(_issue("artifact.request_mismatch", "artifact request_id does not match the run request"))
    if artifact.recipe_id != request.recipe_id:
        issues.append(_issue("artifact.recipe_mismatch", "artifact recipe_id does not match the run request"))
    if request.evidence_mode == EvidenceMode.MODEL_DISTILLATION and declared_sources:
        issues.append(
            _issue(
                "artifact.source_ids_in_distillation_mode",
                "model_distillation artifacts must not declare source_ids; use empty arrays",
                "source_ids",
            )
        )
    if declared_sources - known_sources:
        issues.append(
            _issue("artifact.unknown_source", f"artifact declares unknown sources: {sorted(declared_sources - known_sources)}")
        )

    node_ids = [item.id for item in artifact.nodes]
    if len(node_ids) != len(set(node_ids)):
        issues.append(_issue("artifact.duplicate_node_id", "knowledge node ids must be unique", "nodes"))
    known_nodes = set(node_ids)
    for index, node in enumerate(artifact.nodes):
        if not ID_PATTERN.fullmatch(node.id):
            issues.append(_issue("artifact.invalid_node_id", f"invalid stable node id: {node.id}", f"nodes[{index}].id"))
        if request.scope.subject.value != "cross_subject" and node.subject != request.scope.subject:
            issues.append(
                _issue(
                    "artifact.subject_out_of_scope",
                    f"node subject {node.subject.value} is outside request subject {request.scope.subject.value}",
                    f"nodes[{index}].subject",
                )
            )
        if node.grade_min < request.scope.grade_min or node.grade_max > request.scope.grade_max:
            issues.append(
                _issue(
                    "artifact.grade_out_of_scope",
                    f"node grade range {node.grade_min}-{node.grade_max} exceeds request scope",
                    f"nodes[{index}]",
                )
            )

    block_ids = [item.id for item in artifact.learning_blocks]
    if len(block_ids) != len(set(block_ids)):
        issues.append(_issue("artifact.duplicate_block_id", "learning block ids must be unique", "learning_blocks"))

    block_node_ids: set[str] = set()
    signal_ids: set[str] = set()
    for index, block in enumerate(artifact.learning_blocks):
        if not ID_PATTERN.fullmatch(block.id):
            issues.append(
                _issue("artifact.invalid_block_id", f"invalid stable learning block id: {block.id}", f"learning_blocks[{index}].id")
            )
        if block.node_id not in known_nodes:
            issues.append(
                _issue(
                    "artifact.dangling_block_node",
                    f"learning block points to unknown node {block.node_id}",
                    f"learning_blocks[{index}].node_id",
                )
            )
        block_node_ids.add(block.node_id)
        for signal in block.observable_signals:
            if not ID_PATTERN.fullmatch(signal.id):
                issues.append(
                    _issue(
                        "artifact.invalid_signal_id",
                        f"invalid stable signal id: {signal.id}",
                        f"learning_blocks[{index}].observable_signals",
                    )
                )
            if signal.id in signal_ids:
                issues.append(
                    _issue(
                        "artifact.duplicate_signal_id",
                        f"observable signal id is duplicated: {signal.id}",
                        f"learning_blocks[{index}].observable_signals",
                    )
                )
            signal_ids.add(signal.id)
        for blueprint_index, blueprint in enumerate(block.probe_blueprints):
            option_ids = [option.id for option in blueprint.options]
            if len(option_ids) != len(set(option_ids)):
                issues.append(
                    _issue(
                        "artifact.duplicate_probe_option",
                        "probe option ids must be unique within a blueprint",
                        f"learning_blocks[{index}].probe_blueprints[{blueprint_index}].options",
                    )
                )

    missing_blocks = known_nodes - block_node_ids
    if missing_blocks:
        issues.append(
            _issue(
                "artifact.node_without_learning_block",
                f"nodes have no learning block: {sorted(missing_blocks)}",
                "learning_blocks",
            )
        )

    prerequisite_graph: dict[str, set[str]] = {node_id: set() for node_id in known_nodes}
    for index, relation in enumerate(artifact.relations):
        if relation.source_node_id not in known_nodes or relation.target_node_id not in known_nodes:
            issues.append(
                _issue(
                    "artifact.dangling_relation",
                    f"relation has unknown endpoint: {relation.source_node_id} -> {relation.target_node_id}",
                    f"relations[{index}]",
                )
            )
        if relation.source_node_id == relation.target_node_id:
            issues.append(_issue("artifact.self_relation", "a node cannot relate to itself", f"relations[{index}]"))
        if relation.relation_type == RelationType.PREREQUISITE:
            prerequisite_graph.setdefault(relation.source_node_id, set()).add(relation.target_node_id)

    cycle = _find_cycle(prerequisite_graph)
    if cycle:
        issues.append(_issue("artifact.prerequisite_cycle", f"prerequisite cycle: {' -> '.join(cycle)}", "relations"))

    for source_id, path in _all_citations(artifact):
        if request.evidence_mode == EvidenceMode.MODEL_DISTILLATION:
            issues.append(
                _issue(
                    "artifact.citation_in_distillation_mode",
                    "model_distillation artifacts must not fabricate source citations",
                    path,
                )
            )
            continue
        if source_id not in known_sources:
            issues.append(_issue("artifact.unknown_citation", f"citation references unknown source {source_id}", path))
        elif source_id not in declared_sources:
            issues.append(_issue("artifact.undeclared_citation", f"citation source {source_id} is not declared", path))

    if request.evidence_mode == EvidenceMode.SOURCE_GROUNDED:
        if not artifact.source_ids:
            issues.append(_issue("artifact.missing_sources", "source_grounded artifacts must declare at least one source_id", "source_ids"))
        for index, node in enumerate(artifact.nodes):
            if not node.citations:
                issues.append(
                    _issue(
                        "artifact.missing_node_citation",
                        "source_grounded knowledge nodes must include at least one citation",
                        f"nodes[{index}].citations",
                    )
                )
        for index, relation in enumerate(artifact.relations):
            if not relation.citations:
                issues.append(
                    _issue(
                        "artifact.missing_relation_citation",
                        "source_grounded relations must include at least one citation",
                        f"relations[{index}].citations",
                    )
                )
        for index, block in enumerate(artifact.learning_blocks):
            if not block.citations:
                issues.append(
                    _issue(
                        "artifact.missing_block_citation",
                        "source_grounded learning blocks must include at least one citation",
                        f"learning_blocks[{index}].citations",
                    )
                )

    serialized = json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False)
    for label in FORBIDDEN_LABELS:
        if label in serialized:
            issues.append(_issue("artifact.forbidden_label", f"forbidden subjective label found: {label}"))

    if request.evidence_mode == EvidenceMode.MODEL_DISTILLATION:
        issues.append(
            _issue(
                "artifact.model_distilled",
                "artifact was generated from model knowledge and still needs later source audit before external publication",
                warning=True,
            )
        )

    if (
        request.evidence_mode == EvidenceMode.SOURCE_GROUNDED
        and request.source_pack
        and not any(item.verified_by_human for item in request.source_pack.documents)
    ):
        issues.append(
            _issue(
                "source_pack.unverified",
                "source pack has no human-verified document and cannot be treated as publication-ready",
                warning=True,
            )
        )
    return issues


def has_errors(issues: Iterable[ValidationIssue]) -> bool:
    return any(item.severity == IssueSeverity.ERROR for item in issues)


def validate_supervision_report(
    report: SupervisionReport,
    recipe: ProductionRecipe,
    candidate_ids: set[str],
    valid_candidate_ids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    score_by_dimension = {item.dimension: item.score for item in report.scores}
    if len(score_by_dimension) != len(report.scores):
        issues.append(_issue("supervisor.duplicate_dimension", "rubric dimensions must be scored exactly once"))

    expected_dimensions = {item.name for item in recipe.rubric}
    actual_dimensions = set(score_by_dimension)
    if actual_dimensions != expected_dimensions:
        issues.append(
            _issue(
                "supervisor.rubric_mismatch",
                f"expected dimensions {sorted(expected_dimensions)}, got {sorted(actual_dimensions)}",
            )
        )
    else:
        calculated = round(
            sum(score_by_dimension[item.name] * item.weight for item in recipe.rubric)
        )
        if report.final_score != calculated:
            issues.append(
                _issue(
                    "supervisor.score_mismatch",
                    f"weighted score must be {calculated}, got {report.final_score}",
                )
            )

    if report.selected_candidate_id and report.selected_candidate_id not in candidate_ids:
        issues.append(
            _issue(
                "supervisor.unknown_candidate",
                f"selected candidate does not exist: {report.selected_candidate_id}",
            )
        )
    if report.decision.value == "pass" and report.selected_candidate_id not in valid_candidate_ids:
        issues.append(
            _issue(
                "supervisor.invalid_candidate_selected",
                "a passing report must select a candidate that passed deterministic validation",
            )
        )
    return issues


def topological_batches(plan: ExecutionPlan) -> list[str]:
    remaining = {batch.id: set(batch.depends_on) for batch in plan.batches}
    ordered: list[str] = []
    while remaining:
        ready = sorted(batch_id for batch_id, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("execution plan contains a dependency cycle")
        ordered.extend(ready)
        for batch_id in ready:
            remaining.pop(batch_id)
        for deps in remaining.values():
            deps.difference_update(ready)
    return ordered
