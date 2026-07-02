from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

from pydantic import ValidationError

from .compiler import compile_diagnostic_probes
from .models import (
    ArtifactKind,
    Decision,
    EvidenceMode,
    ExecutionPlan,
    IssueSeverity,
    KnowledgeArtifact,
    ProductionOutcome,
    ProductionRecipe,
    ProductionRequest,
    ProductionRun,
    ReleaseBundle,
    ReleaseManifest,
    ReviewState,
    SupervisionReport,
    ValidationIssue,
    stable_digest,
)
from .prompts import executor_prompts, planner_prompts, supervisor_prompts
from .providers import JsonProvider
from .repository import FactoryRepository
from .validators import (
    has_errors,
    topological_batches,
    validate_artifact,
    validate_plan,
    validate_supervision_report,
)


class ProductionFactory:
    def __init__(
        self,
        *,
        planner: JsonProvider,
        executors: list[JsonProvider],
        supervisor: JsonProvider,
        recipe: ProductionRecipe,
        repository: FactoryRepository,
    ):
        if not executors:
            raise ValueError("at least one executor provider is required")
        self.planner = planner
        self.executors = executors
        self.supervisor = supervisor
        self.recipe = recipe
        self.repository = repository

    def run(self, request: ProductionRequest) -> ProductionOutcome:
        if self.recipe.artifact_kind != ArtifactKind.KNOWLEDGE_GRAPH:
            raise ValueError(
                "core thinking and psychology recipes must use SpecializedMaterialFactory"
            )
        if request.recipe_id != self.recipe.id:
            raise ValueError("production request recipe does not match factory recipe")
        if self.recipe.subject.value != "cross_subject" and request.scope.subject != self.recipe.subject:
            raise ValueError("production request subject does not match recipe subject")
        if (
            self.recipe.artifact_kind == ArtifactKind.KNOWLEDGE_GRAPH
            and request.evidence_mode == EvidenceMode.MODEL_DISTILLATION
        ):
            raise ValueError(
                "knowledge graph scope cannot use model_distillation; run the official curriculum pipeline first"
            )

        run = ProductionRun(request=request)
        self.repository.save_run(run)
        reports: list[SupervisionReport] = []
        accepted: list[KnowledgeArtifact] = []

        try:
            system_prompt, user_prompt = planner_prompts(request, self.recipe)
            plan = ExecutionPlan.model_validate(self.planner.complete_json(system_prompt, user_prompt))
            plan_issues = validate_plan(plan, request)
            if has_errors(plan_issues):
                details = "; ".join(issue.message for issue in plan_issues)
                raise ValueError(f"planner produced an invalid plan: {details}")
            run.plan = plan
            run.status = "planned"
            self.repository.save_run(run)

            batch_by_id = {batch.id: batch for batch in plan.batches}
            run.status = "running"
            self.repository.save_run(run)

            for batch_id in topological_batches(plan):
                batch = batch_by_id[batch_id]
                feedback: list[str] = []
                accepted_artifact: KnowledgeArtifact | None = None

                for attempt in range(1, request.max_reruns + 2):
                    candidates, provider_errors = self._execute_candidates(request, batch, attempt, feedback)
                    issues_by_candidate: dict[str, list[ValidationIssue]] = {}
                    for artifact in candidates:
                        issues = validate_artifact(artifact, request)
                        issues_by_candidate[artifact.candidate_id] = issues
                        self.repository.record_attempt(run.id, batch.id, attempt, artifact, issues)

                    valid_ids = {
                        candidate.candidate_id
                        for candidate in candidates
                        if not has_errors(issues_by_candidate[candidate.candidate_id])
                    }
                    if not valid_ids:
                        feedback = provider_errors + [
                            f"{candidate_id}: {issue.message}"
                            for candidate_id, issues in issues_by_candidate.items()
                            for issue in issues
                            if issue.severity == IssueSeverity.ERROR
                        ]
                        continue

                    report = self._supervise(request, batch, candidates, issues_by_candidate, valid_ids)
                    reports.append(report)
                    self.repository.record_review(run.id, batch.id, attempt, report)

                    if report.decision == Decision.HUMAN_REVIEW:
                        run.status = "needs_human"
                        self.repository.save_run(run)
                        return ProductionOutcome(run=run, artifacts=accepted, reports=reports)

                    if report.decision == Decision.PASS:
                        if report.selected_candidate_id not in valid_ids:
                            feedback = [
                                "监督层选择了未通过硬校验或不存在的候选，请只选择通过硬校验的 candidate_id。"
                            ]
                            continue
                        accepted_artifact = next(
                            item for item in candidates if item.candidate_id == report.selected_candidate_id
                        )
                        break

                    feedback = list(report.rerun_instructions)
                    if not feedback:
                        feedback = [issue.message for issue in report.issues]

                if accepted_artifact is None:
                    run.status = "needs_human"
                    run.error = f"batch {batch.id} exceeded the rerun limit"
                    self.repository.save_run(run)
                    return ProductionOutcome(run=run, artifacts=accepted, reports=reports)

                accepted.append(accepted_artifact)
                run.accepted_candidate_ids.append(accepted_artifact.candidate_id)
                self.repository.save_run(run)

            run.status = "completed"
            self.repository.save_run(run)
            return ProductionOutcome(run=run, artifacts=accepted, reports=reports)
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            self.repository.save_run(run)
            raise

    def _execute_candidates(
        self,
        request: ProductionRequest,
        batch,
        attempt: int,
        feedback: list[str],
    ) -> tuple[list[KnowledgeArtifact], list[str]]:
        candidates: list[KnowledgeArtifact] = []
        errors: list[str] = []

        def call(provider: JsonProvider) -> KnowledgeArtifact:
            system_prompt, user_prompt = executor_prompts(
                request, self.recipe, batch, provider.name, attempt, feedback
            )
            payload = provider.complete_json(system_prompt, user_prompt)
            artifact = KnowledgeArtifact.model_validate(payload)
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
        candidates.sort(key=lambda item: item.provider_name)
        return candidates, errors

    def _supervise(
        self,
        request: ProductionRequest,
        batch,
        candidates: list[KnowledgeArtifact],
        issues_by_candidate: dict[str, list[ValidationIssue]],
        valid_candidate_ids: set[str],
    ) -> SupervisionReport:
        system_prompt, user_prompt = supervisor_prompts(
            request, self.recipe, batch, candidates, issues_by_candidate
        )
        last_error = ""
        for _ in range(2):
            retry_prompt = user_prompt
            if last_error:
                retry_prompt += f"\n\n上一次审核报告未通过结构校验：{last_error}。请重新计算并输出完整报告。"
            payload = self.supervisor.complete_json(system_prompt, retry_prompt)
            try:
                report = SupervisionReport.model_validate(payload)
            except ValidationError as exc:
                last_error = str(exc)
                continue
            report_issues = validate_supervision_report(
                report,
                self.recipe,
                {item.candidate_id for item in candidates},
                valid_candidate_ids,
            )
            if not has_errors(report_issues):
                return report
            last_error = "; ".join(item.message for item in report_issues)
        raise ValueError(f"supervisor produced an invalid report twice: {last_error}")


