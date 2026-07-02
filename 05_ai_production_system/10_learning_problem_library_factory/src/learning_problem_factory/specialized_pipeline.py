from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from .models import (
    ArtifactKind,
    Decision,
    EvidenceMode,
    ExecutionPlan,
    IssueSeverity,
    ProductionRecipe,
    ProductionRequest,
    Subject,
    SupervisionReport,
    ValidationIssue,
    stable_digest,
)
from .providers import JsonProvider
from .repository import FactoryRepository
from .specialized_models import (
    SpecializedArtifact,
    SpecializedProductionOutcome,
    SpecializedProductionRun,
    SpecializedReleaseBundle,
    SpecializedReleaseManifest,
)
from .specialized_prompts import (
    specialized_executor_prompts,
    specialized_planner_prompts,
    specialized_supervisor_prompts,
)
from .specialized_taxonomy import (
    PSYCHOLOGY_GUIDELINE_SOURCE_IDS,
    PSYCHOLOGY_THEORY_SOURCE_BY_MODULE,
)
from .specialized_validators import validate_specialized_artifact
from .validators import (
    has_errors,
    topological_batches,
    validate_plan,
    validate_supervision_report,
)


ARTIFACT_ADAPTER = TypeAdapter(SpecializedArtifact)


SUBJECTIVE_LABEL_REPLACEMENTS = (
    ("笨拙", "操作不熟练"),
    ("粗心", "检查行为不稳定"),
    ("不努力", "任务投入减少"),
    ("态度不端正", "参与方式与任务要求不匹配"),
    ("智商低", "当前任务表现较弱"),
    ("家长做错了", "家庭支持方式可能需要调整"),
    ("笨", "能力不足"),
)


