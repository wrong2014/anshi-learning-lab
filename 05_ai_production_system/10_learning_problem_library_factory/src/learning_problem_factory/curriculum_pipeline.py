from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from .curriculum_models import (
    CurriculumEvidencePack,
    CurriculumKnowledgeNetwork,
    CurriculumOutline,
    CurriculumPipelineRequest,
    CurriculumRelationBatch,
    CurriculumSourceCatalog,
    KnowledgePointBatch,
    OutlineLevel,
)
from .curriculum_citation_repair import repair_point_citations
from .curriculum_relation_repair import sanitize_relation_batch
from .curriculum_prompts import (
    CURRICULUM_RUBRIC,
    curriculum_supervisor_prompts,
    graph_prompts,
    outline_prompts,
    point_prompts,
)
from .curriculum_validators import (
    build_coverage,
    validate_network,
    validate_outline,
    validate_points,
    validate_relations,
)
from .models import Decision, IssueSeverity, SupervisionReport, ValidationIssue, stable_digest
from .providers import JsonProvider
from .repository import FactoryRepository


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    provider_name: str
    value: BaseModel

    def supervisor_payload(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "provider_name": self.provider_name,
            "payload": self.value.model_dump(mode="json"),
        }


def _error(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, severity=IssueSeverity.ERROR, message=message)


def _raise_for_errors(stage: str, issues: list[ValidationIssue]) -> None:
    errors = [item for item in issues if item.severity == IssueSeverity.ERROR]
    if errors:
        details = "; ".join(f"{item.code}: {item.message}" for item in errors)
        raise ValueError(f"{stage} validation failed: {details}")


def _ensure_seed_preserved(seed: CurriculumOutline, produced: CurriculumOutline) -> None:
    produced_by_id = {node.id: node for node in produced.nodes}
    seed_ids = {node.id for node in seed.nodes}
    missing = sorted(node.id for node in seed.nodes if node.id not in produced_by_id)
    extra = sorted(node_id for node_id in produced_by_id if node_id not in seed_ids)
    changed = sorted(
        node.id
        for node in seed.nodes
        if node.id in produced_by_id and produced_by_id[node.id] != node
    )
    metadata_changed = produced.title != seed.title or produced.subjects != seed.subjects
    if missing or extra or changed or metadata_changed:
        raise ValueError(
            "outline agent altered frozen verified seed; "
            f"missing={missing}, extra={extra}, changed={changed}, "
            f"metadata_changed={metadata_changed}"
        )