def publish_outcome(
    outcome: ProductionOutcome,
    *,
    recipe: ProductionRecipe,
    version: str,
    repository: FactoryRepository,
    approved_by: str | None = None,
    notes: str = "",
) -> ReleaseBundle:
    if recipe.artifact_kind != ArtifactKind.KNOWLEDGE_GRAPH:
        raise ValueError("specialized material releases must use publish_specialized_outcome")
    if outcome.run.status != "completed":
        raise ValueError("only a completed production run can be published")
    if not outcome.artifacts:
        raise ValueError("a release must contain at least one artifact")
    if recipe.requires_human_approval and not approved_by:
        raise ValueError("this high-risk recipe requires an explicit human approver")
    if (
        recipe.artifact_kind == ArtifactKind.KNOWLEDGE_GRAPH
        and outcome.run.request.evidence_mode == EvidenceMode.MODEL_DISTILLATION
    ):
        raise ValueError("model-distilled knowledge graphs cannot be published")

    if outcome.run.request.evidence_mode == EvidenceMode.SOURCE_GROUNDED:
        if outcome.run.request.source_pack is None:
            raise ValueError("source_grounded release requires a source_pack")
        used_source_ids = {source_id for artifact in outcome.artifacts for source_id in artifact.source_ids}
        source_by_id = {item.id: item for item in outcome.run.request.source_pack.documents}
        unverified_sources = sorted(
            source_id
            for source_id in used_source_ids
            if source_id not in source_by_id or not source_by_id[source_id].verified_by_human
        )
        if unverified_sources:
            raise ValueError(f"release uses sources that have not been human-verified: {unverified_sources}")

    probes = compile_diagnostic_probes(outcome.artifacts)
    manifest = ReleaseManifest(
        release_id=f"release-{uuid4().hex}",
        version=version,
        recipe_id=recipe.id,
        evidence_mode=outcome.run.request.evidence_mode,
        state=ReviewState.PUBLISHED,
        source_pack_id=outcome.run.request.source_pack.id if outcome.run.request.source_pack else None,
        artifact_digest=stable_digest(outcome.artifacts),
        probe_digest=stable_digest(probes),
        approved_by=approved_by,
        notes=notes,
    )
    bundle = ReleaseBundle(manifest=manifest, artifacts=outcome.artifacts, probes=probes)
    repository.save_release(bundle)
    return bundle
