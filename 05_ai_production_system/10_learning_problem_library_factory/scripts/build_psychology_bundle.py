from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from learning_problem_factory.models import ProductionRequest
from learning_problem_factory.recipes import get_recipe
from learning_problem_factory.specialized_models import SpecializedProductionOutcome
from learning_problem_factory.specialized_taxonomy import PSYCHOLOGY_DIMENSION_TAXONOMY
from learning_problem_factory.specialized_validators import validate_specialized_artifact


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest_completed_outcome() -> tuple[Path, SpecializedProductionOutcome]:
    run_dir = ROOT / "artifacts/psychology/runs"
    for path in sorted(run_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        outcome = SpecializedProductionOutcome.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if outcome.run.status == "completed":
            return path, outcome
    raise ValueError("no completed psychology outcome found")


def normalize_relation_views(artifacts):
    dimensions = {
        dimension.id: dimension
        for artifact in artifacts
        for dimension in artifact.dimensions
    }
    edges: set[tuple[str, str]] = set()
    for dimension in dimensions.values():
        edges.update((dimension.id, target) for target in dimension.may_lead_to)
        edges.update((source, dimension.id) for source in dimension.may_be_caused_by)
    unknown = sorted(
        (source, target)
        for source, target in edges
        if source not in dimensions or target not in dimensions
    )
    self_relations = sorted(
        (source, target) for source, target in edges if source == target
    )
    if unknown or self_relations:
        raise ValueError(
            f"invalid psychology relations: unknown={unknown}, self={self_relations}"
        )
    inverse_mismatches = 0
    for source, target in edges:
        if target not in dimensions[source].may_lead_to:
            inverse_mismatches += 1
        if source not in dimensions[target].may_be_caused_by:
            inverse_mismatches += 1
    outgoing = {dimension_id: set() for dimension_id in dimensions}
    incoming = {dimension_id: set() for dimension_id in dimensions}
    for source, target in edges:
        outgoing[source].add(target)
        incoming[target].add(source)
    normalized_artifacts = []
    for artifact in artifacts:
        normalized_dimensions = [
            dimension.model_copy(
                update={
                    "may_lead_to": sorted(outgoing[dimension.id]),
                    "may_be_caused_by": sorted(incoming[dimension.id]),
                }
            )
            for dimension in artifact.dimensions
        ]
        normalized_artifacts.append(
            artifact.model_copy(update={"dimensions": normalized_dimensions})
        )
    return normalized_artifacts, len(edges), inverse_mismatches


def selected_repair_warnings(database: Path, outcome: SpecializedProductionOutcome) -> list[dict]:
    selected = set(outcome.run.accepted_candidate_ids)
    if not selected:
        return []
    connection = sqlite3.connect(database)
    rows = connection.execute(
        "SELECT candidate_id, validation_json FROM specialized_attempts WHERE run_id = ?",
        (outcome.run.id,),
    ).fetchall()
    warnings = []
    for candidate_id, raw_issues in rows:
        if candidate_id not in selected:
            continue
        for issue in json.loads(raw_issues):
            if issue["severity"] != "error":
                warnings.append({"candidate_id": candidate_id, **issue})
    return warnings


def main() -> None:
    request_path = ROOT / "artifacts/psychology/requests/psychology-cognition.json"
    request = ProductionRequest.model_validate_json(
        request_path.read_text(encoding="utf-8")
    )
    outcome_path, outcome = latest_completed_outcome()
    recipe = get_recipe(request.recipe_id)
    errors: list[str] = []

    final_scores: dict[str, int] = {}
    for accepted_id in outcome.run.accepted_candidate_ids:
        matching = [
            report
            for report in outcome.reports
            if report.selected_candidate_id == accepted_id and report.decision.value == "pass"
        ]
        if not matching:
            errors.append(f"accepted candidate has no passing report: {accepted_id}")
            continue
        batch_id = next(
            artifact.batch_id
            for artifact in outcome.artifacts
            if artifact.candidate_id == accepted_id
        )
        final_scores[batch_id] = matching[-1].final_score

    if len(final_scores) != len(outcome.run.plan.batches):
        errors.append(
            f"expected {len(outcome.run.plan.batches)} passing batches; got {len(final_scores)}"
        )
    if any(score < 90 for score in final_scores.values()):
        errors.append(f"one or more final batch scores are below 90: {final_scores}")

    raw_dimensions = []
    for artifact in outcome.artifacts:
        batch = next(
            batch for batch in outcome.run.plan.batches if batch.id == artifact.batch_id
        )
        issues = validate_specialized_artifact(artifact, request, recipe, batch)
        errors.extend(
            f"{artifact.batch_id}: {issue.code}: {issue.message}"
            for issue in issues
        )
        raw_dimensions.extend(artifact.dimensions)

    names = [dimension.name for dimension in raw_dimensions]
    ids = [dimension.id for dimension in raw_dimensions]
    layers = Counter(dimension.layer for dimension in raw_dimensions)
    if set(names) != set(request.scope.modules) or len(names) != len(request.scope.modules):
        errors.append("final dimensions do not exactly match the 12 requested modules")
    if len(ids) != len(set(ids)):
        errors.append("psychology dimension ids are not globally unique")
    if layers != Counter({"psychology": 5, "cognition": 4, "motivation": 3}):
        errors.append(f"unexpected layer counts: {dict(layers)}")

    normalized_artifacts, relation_count, inverse_mismatches = normalize_relation_views(
        outcome.artifacts
    )
    normalized_dimensions = [
        dimension
        for artifact in normalized_artifacts
        for dimension in artifact.dimensions
    ]
    normalized_by_id = {dimension.id: dimension for dimension in normalized_dimensions}
    normalized_mismatches = []
    for dimension in normalized_dimensions:
        for target in dimension.may_lead_to:
            if dimension.id not in normalized_by_id[target].may_be_caused_by:
                normalized_mismatches.append((dimension.id, target))
    if normalized_mismatches:
        errors.append(f"normalized relation views remain inconsistent: {normalized_mismatches}")

    documents = request.source_pack.documents if request.source_pack else []
    all_sources_human_verified = all(document.verified_by_human for document in documents)
    publication_blockers = []
    if not all_sources_human_verified:
        publication_blockers.append(
            "12份理论证据卡和3份安全指南摘要尚未由教育心理/临床专业人员逐条核验。"
        )
    publication_blockers.append(
        "高风险心理与认知资料必须由具名人类审批者签署后才能正式发布。"
    )

    repair_warnings = selected_repair_warnings(
        ROOT / "artifacts/psychology/factory.db",
        outcome,
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    state = "human_review_required" if not errors else "failed_audit"
    checks = [
        {
            "check": "production_and_scores",
            "passed": len(final_scores) == len(outcome.run.plan.batches)
            and all(score >= 90 for score in final_scores.values()),
            "final_scores": final_scores,
        },
        {
            "check": "taxonomy_and_layer_coverage",
            "passed": len(ids) == 12
            and len(set(ids)) == 12
            and set(names) == set(PSYCHOLOGY_DIMENSION_TAXONOMY)
            and layers == Counter({"psychology": 5, "cognition": 4, "motivation": 3}),
            "dimension_count": len(ids),
            "layer_counts": dict(layers),
        },
        {
            "check": "deterministic_artifact_validation",
            "passed": not any(":" in error and "expected" not in error for error in errors),
            "error_count": len(errors),
        },
        {
            "check": "relationship_view_consistency",
            "passed": not normalized_mismatches,
            "relation_count": relation_count,
            "raw_inverse_mismatches_repaired": inverse_mismatches,
            "normalized_inverse_mismatches": len(normalized_mismatches),
        },
        {
            "check": "human_approval_gate",
            "passed": not all_sources_human_verified and recipe.requires_human_approval,
            "source_documents": len(documents),
            "all_sources_human_verified": all_sources_human_verified,
            "requires_human_approval": recipe.requires_human_approval,
        },
    ]
    bundle = {
        "schema_version": "1.0",
        "bundle_id": "psychology-cognition-k9-2026-v1",
        "state": state,
        "generated_at": generated_at,
        "relationship_policy": (
            "may_lead_to/may_be_caused_by are source-constrained, testable learning "
            "hypotheses; they are not clinical causal conclusions."
        ),
        "publication_blockers": publication_blockers,
        "request_file": str(request_path.relative_to(ROOT)).replace("\\", "/"),
        "request_sha256": digest(request_path),
        "outcome_file": str(outcome_path.relative_to(ROOT)).replace("\\", "/"),
        "outcome_sha256": digest(outcome_path),
        "final_scores": final_scores,
        "source_pack": {
            "id": request.source_pack.id if request.source_pack else None,
            "documents": [
                {
                    "id": document.id,
                    "title": document.title,
                    "publisher_or_author": document.publisher_or_author,
                    "edition_or_year": document.edition_or_year,
                    "locator": document.locator,
                    "verified_by_human": document.verified_by_human,
                }
                for document in documents
            ],
        },
        "selected_candidate_warnings": repair_warnings,
        "artifacts": [
            artifact.model_dump(mode="json") for artifact in normalized_artifacts
        ],
        "checks": checks,
    }
    audit = {
        "schema_version": "1.0",
        "bundle_id": bundle["bundle_id"],
        "generated_at": generated_at,
        "passed": not errors,
        "state": state,
        "errors": errors,
        "publication_blockers": publication_blockers,
        "checks": checks,
    }
    output_dir = ROOT / "artifacts/psychology"
    bundle_path = output_dir / "psychology-cognition-k9-v1.0.0-human-review.json"
    audit_path = output_dir / "psychology-cognition-k9-v1.0.0-audit.json"
    bundle_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(bundle_path.resolve())
    print(audit_path.resolve())
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