class CurriculumPipeline:
    """Source-grounded, supervised curriculum knowledge-network pipeline."""

    def __init__(
        self,
        *,
        outline_agents: list[JsonProvider],
        knowledge_point_agents: list[JsonProvider],
        graph_agents: list[JsonProvider],
        supervisor: JsonProvider,
        checkpoint_dir: str | Path | None = None,
        repository: FactoryRepository | None = None,
        unit_workers: int = 2,
    ):
        for role, providers in (
            ("outline", outline_agents),
            ("knowledge_point", knowledge_point_agents),
            ("graph", graph_agents),
        ):
            if len(providers) < 2:
                raise ValueError(f"curriculum {role} stage requires at least two independent providers")
        self.outline_agents = outline_agents
        self.knowledge_point_agents = knowledge_point_agents
        self.graph_agents = graph_agents
        self.supervisor = supervisor
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self._active_checkpoint_dir: Path | None = None
        self.repository = repository
        self.unit_workers = max(1, unit_workers)

    def _checkpoint_path(self, name: str) -> Path | None:
        checkpoint_root = self._active_checkpoint_dir or self.checkpoint_dir
        if checkpoint_root is None:
            return None
        checkpoint_root.mkdir(parents=True, exist_ok=True)
        return checkpoint_root / f"{name}.json"

    def _load_checkpoint(self, name: str, model_type: type[T]) -> T | None:
        path = self._checkpoint_path(name)
        if path is None or not path.exists():
            return None
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))

    def _save_checkpoint(self, name: str, model: BaseModel) -> None:
        path = self._checkpoint_path(name)
        if path is not None:
            path.write_text(model.model_dump_json(indent=2), encoding="utf-8")

    def _produce_candidates(
        self,
        *,
        providers: list[JsonProvider],
        stage: str,
        unit_id: str,
        attempt: int,
        produce: Callable[[JsonProvider], T],
    ) -> tuple[list[_Candidate], list[str]]:
        candidates: list[_Candidate] = []
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=len(providers)) as pool:
            futures = {pool.submit(produce, provider): provider for provider in providers}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    value = future.result()
                except (RuntimeError, ValueError, ValidationError) as exc:
                    errors.append(f"provider {provider.name}: {exc}")
                    continue
                candidates.append(
                    _Candidate(
                        candidate_id=f"{stage}-{unit_id}-{provider.name}-attempt-{attempt}",
                        provider_name=provider.name,
                        value=value,
                    )
                )
        candidates.sort(key=lambda item: item.provider_name)
        return candidates, errors

    def _validate_report(
        self,
        report: SupervisionReport,
        candidate_ids: set[str],
        valid_ids: set[str],
        context: dict | None = None,
    ) -> list[str]:
        errors: list[str] = []
        score_by_dimension = {score.dimension: score.score for score in report.scores}
        if set(score_by_dimension) != set(CURRICULUM_RUBRIC):
            errors.append("supervisor rubric dimensions do not match curriculum rubric")
        else:
            expected_score = round(
                sum(score_by_dimension[name] * weight for name, weight in CURRICULUM_RUBRIC.items())
            )
            if report.final_score != expected_score:
                errors.append(
                    f"supervisor weighted score must be {expected_score}, got {report.final_score}"
                )
        if report.selected_candidate_id and report.selected_candidate_id not in candidate_ids:
            errors.append("supervisor selected an unknown candidate")
        if report.decision == Decision.PASS and report.selected_candidate_id not in valid_ids:
            errors.append("supervisor selected a candidate that failed deterministic validation")
        return errors

    def _supervise(
        self,
        *,
        stage: str,
        unit_id: str,
        candidates: list[_Candidate],
        issues_by_candidate: dict[str, list[ValidationIssue]],
        valid_ids: set[str],
        context: dict | None = None,
    ) -> SupervisionReport:
        system, user = curriculum_supervisor_prompts(
            stage=stage,
            unit_id=unit_id,
            candidates=[candidate.supervisor_payload() for candidate in candidates],
            issues_by_candidate=issues_by_candidate,
            context=context,
        )
        last_error = ""
        for _ in range(2):
            retry_user = user
            if last_error:
                retry_user += f"\n上次报告无效：{last_error}。请重新输出完整报告。"
            payload = self.supervisor.complete_json(system, retry_user)
            try:
                report = SupervisionReport.model_validate(payload)
            except ValidationError as exc:
                last_error = str(exc)
                continue
            report_errors = self._validate_report(
                report,
                {candidate.candidate_id for candidate in candidates},
                valid_ids,
            )
            if not report_errors:
                return report
            last_error = "; ".join(report_errors)
        raise ValueError(f"curriculum supervisor returned an invalid report twice: {last_error}")

    def _select_stage_candidate(
        self,
        *,
        run_id: str,
        stage: str,
        unit_id: str,
        providers: list[JsonProvider],
        max_reruns: int,
        produce: Callable[[JsonProvider, int, list[str]], T],
        validate: Callable[[T], list[ValidationIssue]],
        supervision_context: dict | None = None,
    ) -> T:
        feedback: list[str] = (
            self.repository.load_latest_curriculum_feedback(
                run_id=run_id,
                stage=stage,
                unit_id=unit_id,
            )
            if self.repository
            else []
        )
        valid_candidate_by_provider: dict[str, _Candidate] = {}
        issues_by_valid_candidate: dict[str, list[ValidationIssue]] = {}
        for attempt in range(1, max_reruns + 2):
            candidates, provider_errors = self._produce_candidates(
                providers=providers,
                stage=stage,
                unit_id=unit_id,
                attempt=attempt,
                produce=lambda provider: produce(provider, attempt, feedback),
            )
            issues_by_candidate: dict[str, list[ValidationIssue]] = {}
            for candidate in candidates:
                issues = validate(candidate.value)  # type: ignore[arg-type]
                issues_by_candidate[candidate.candidate_id] = issues
                if self.repository:
                    self.repository.record_curriculum_attempt(
                        run_id=run_id,
                        stage=stage,
                        unit_id=unit_id,
                        attempt_number=attempt,
                        provider_name=candidate.provider_name,
                        candidate_id=candidate.candidate_id,
                        payload=candidate.value,
                        issues=issues,
                    )
            current_valid_candidates = [
                candidate
                for candidate in candidates
                if not any(
                    issue.severity == IssueSeverity.ERROR
                    for issue in issues_by_candidate[candidate.candidate_id]
                )
            ]
            for candidate in current_valid_candidates:
                previous = valid_candidate_by_provider.get(candidate.provider_name)
                if previous:
                    issues_by_valid_candidate.pop(previous.candidate_id, None)
                valid_candidate_by_provider[candidate.provider_name] = candidate
                issues_by_valid_candidate[candidate.candidate_id] = issues_by_candidate[
                    candidate.candidate_id
                ]

            pooled_candidates = sorted(
                valid_candidate_by_provider.values(),
                key=lambda item: item.provider_name,
            )
            valid_ids = {candidate.candidate_id for candidate in pooled_candidates}
            if len(valid_ids) < 2 or not current_valid_candidates:
                feedback = provider_errors + [
                    f"{candidate_id}: {issue.message}"
                    for candidate_id, issues in issues_by_candidate.items()
                    for issue in issues
                    if issue.severity == IssueSeverity.ERROR
                ]
                if len(valid_ids) < 2:
                    feedback.append(
                        "stage requires at least two valid independent provider candidates; "
                        f"retained {len(valid_ids)}"
                    )
                continue

            report = self._supervise(
                stage=stage,
                unit_id=unit_id,
                candidates=pooled_candidates,
                issues_by_candidate=issues_by_valid_candidate,
                valid_ids=valid_ids,
                context=supervision_context,
            )
            if self.repository:
                self.repository.record_curriculum_review(
                    run_id=run_id,
                    stage=stage,
                    unit_id=unit_id,
                    attempt_number=attempt,
                    report=report,
                )
            if report.decision == Decision.HUMAN_REVIEW:
                raise ValueError(f"{stage}/{unit_id} requires human review")
            if report.decision == Decision.PASS:
                return next(
                    candidate.value  # type: ignore[return-value]
                    for candidate in pooled_candidates
                    if candidate.candidate_id == report.selected_candidate_id
                )
            feedback = report.rerun_instructions or [issue.message for issue in report.issues]
            if not feedback:
                feedback = ["Supervisor requested a rerun without details; improve all rubric dimensions."]
        raise ValueError(f"{stage}/{unit_id} exceeded the rerun limit")

    def run(
        self,
        request: CurriculumPipelineRequest,
        catalog: CurriculumSourceCatalog,
        seed: CurriculumOutline,
        evidence: CurriculumEvidencePack,
    ) -> CurriculumKnowledgeNetwork:
        input_digest = stable_digest(
            {
                "pipeline_version": "1.1",
                "request": request,
                "catalog": catalog,
                "seed": seed,
                "evidence": evidence,
            }
        )
        run_id = f"curriculum-{request.id}-{input_digest[:12]}"
        if self.checkpoint_dir:
            self._active_checkpoint_dir = self.checkpoint_dir / f"v1.1-{input_digest[:12]}"
        if self.repository:
            self.repository.save_curriculum_run(run_id, request, "running")
        try:
            _raise_for_errors("seed outline", validate_outline(seed, request, catalog))

            outline = self._load_checkpoint("outline", CurriculumOutline)
            if outline is None:
                def produce_outline(provider: JsonProvider, _attempt: int, feedback: list[str]) -> CurriculumOutline:
                    system, user = outline_prompts(request, catalog, seed, feedback)
                    return CurriculumOutline.model_validate(provider.complete_json(system, user))

                def validate_outline_candidate(candidate: CurriculumOutline) -> list[ValidationIssue]:
                    try:
                        _ensure_seed_preserved(seed, candidate)
                    except ValueError as exc:
                        return [_error("outline.seed_changed", str(exc))]
                    return validate_outline(candidate, request, catalog)

                outline = self._select_stage_candidate(
                    run_id=run_id,
                    stage="outline",
                    unit_id=request.id,
                    providers=self.outline_agents,
                    max_reruns=request.max_reruns,
                    produce=produce_outline,
                    validate=validate_outline_candidate,
                    supervision_context={
                        "request": request.model_dump(mode="json"),
                        "verified_seed_node_count": len(seed.nodes),
                    },
                )
                self._save_checkpoint("outline", outline)
            _ensure_seed_preserved(seed, outline)
            _raise_for_errors("outline", validate_outline(outline, request, catalog))

            tasks = sorted(
                (node for node in outline.nodes if node.level == OutlineLevel.STAGE_TASK),
                key=lambda item: item.id,
            )

            def process_task(task) -> KnowledgePointBatch:
                source_ids = {citation.source_id for citation in task.citations}
                ranges = [
                    (citation.page_start, citation.page_end)
                    for citation in task.citations
                    if citation.page_start is not None and citation.page_end is not None
                ]
                evidence_pages = [
                    page
                    for page in evidence.pages
                    if page.source_id in source_ids
                    and page.logical_page is not None
                    and any(start <= page.logical_page <= end for start, end in ranges)
                ]
                if not evidence_pages:
                    raise ValueError(f"no OCR evidence pages are available for task {task.id}")

                batch = self._load_checkpoint(f"point-{task.id}", KnowledgePointBatch)
                if batch is None:
                    def produce_points(
                        provider: JsonProvider,
                        _attempt: int,
                        feedback: list[str],
                    ) -> KnowledgePointBatch:
                        system, user = point_prompts(task, evidence_pages, feedback)
                        batch = KnowledgePointBatch.model_validate(
                            provider.complete_json(system, user)
                        )
                        repaired_batch, repairs = repair_point_citations(batch, evidence_pages)
                        if repairs and self.repository:
                            self.repository.record_curriculum_repairs(
                                run_id=run_id,
                                stage="knowledge-point",
                                unit_id=task.id,
                                attempt_number=_attempt,
                                provider_name=provider.name,
                                repairs=repairs,
                            )
                        return repaired_batch

                    task_outline = CurriculumOutline(
                        title=outline.title,
                        subjects=[task.subject],
                        nodes=[task],
                    )

                    def validate_point_candidate(candidate: KnowledgePointBatch) -> list[ValidationIssue]:
                        issues: list[ValidationIssue] = []
                        if candidate.outline_node_id != task.id:
                            issues.append(
                                _error(
                                    "points.task_escape",
                                    f"expected {task.id}, got {candidate.outline_node_id}",
                                )
                            )
                        issues.extend(validate_points(task_outline, candidate.points, evidence))
                        return issues

                    batch = self._select_stage_candidate(
                        run_id=run_id,
                        stage="knowledge-point",
                        unit_id=task.id,
                        providers=self.knowledge_point_agents,
                        max_reruns=request.max_reruns,
                        produce=produce_points,
                        validate=validate_point_candidate,
                        supervision_context={
                            "task": task.model_dump(mode="json"),
                            "evidence_pages": [
                                {
                                    "source_id": page.source_id,
                                    "logical_page": page.logical_page,
                                    "text": page.text,
                                }
                                for page in evidence_pages
                            ],
                        },
                    )
                    self._save_checkpoint(f"point-{task.id}", batch)
                if batch.outline_node_id != task.id:
                    raise ValueError(
                        f"knowledge-point checkpoint escaped task {task.id}: {batch.outline_node_id}"
                    )
                return batch

            batches: list[KnowledgePointBatch] = []
            with ThreadPoolExecutor(max_workers=min(self.unit_workers, len(tasks))) as pool:
                futures = {pool.submit(process_task, task): task for task in tasks}
                for future in as_completed(futures):
                    batches.append(future.result())
            batches.sort(key=lambda item: item.outline_node_id)

            points = [point for batch in batches for point in batch.points]
            _raise_for_errors("knowledge points", validate_points(outline, points, evidence))

            task_by_id = {
                node.id: node
                for node in outline.nodes
                if node.level == OutlineLevel.STAGE_TASK
            }
            batches_by_theme: dict[str, list[KnowledgePointBatch]] = {}
            for batch in batches:
                task = task_by_id[batch.outline_node_id]
                theme_id = task.parent_id or f"{task.subject.value}.unscoped"
                batches_by_theme.setdefault(theme_id, []).append(batch)

            def process_theme(item) -> tuple[str, CurriculumRelationBatch]:
                theme_id, theme_batches = item
                theme_points = [point for batch in theme_batches for point in batch.points]
                safe_theme_id = theme_id.replace("/", "-")
                theme_relations = self._load_checkpoint(
                    f"relations-{safe_theme_id}",
                    CurriculumRelationBatch,
                )
                if theme_relations is None:
                    def produce_theme_relations(
                        provider: JsonProvider,
                        _attempt: int,
                        feedback: list[str],
                    ) -> CurriculumRelationBatch:
                        system, user = graph_prompts(
                            outline,
                            theme_batches,
                            feedback,
                            scope_note=f"只建立主题 {theme_id} 内部的关系",
                        )
                        return CurriculumRelationBatch.model_validate(
                            provider.complete_json(system, user)
                        )

                    theme_relations = self._select_stage_candidate(
                        run_id=run_id,
                        stage="graph-theme",
                        unit_id=theme_id,
                        providers=self.graph_agents,
                        max_reruns=max(request.max_reruns, 5),
                        produce=produce_theme_relations,
                        validate=lambda candidate, scoped_points=theme_points: validate_relations(
                            scoped_points,
                            candidate.relations,
                        ),
                        supervision_context={
                            "scope": "within_theme",
                            "theme_id": theme_id,
                            "points": [
                                {
                                    "id": point.id,
                                    "name": point.name,
                                    "definition": point.definition,
                                }
                                for point in theme_points
                            ],
                        },
                    )
                    self._save_checkpoint(f"relations-{safe_theme_id}", theme_relations)
                return theme_id, theme_relations

            theme_results: list[tuple[str, CurriculumRelationBatch]] = []
            theme_items = sorted(batches_by_theme.items())
            with ThreadPoolExecutor(max_workers=min(self.unit_workers, len(theme_items))) as pool:
                futures = {pool.submit(process_theme, item): item[0] for item in theme_items}
                for future in as_completed(futures):
                    theme_results.append(future.result())
            theme_results.sort(key=lambda item: item[0])
            accepted_relations = [
                relation
                for _theme_id, relation_batch in theme_results
                for relation in relation_batch.relations
            ]

            cross_relations = self._load_checkpoint(
                "relations-cross-theme",
                CurriculumRelationBatch,
            )
            if cross_relations is None:
                batches_by_subject: dict[str, list[KnowledgePointBatch]] = {}
                for batch in batches:
                    subject = task_by_id[batch.outline_node_id].subject.value
                    batches_by_subject.setdefault(subject, []).append(batch)

                scope_specs: list[tuple[str, list[str], str]] = []
                for subject in ("math", "science", "physics", "chemistry"):
                    if subject in batches_by_subject:
                        scope_specs.append(
                            (
                                f"within-{subject}",
                                [subject],
                                f"只补充 {subject} 学科内部跨主题与跨学段关系",
                            )
                        )
                for left, right in (
                    ("science", "physics"),
                    ("science", "chemistry"),
                ):
                    if left in batches_by_subject and right in batches_by_subject:
                        emphasis = (
                            "；必须建立小学科学到初中物理的 bridges_to"
                            if (left, right) == ("science", "physics")
                            else "；必须建立小学科学到初中化学的 bridges_to"
                            if (left, right) == ("science", "chemistry")
                            else ""
                        )
                        scope_specs.append(
                            (
                                f"between-{left}-{right}",
                                [left, right],
                                f"只建立 {left} 与 {right} 之间的跨学科关系{emphasis}",
                            )
                        )

                def process_cross_scope(
                    spec: tuple[str, list[str], str],
                ) -> tuple[str, CurriculumRelationBatch]:
                    scope_id, subjects, scope_note = spec
                    scoped_batches = [
                        batch
                        for subject in subjects
                        for batch in batches_by_subject[subject]
                    ]
                    scoped_points = [
                        point for batch in scoped_batches for point in batch.points
                    ]
                    scoped_point_ids = {point.id for point in scoped_points}
                    existing_scoped = (
                        [
                            relation
                            for relation in accepted_relations
                            if relation.source_point_id in scoped_point_ids
                            and relation.target_point_id in scoped_point_ids
                        ]
                        if len(subjects) == 1
                        else []
                    )
                    checkpoint_name = f"relations-cross-{scope_id}"
                    result = self._load_checkpoint(
                        checkpoint_name,
                        CurriculumRelationBatch,
                    )
                    if result is not None:
                        return scope_id, result

                    def produce_scope_relations(
                        provider: JsonProvider,
                        _attempt: int,
                        feedback: list[str],
                    ) -> CurriculumRelationBatch:
                        system, user = graph_prompts(
                            outline,
                            scoped_batches,
                            feedback,
                            scope_note=scope_note,
                            existing_relations=existing_scoped,
                            compact_points=True,
                        )
                        batch = CurriculumRelationBatch.model_validate(
                            provider.complete_json(system, user)
                        )
                        sanitized, repairs = sanitize_relation_batch(
                            batch,
                            allowed_point_ids=scoped_point_ids,
                            existing_relations=existing_scoped,
                        )
                        if repairs and self.repository:
                            self.repository.record_curriculum_repairs(
                                run_id=run_id,
                                stage="graph-cross-scope",
                                unit_id=scope_id,
                                attempt_number=_attempt,
                                provider_name=provider.name,
                                repairs=repairs,
                            )
                        return sanitized

                    result = self._select_stage_candidate(
                        run_id=run_id,
                        stage="graph-cross-scope",
                        unit_id=scope_id,
                        providers=self.graph_agents,
                        max_reruns=max(request.max_reruns, 5),
                        produce=produce_scope_relations,
                        validate=lambda candidate: validate_relations(
                            scoped_points,
                            candidate.relations,
                        ),
                        supervision_context={
                            "scope": scope_id,
                            "subjects": subjects,
                            "existing_relation_count": len(existing_scoped),
                            "points": [
                                {
                                    "id": point.id,
                                    "subject": point.subject.value,
                                    "name": point.name,
                                    "outline_node_id": point.outline_node_id,
                                }
                                for point in scoped_points
                            ],
                        },
                    )
                    self._save_checkpoint(checkpoint_name, result)
                    return scope_id, result

                cross_scope_results: list[tuple[str, CurriculumRelationBatch]] = []
                with ThreadPoolExecutor(
                    max_workers=min(self.unit_workers, len(scope_specs))
                ) as pool:
                    futures = {
                        pool.submit(process_cross_scope, spec): spec[0]
                        for spec in scope_specs
                    }
                    for future in as_completed(futures):
                        cross_scope_results.append(future.result())
                cross_scope_results.sort(key=lambda item: item[0])
                cross_relations = CurriculumRelationBatch(
                    relations=[
                        relation
                        for _scope_id, relation_batch in cross_scope_results
                        for relation in relation_batch.relations
                    ]
                )
                self._save_checkpoint("relations-cross-theme", cross_relations)
            all_relations = accepted_relations + cross_relations.relations
            _raise_for_errors("knowledge graph", validate_relations(points, all_relations))

            network = CurriculumKnowledgeNetwork(
                outline=outline,
                points=points,
                relations=all_relations,
                coverage=build_coverage(outline, points),
            )
            _raise_for_errors(
                "curriculum network",
                validate_network(network, request, catalog, evidence),
            )
            if self.repository:
                self.repository.save_curriculum_run(run_id, request, "completed", network=network)
            return network
        except Exception as exc:
            if self.repository:
                self.repository.save_curriculum_run(run_id, request, "failed", error=str(exc))
            raise