def _sanitize_subjective_labels(
    artifact: SpecializedArtifact,
) -> tuple[SpecializedArtifact, list[ValidationIssue]]:
    payload = artifact.model_dump(mode="python")
    repaired_paths: list[str] = []

    def repair(value, path: str):
        if isinstance(value, dict):
            return {
                key: repair(item, f"{path}.{key}") for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                repair(item, f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        if isinstance(value, str):
            repaired = value
            for label, replacement in SUBJECTIVE_LABEL_REPLACEMENTS:
                repaired = repaired.replace(label, replacement)
            if repaired != value:
                repaired_paths.append(path)
            return repaired
        return value

    repaired_payload = repair(payload, "artifact")
    if not repaired_paths:
        return artifact, []
    repaired_artifact = ARTIFACT_ADAPTER.validate_python(repaired_payload)
    return repaired_artifact, [
        ValidationIssue(
            code="material.subjective_label_rewritten",
            severity=IssueSeverity.WARNING,
            message=(
                "subjective labels were deterministically rewritten at: "
                + ", ".join(repaired_paths)
            ),
        )
    ]


def _normalize_supervision_score(
    report: SupervisionReport,
    recipe: ProductionRecipe,
) -> SupervisionReport:
    score_by_dimension = {item.dimension: item.score for item in report.scores}
    if len(score_by_dimension) != len(report.scores):
        return report
    if set(score_by_dimension) != {item.name for item in recipe.rubric}:
        return report
    calculated = round(
        sum(score_by_dimension[item.name] * item.weight for item in recipe.rubric)
    )
    if calculated == report.final_score:
        return report
    decision = report.decision
    if decision != Decision.HUMAN_REVIEW:
        decision = (
            Decision.PASS
            if calculated >= 90
            else Decision.PARTIAL_RERUN
            if calculated >= 70
            else Decision.FULL_RERUN
        )
    issue = ValidationIssue(
        code="supervisor.score_recomputed",
        severity=IssueSeverity.INFO,
        message=(
            f"final_score was recomputed from rubric weights: "
            f"{report.final_score} -> {calculated}"
        ),
    )
    return report.model_copy(
        update={
            "final_score": calculated,
            "decision": decision,
            "issues": report.issues + [issue],
        }
    )


def _normalize_psychology_plan_sources(
    plan: ExecutionPlan,
    request: ProductionRequest,
    recipe: ProductionRecipe,
) -> ExecutionPlan:
    if recipe.artifact_kind != ArtifactKind.PSYCHOLOGY_COGNITION:
        return plan
    available = {source.id for source in request.source_pack.documents}  # type: ignore[union-attr]
    batches = []
    for batch in plan.batches:
        required = set(PSYCHOLOGY_GUIDELINE_SOURCE_IDS)
        for module_name in batch.module_names:
            source_id = PSYCHOLOGY_THEORY_SOURCE_BY_MODULE.get(module_name)
            if source_id is None:
                raise ValueError(f"unknown psychology module in plan: {module_name}")
            required.add(source_id)
        missing = required - available
        if missing:
            raise ValueError(
                f"psychology batch {batch.id} is missing required sources: {sorted(missing)}"
            )
        batches.append(batch.model_copy(update={"source_ids": sorted(required)}))
    return plan.model_copy(update={"batches": batches})


def _validate_specialized_plan_scope(
    plan: ExecutionPlan,
    request: ProductionRequest,
    recipe: ProductionRecipe,
) -> None:
    planned_modules = [
        module_name for batch in plan.batches for module_name in batch.module_names
    ]
    if len(planned_modules) != len(set(planned_modules)):
        raise ValueError("specialized plan repeats one or more modules")
    if set(planned_modules) != set(request.scope.modules):
        raise ValueError(
            "specialized plan modules do not match request scope; "
            f"expected {sorted(request.scope.modules)}, got {sorted(planned_modules)}"
        )
    if recipe.artifact_kind == ArtifactKind.PSYCHOLOGY_COGNITION:
        from .specialized_taxonomy import PSYCHOLOGY_DIMENSION_TAXONOMY

        for batch in plan.batches:
            layers = {
                PSYCHOLOGY_DIMENSION_TAXONOMY[module_name][1]
                for module_name in batch.module_names
            }
            if len(layers) != 1:
                raise ValueError(
                    f"psychology batch {batch.id} mixes taxonomy layers: {sorted(layers)}"
                )


class SpecializedMaterialFactory:
    def __init__(
        self,
        *,
        planner: JsonProvider,
        executors: list[JsonProvider],
        supervisor: JsonProvider,
        recipe: ProductionRecipe,
        repository: FactoryRepository,
    ):
        if len(executors) < 2:
            raise ValueError("specialized material production requires at least two executors")
        if recipe.artifact_kind == ArtifactKind.KNOWLEDGE_GRAPH:
            raise ValueError("knowledge graph recipes must use CurriculumPipeline")
        self.planner = planner
        self.executors = executors
        self.supervisor = supervisor
        self.recipe = recipe
        self.repository = repository

    def run(self, request: ProductionRequest) -> SpecializedProductionOutcome:
        if request.recipe_id != self.recipe.id:
            raise ValueError("request recipe does not match specialized factory recipe")
        if request.evidence_mode != EvidenceMode.SOURCE_GROUNDED or request.source_pack is None:
            raise ValueError("core thinking and psychology production require source_grounded mode")
        if self.recipe.subject != Subject.CROSS_SUBJECT and request.scope.subject != self.recipe.subject:
            raise ValueError("request subject does not match specialized recipe")

        run = SpecializedProductionRun(
            id=f"specialized-run-{uuid4().hex}",
            request=request,
            status="created",
        )
        reports: list[SupervisionReport] = []
        accepted: list[SpecializedArtifact] = []
        self.repository.save_specialized_run(run)
        try:
            system, user = specialized_planner_prompts(request, self.recipe)
            plan = ExecutionPlan.model_validate(self.planner.complete_json(system, user))
            plan = _normalize_psychology_plan_sources(plan, request, self.recipe)
            _validate_specialized_plan_scope(plan, request, self.recipe)
            plan_issues = validate_plan(plan, request)
            if has_errors(plan_issues):
                raise ValueError(
                    "invalid specialized plan: "
                    + "; ".join(issue.message for issue in plan_issues)
                )
            run.plan = plan
            run.status = "planned"
            self.repository.save_specialized_run(run)
            run.status = "running"
            self.repository.save_specialized_run(run)
            batch_by_id = {batch.id: batch for batch in plan.batches}

            for batch_id in topological_batches(plan):
                batch = batch_by_id[batch_id]
                feedback: list[str] = []
                accepted_artifact: SpecializedArtifact | None = None
                valid_artifact_by_provider: dict[str, SpecializedArtifact] = {}
                issues_by_valid_artifact: dict[str, list[ValidationIssue]] = {}
                for attempt in range(1, request.max_reruns + 2):
                    candidates, provider_errors = self._execute(request, batch, attempt, feedback)
                    issues_by_candidate: dict[str, list[ValidationIssue]] = {}
                    sanitized_candidates: list[SpecializedArtifact] = []
                    for raw_artifact in candidates:
                        artifact, repair_issues = _sanitize_subjective_labels(raw_artifact)
                        sanitized_candidates.append(artifact)
                        issues = repair_issues + validate_specialized_artifact(
                            artifact,
                            request,
                            self.recipe,
                            batch,
                        )
                        issues_by_candidate[artifact.candidate_id] = issues
                        self.repository.record_specialized_attempt(
                            run.id,
                            batch.id,
                            attempt,
                            artifact,
                            issues,
                        )
                    candidates = sanitized_candidates
                    current_valid = [
                        artifact
                        for artifact in candidates
                        if not has_errors(issues_by_candidate[artifact.candidate_id])
                    ]
                    for artifact in current_valid:
                        previous = valid_artifact_by_provider.get(artifact.provider_name)
                        if previous:
                            issues_by_valid_artifact.pop(previous.candidate_id, None)
                        valid_artifact_by_provider[artifact.provider_name] = artifact
                        issues_by_valid_artifact[artifact.candidate_id] = issues_by_candidate[
                            artifact.candidate_id
                        ]
                    pooled_candidates = sorted(
                        valid_artifact_by_provider.values(),
                        key=lambda artifact: artifact.provider_name,
                    )
                    valid_ids = {artifact.candidate_id for artifact in pooled_candidates}
                    if len(valid_ids) < 2 or not current_valid:
                        feedback = provider_errors + [
                            f"{candidate_id}: {issue.message}"
                            for candidate_id, issues in issues_by_candidate.items()
                            for issue in issues
                            if issue.severity == IssueSeverity.ERROR
                        ]
                        feedback.append(
                            f"at least two valid candidates are required; got {len(valid_ids)}"
                        )
                        continue

                    report = self._supervise(
                        request,
                        batch,
                        pooled_candidates,
                        issues_by_valid_artifact,
                        valid_ids,
                    )
                    reports.append(report)
                    self.repository.record_specialized_review(run.id, batch.id, attempt, report)
                    if report.decision == Decision.HUMAN_REVIEW:
                        run.status = "needs_human"
                        self.repository.save_specialized_run(run)
                        return SpecializedProductionOutcome(
                            run=run,
                            artifacts=accepted,
                            reports=reports,
                        )
                    if report.decision == Decision.PASS:
                        accepted_artifact = next(
                            artifact
                            for artifact in pooled_candidates
                            if artifact.candidate_id == report.selected_candidate_id
                        )
                        break
                    feedback = report.rerun_instructions or [
                        issue.message for issue in report.issues
                    ]
                if accepted_artifact is None:
                    run.status = "needs_human"
                    run.error = f"batch {batch.id} exceeded the rerun limit"
                    self.repository.save_specialized_run(run)
                    return SpecializedProductionOutcome(run=run, artifacts=accepted, reports=reports)
                accepted.append(accepted_artifact)
                run.accepted_candidate_ids.append(accepted_artifact.candidate_id)
                self.repository.save_specialized_run(run)

            run.status = "completed"
            self.repository.save_specialized_run(run)
            return SpecializedProductionOutcome(run=run, artifacts=accepted, reports=reports)
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            self.repository.save_specialized_run(run)
            raise

    def _execute(self, request, batch, attempt: int, feedback: list[str]):
        candidates: list[SpecializedArtifact] = []
        errors: list[str] = []

        def call(provider: JsonProvider) -> SpecializedArtifact:
            system, user = specialized_executor_prompts(
                request,
                self.recipe,
                batch,
                provider.name,
                attempt,
                feedback,
            )
            artifact = ARTIFACT_ADAPTER.validate_python(provider.complete_json(system, user))
            return artifact.model_copy(
                update={
                    "recipe_id": self.recipe.id,
                    "request_id": request.id,
                    "batch_id": batch.id,
                    "candidate_id": f"{batch.id}-{provider.name}-attempt-{attempt}",
                    "provider_name": provider.name,
                }
            )

        with ThreadPoolExecutor(max_workers=len(self.executors)) as pool:
            futures = {pool.submit(call, provider): provider for provider in self.executors}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    candidates.append(future.result())
                except (RuntimeError, ValueError, ValidationError) as exc:
                    errors.append(f"provider {provider.name}: {exc}")
        candidates.sort(key=lambda artifact: artifact.provider_name)
        return candidates, errors

    def _supervise(
        self,
        request: ProductionRequest,
        batch,
        candidates: list[SpecializedArtifact],
        issues_by_candidate: dict[str, list[ValidationIssue]],
        valid_ids: set[str],
    ) -> SupervisionReport:
        system, user = specialized_supervisor_prompts(
            request,
            self.recipe,
            batch,
            candidates,
            issues_by_candidate,
        )
        last_error = ""
        for _ in range(2):
            retry_user = user + (f"\n上次报告无效：{last_error}" if last_error else "")
            try:
                report = SupervisionReport.model_validate(
                    self.supervisor.complete_json(system, retry_user)
                )
                report = _normalize_supervision_score(report, self.recipe)
            except ValidationError as exc:
                last_error = str(exc)
                continue
            report_issues = validate_supervision_report(
                report,
                self.recipe,
                {artifact.candidate_id for artifact in candidates},
                valid_ids,
            )
            if not has_errors(report_issues):
                return report
            last_error = "; ".join(issue.message for issue in report_issues)
        raise ValueError(f"specialized supervisor returned an invalid report twice: {last_error}")


def publish_specialized_outcome(
    outcome: SpecializedProductionOutcome,
    *,
    recipe: ProductionRecipe,
    version: str,
    repository: FactoryRepository,
    approved_by: str | None = None,
    notes: str = "",
) -> SpecializedReleaseBundle:
    if outcome.run.status != "completed" or not outcome.artifacts:
        raise ValueError("only completed specialized runs can be published")
    if outcome.run.request.source_pack is None:
        raise ValueError("specialized release requires a source pack")
    source_by_id = {
        source.id: source for source in outcome.run.request.source_pack.documents
    }
    used_sources = {
        source_id for artifact in outcome.artifacts for source_id in artifact.source_ids
    }
    unverified = sorted(
        source_id
        for source_id in used_sources
        if source_id not in source_by_id or not source_by_id[source_id].verified_by_human
    )
    if unverified:
        raise ValueError(f"specialized release uses unverified sources: {unverified}")
    if recipe.requires_human_approval and not approved_by:
        raise ValueError("psychology and cognition releases require an explicit human approver")
    bundle = SpecializedReleaseBundle(
        manifest=SpecializedReleaseManifest(
            release_id=f"specialized-release-{uuid4().hex}",
            version=version,
            recipe_id=recipe.id,
            artifact_kind=recipe.artifact_kind,
            source_pack_id=outcome.run.request.source_pack.id,
            artifact_digest=stable_digest(outcome.artifacts),
            approved_by=approved_by,
            notes=notes,
        ),
        artifacts=outcome.artifacts,
    )
    repository.save_specialized_release(bundle)
    return bundle
