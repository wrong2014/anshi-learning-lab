from __future__ import annotations

from collections import Counter

from .curriculum_models import (
    CoverageEntry,
    CoverageState,
    CurriculumKnowledgeNetwork,
    CurriculumEvidencePack,
    CurriculumOutline,
    CurriculumPipelineRequest,
    CurriculumRelation,
    CurriculumRelationType,
    CurriculumSourceCatalog,
    KnowledgePoint,
    OutlineLevel,
)
from .models import IssueSeverity, ValidationIssue


def _error(code: str, message: str, path: str | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, severity=IssueSeverity.ERROR, message=message, path=path)


def _cycle(graph: dict[str, set[str]]) -> list[str] | None:
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
            found = visit(target)
            if found:
                return found
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        found = visit(node)
        if found:
            return found
    return None


def validate_outline(
    outline: CurriculumOutline,
    request: CurriculumPipelineRequest,
    catalog: CurriculumSourceCatalog,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ids = [node.id for node in outline.nodes]
    known_ids = set(ids)
    source_by_id = {source.id: source for source in catalog.sources}
    source_ids = set(source_by_id)
    if len(ids) != len(known_ids):
        issues.append(_error("outline.duplicate_id", "outline node ids must be unique", "nodes"))

    requested_subjects = set(request.subjects)
    actual_subjects = {node.subject for node in outline.nodes}
    missing_subjects = requested_subjects - actual_subjects
    if missing_subjects:
        issues.append(
            _error(
                "outline.missing_subject",
                f"outline is missing requested subjects: {sorted(item.value for item in missing_subjects)}",
            )
        )

    parent_graph: dict[str, set[str]] = {node.id: set() for node in outline.nodes}
    for index, node in enumerate(outline.nodes):
        if node.subject not in requested_subjects:
            issues.append(_error("outline.subject_out_of_scope", f"{node.id} is outside requested subjects"))
        if node.grade_min < request.grade_min or node.grade_max > request.grade_max:
            issues.append(_error("outline.grade_out_of_scope", f"{node.id} exceeds requested grade range"))
        if node.level == OutlineLevel.COURSE and node.parent_id is not None:
            issues.append(_error("outline.course_has_parent", f"course node {node.id} cannot have a parent"))
        if node.level != OutlineLevel.COURSE and node.parent_id not in known_ids:
            issues.append(_error("outline.missing_parent", f"{node.id} has unknown parent {node.parent_id}"))
        if node.parent_id in known_ids:
            parent_graph[node.id].add(node.parent_id)
        for citation in node.citations:
            if citation.source_id not in source_ids:
                issues.append(
                    _error(
                        "outline.unknown_source",
                        f"{node.id} cites unknown source {citation.source_id}",
                        f"nodes[{index}].citations",
                    )
                )
                continue
            source = source_by_id[citation.source_id]
            if source.subject != node.subject:
                issues.append(
                    _error(
                        "outline.source_subject_mismatch",
                        f"{node.id} cites {source.subject.value} source {source.id}",
                    )
                )
            if (
                citation.page_end is not None
                and citation.page_end + source.logical_page_offset > source.page_count
            ):
                issues.append(
                    _error(
                        "outline.page_out_of_range",
                        f"{node.id} cites logical page {citation.page_end} beyond {source.id}",
                    )
                )

    cycle = _cycle(parent_graph)
    if cycle:
        issues.append(_error("outline.parent_cycle", f"outline parent cycle: {' -> '.join(cycle)}"))

    stage_subjects = {node.subject for node in outline.nodes if node.level == OutlineLevel.STAGE_TASK}
    for subject in requested_subjects - stage_subjects:
        issues.append(_error("outline.no_stage_tasks", f"subject {subject.value} has no stage tasks"))
    return issues


def _normalized_ocr(value: str) -> str:
    return "".join(character for character in value if character.isalnum())


def validate_points(
    outline: CurriculumOutline,
    points: list[KnowledgePoint],
    evidence: CurriculumEvidencePack | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    stage_nodes = {node.id: node for node in outline.nodes if node.level == OutlineLevel.STAGE_TASK}
    ids = [point.id for point in points]
    if len(ids) != len(set(ids)):
        issues.append(_error("points.duplicate_id", "knowledge point ids must be unique"))
    counts = Counter(point.outline_node_id for point in points)
    evidence_by_page = (
        {(page.source_id, page.logical_page): page for page in evidence.pages if page.logical_page is not None}
        if evidence
        else {}
    )

    for point in points:
        node = stage_nodes.get(point.outline_node_id)
        if node is None:
            issues.append(_error("points.unknown_task", f"{point.id} references unknown stage task"))
            continue
        if point.subject != node.subject:
            issues.append(_error("points.subject_mismatch", f"{point.id} subject does not match its task"))
        if point.grade_min < node.grade_min or point.grade_max > node.grade_max:
            issues.append(_error("points.grade_mismatch", f"{point.id} exceeds its task grade range"))
        node_source_ids = {citation.source_id for citation in node.citations}
        if any(citation.source_id not in node_source_ids for citation in point.citations):
            issues.append(_error("points.source_escape", f"{point.id} cites a source not attached to its task"))
        if evidence:
            for citation in point.citations:
                if citation.page_start is None or citation.page_start != citation.page_end:
                    issues.append(
                        _error("points.imprecise_citation", f"{point.id} must cite exactly one logical page")
                    )
                    continue
                page = evidence_by_page.get((citation.source_id, citation.page_start))
                if page is None:
                    issues.append(
                        _error(
                            "points.missing_evidence_page",
                            f"{point.id} cites unavailable logical page {citation.page_start}",
                        )
                    )
                    continue
                if _normalized_ocr(citation.excerpt) not in _normalized_ocr(page.text):
                    issues.append(
                        _error(
                            "points.excerpt_not_found",
                            f"{point.id} citation excerpt is not present in OCR evidence",
                        )
                    )

    for node_id, node in stage_nodes.items():
        if counts[node_id] < node.expected_min_points:
            issues.append(
                _error(
                    "points.incomplete_task",
                    f"{node_id} has {counts[node_id]} points; expected at least {node.expected_min_points}",
                )
            )
    return issues


def build_coverage(outline: CurriculumOutline, points: list[KnowledgePoint]) -> list[CoverageEntry]:
    counts = Counter(point.outline_node_id for point in points)
    entries: list[CoverageEntry] = []
    for node in outline.nodes:
        if node.level != OutlineLevel.STAGE_TASK:
            continue
        actual = counts[node.id]
        state = (
            CoverageState.EMPTY
            if actual == 0
            else CoverageState.COMPLETE
            if actual >= node.expected_min_points
            else CoverageState.PARTIAL
        )
        entries.append(
            CoverageEntry(
                outline_node_id=node.id,
                expected_min_points=node.expected_min_points,
                actual_points=actual,
                state=state,
                missing_reason=None if state == CoverageState.COMPLETE else "knowledge-point agent coverage gap",
            )
        )
    return entries


def validate_relations(points: list[KnowledgePoint], relations: list[CurriculumRelation]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    point_ids = {point.id for point in points}
    seen: set[tuple[str, str, CurriculumRelationType]] = set()
    prerequisite_graph: dict[str, set[str]] = {point_id: set() for point_id in point_ids}
    subject_by_point = {point.id: point.subject for point in points}
    science_bridge_targets: set[str] = set()
    for relation in relations:
        key = (relation.source_point_id, relation.target_point_id, relation.relation_type)
        if key in seen:
            issues.append(_error("graph.duplicate_relation", f"duplicate relation: {key}"))
        seen.add(key)
        if relation.source_point_id not in point_ids or relation.target_point_id not in point_ids:
            issues.append(_error("graph.dangling_relation", f"unknown relation endpoint: {key}"))
        if relation.source_point_id == relation.target_point_id:
            issues.append(_error("graph.self_relation", f"self relation: {relation.source_point_id}"))
        if relation.relation_type == CurriculumRelationType.PREREQUISITE:
            prerequisite_graph.setdefault(relation.source_point_id, set()).add(relation.target_point_id)
        if relation.relation_type == CurriculumRelationType.BRIDGES_TO:
            source_subject = subject_by_point.get(relation.source_point_id)
            target_subject = subject_by_point.get(relation.target_point_id)
            if source_subject and target_subject:
                if source_subject.value == "science" and target_subject.value in {"physics", "chemistry"}:
                    science_bridge_targets.add(target_subject.value)
    cycle = _cycle(prerequisite_graph)
    if cycle:
        issues.append(_error("graph.prerequisite_cycle", f"prerequisite cycle: {' -> '.join(cycle)}"))

    subjects = {point.subject for point in points}
    if {"science", "physics", "chemistry"}.issubset({item.value for item in subjects}):
        missing_targets = {"physics", "chemistry"} - science_bridge_targets
        if missing_targets:
            issues.append(
                _error(
                    "graph.missing_science_bridge",
                    "science scope requires bridges_to relations into both physics and chemistry; "
                    f"missing targets: {sorted(missing_targets)}",
                )
            )
    return issues


def validate_network(
    network: CurriculumKnowledgeNetwork,
    request: CurriculumPipelineRequest,
    catalog: CurriculumSourceCatalog,
    evidence: CurriculumEvidencePack | None = None,
) -> list[ValidationIssue]:
    issues = validate_outline(network.outline, request, catalog)
    issues.extend(validate_points(network.outline, network.points, evidence))
    issues.extend(validate_relations(network.points, network.relations))
    expected_coverage = build_coverage(network.outline, network.points)
    if network.coverage != expected_coverage:
        issues.append(_error("coverage.mismatch", "coverage ledger does not match outline and points"))
    if request.require_complete_coverage and any(
        entry.state != CoverageState.COMPLETE for entry in network.coverage
    ):
        issues.append(_error("coverage.incomplete", "complete coverage is required before release"))
    return issues
