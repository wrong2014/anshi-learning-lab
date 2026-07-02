from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from learning_problem_factory.models import ProductionRequest
from learning_problem_factory.recipes import get_recipe
from learning_problem_factory.specialized_models import SpecializedProductionOutcome
from learning_problem_factory.specialized_validators import validate_specialized_artifact


ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = ("math", "physics", "chemistry")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest_completed_outcome(subject: str) -> tuple[Path, SpecializedProductionOutcome]:
    run_dir = ROOT / "artifacts/core-thinking/runs" / subject
    for path in sorted(run_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        outcome = SpecializedProductionOutcome.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if outcome.run.status == "completed":
            return path, outcome
    raise ValueError(f"no completed outcome found for {subject}")


def namespace_artifact(artifact, subject: str):
    id_map = {
        dimension.id: f"{subject}.{dimension.id}"
        for dimension in artifact.dimensions
    }
    dimensions = [
        dimension.model_copy(
            update={
                "id": id_map[dimension.id],
                "depends_on": [id_map[item] for item in dimension.depends_on],
                "supports": [id_map[item] for item in dimension.supports],
            }
        )
        for dimension in artifact.dimensions
    ]
    return artifact.model_copy(update={"dimensions": dimensions})


def main() -> None:
    errors: list[str] = []
    checks: list[dict] = []
    subject_payloads: dict[str, dict] = {}
    namespaced_ids: list[str] = []
    dimensions_by_subject_and_name: dict[tuple[str, str], object] = {}

    for subject in SUBJECTS:
        request_path = ROOT / f"artifacts/core-thinking/requests/{subject}.json"
        request = ProductionRequest.model_validate_json(
            request_path.read_text(encoding="utf-8")
        )
        outcome_path, outcome = latest_completed_outcome(subject)
        recipe = get_recipe(request.recipe_id)
        review_scores = [report.final_score for report in outcome.reports]
        if not review_scores or any(
            score < 90 or report.decision.value != "pass"
            for score, report in zip(review_scores, outcome.reports, strict=True)
        ):
            errors.append(f"{subject}: not all supervision reports passed at 90+")

        normalized_artifacts = []
        module_names: list[str] = []
        aggregate_grades: set[int] = set()
        for artifact in outcome.artifacts:
            batch = next(
                batch for batch in outcome.run.plan.batches if batch.id == artifact.batch_id
            )
            issues = validate_specialized_artifact(artifact, request, recipe, batch)
            if issues:
                errors.extend(
                    f"{subject}/{artifact.batch_id}: {issue.code}: {issue.message}"
                    for issue in issues
                )
            normalized = namespace_artifact(artifact, subject)
            normalized_issues = validate_specialized_artifact(
                normalized, request, recipe, batch
            )
            if normalized_issues:
                errors.extend(
                    f"{subject}/{artifact.batch_id}/namespaced: {issue.code}: {issue.message}"
                    for issue in normalized_issues
                )
            normalized_artifacts.append(normalized.model_dump(mode="json"))
            for dimension in normalized.dimensions:
                namespaced_ids.append(dimension.id)
                module_names.append(dimension.name)
                dimensions_by_subject_and_name[(subject, dimension.name)] = dimension
                observers = {
                    signal.observer.value for signal in dimension.observable_deficits
                }
                if observers != {"teacher", "parent", "learner"}:
                    errors.append(
                        f"{subject}/{dimension.id}: incomplete observer coverage"
                    )
                for stage in dimension.stage_features:
                    aggregate_grades.update(range(stage.grade_min, stage.grade_max + 1))

        if set(module_names) != set(request.scope.modules):
            errors.append(
                f"{subject}: module mismatch; expected {request.scope.modules}, got {module_names}"
            )
        if aggregate_grades != set(range(1, 10)):
            errors.append(
                f"{subject}: aggregate grade coverage is {sorted(aggregate_grades)}"
            )
        documents = request.source_pack.documents if request.source_pack else []
        subject_payloads[subject] = {
            "request_id": request.id,
            "recipe_id": request.recipe_id,
            "request_file": str(request_path.relative_to(ROOT)).replace("\\", "/"),
            "request_sha256": digest(request_path),
            "outcome_file": str(outcome_path.relative_to(ROOT)).replace("\\", "/"),
            "outcome_sha256": digest(outcome_path),
            "review_scores": review_scores,
            "modules": module_names,
            "aggregate_grade_coverage": sorted(aggregate_grades),
            "source_pack": {
                "id": request.source_pack.id if request.source_pack else None,
                "title": request.source_pack.title if request.source_pack else None,
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
            "artifacts": normalized_artifacts,
        }
        checks.append(
            {
                "check": f"{subject}_production",
                "passed": not any(
                    item.startswith((f"{subject}:", f"{subject}/"))
                    for item in errors
                ),
                "scores": review_scores,
                "module_count": len(module_names),
                "grade_coverage": sorted(aggregate_grades),
            }
        )

    if len(namespaced_ids) != len(set(namespaced_ids)):
        errors.append("namespaced dimension ids are not globally unique")

    physics_model = dimensions_by_subject_and_name[("physics", "模型建构")]
    chemistry_model = dimensions_by_subject_and_name[("chemistry", "模型建构")]
    physics_questioning = dimensions_by_subject_and_name[("physics", "质疑创新")]
    chemistry_questioning = dimensions_by_subject_and_name[("chemistry", "质疑创新")]
    distinction_checks = {
        "physics_model_math_boundary": len(
            physics_model.profile.boundary_with_mathematics.strip()
        )
        >= 20,
        "chemistry_model_physics_distinction": len(
            chemistry_model.profile.distinction_from_physics.strip()
        )
        >= 20,
        "physics_questioning_math_boundary": len(
            physics_questioning.profile.boundary_with_mathematics.strip()
        )
        >= 20,
        "chemistry_questioning_physics_distinction": len(
            chemistry_questioning.profile.distinction_from_physics.strip()
        )
        >= 20,
    }
    if not all(distinction_checks.values()):
        errors.append("shared physics/chemistry concepts lack subject boundary detail")
    checks.append(
        {
            "check": "cross_subject_identity_and_boundaries",
            "passed": len(namespaced_ids) == len(set(namespaced_ids))
            and all(distinction_checks.values()),
            "dimension_count": len(namespaced_ids),
            "globally_unique_id_count": len(set(namespaced_ids)),
            "details": distinction_checks,
        }
    )

    all_documents = [
        document
        for payload in subject_payloads.values()
        for document in payload["source_pack"]["documents"]
    ]
    all_sources_human_verified = all(
        document["verified_by_human"] for document in all_documents
    )
    publication_blockers = []
    if not all_sources_human_verified:
        publication_blockers.append(
            "官方课标 OCR 页摘录尚未由人类逐页核验，不能发布为不可变正式版本。"
        )

    state = "validated_draft" if not errors else "failed_audit"
    generated_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "schema_version": "1.0",
        "bundle_id": "core-thinking-k9-math-physics-chemistry-2022-v1",
        "state": state,
        "generated_at": generated_at,
        "publication_blockers": publication_blockers,
        "namespace_policy": "All dimension ids are prefixed with subject at bundle time.",
        "subjects": subject_payloads,
        "cross_subject_audit": checks,
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
    output_dir = ROOT / "artifacts/core-thinking"
    bundle_path = output_dir / "core-thinking-k9-v1.0.0-draft.json"
    audit_path = output_dir / "core-thinking-k9-v1.0.0-audit.json"
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
