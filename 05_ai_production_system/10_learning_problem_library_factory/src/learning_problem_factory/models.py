from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


def utc_now() -> datetime:
    return datetime.now(UTC)


def stable_digest(payload: Any) -> str:
    if isinstance(payload, BaseModel):
        value = payload.model_dump(mode="json", exclude_none=True)
    else:
        value = payload
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: item.model_dump(mode="json", exclude_none=True)
        if isinstance(item, BaseModel)
        else str(item),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Subject(str, Enum):
    MATH = "math"
    SCIENCE = "science"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    CROSS_SUBJECT = "cross_subject"


class ArtifactKind(str, Enum):
    KNOWLEDGE_GRAPH = "knowledge_graph"
    CORE_THINKING = "core_thinking"
    PSYCHOLOGY_COGNITION = "psychology_cognition"


class SourceKind(str, Enum):
    CURRICULUM_STANDARD = "curriculum_standard"
    TEXTBOOK = "textbook"
    ACADEMIC_PAPER = "academic_paper"
    PROFESSIONAL_GUIDELINE = "professional_guideline"
    EXPERT_NOTE = "expert_note"


class EvidenceMode(str, Enum):
    MODEL_DISTILLATION = "model_distillation"
    SOURCE_GROUNDED = "source_grounded"


class ReviewState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class Decision(str, Enum):
    PASS = "pass"
    PARTIAL_RERUN = "partial_rerun"
    FULL_RERUN = "full_rerun"
    HUMAN_REVIEW = "human_review"


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RelationType(str, Enum):
    PREREQUISITE = "prerequisite"
    SUPPORTS = "supports"
    EXTENDS = "extends"
    CROSS_MODULE = "cross_module"
    RELATED = "related"


class Observer(str, Enum):
    PARENT = "parent"
    TEACHER = "teacher"
    LEARNER = "learner"


class EvidenceDirection(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    UNCERTAIN = "uncertain"


class SourceDocument(StrictModel):
    id: str
    title: str
    kind: SourceKind
    publisher_or_author: str
    edition_or_year: str
    locator: str
    content: str = Field(min_length=20)
    verified_by_human: bool = False

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("source id must be a stable lowercase identifier")
        return value


class SourceCitation(StrictModel):
    source_id: str
    locator: str
    claim: str = Field(min_length=3)


class SourcePack(StrictModel):
    id: str
    title: str
    scope_note: str
    documents: list[SourceDocument] = Field(min_length=1)

    @model_validator(mode="after")
    def ensure_unique_source_ids(self) -> "SourcePack":
        ids = [item.id for item in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("source document ids must be unique")
        return self


class ProductionScope(StrictModel):
    subject: Subject
    grade_min: int = Field(ge=1, le=12)
    grade_max: int = Field(ge=1, le=12)
    modules: list[str] = Field(min_length=1)
    granularity: Literal["overview", "module", "knowledge_point"] = "knowledge_point"

    @model_validator(mode="after")
    def validate_grade_range(self) -> "ProductionScope":
        if self.grade_min > self.grade_max:
            raise ValueError("grade_min cannot exceed grade_max")
        return self


class ProductionRequest(StrictModel):
    id: str = Field(default_factory=lambda: f"request-{uuid4().hex[:12]}")
    recipe_id: str
    evidence_mode: EvidenceMode = EvidenceMode.MODEL_DISTILLATION
    source_pack: SourcePack | None = None
    scope: ProductionScope
    requested_by: str = "local"
    max_reruns: int = Field(default=2, ge=0, le=5)

    @model_validator(mode="after")
    def validate_evidence_mode(self) -> "ProductionRequest":
        if self.evidence_mode == EvidenceMode.SOURCE_GROUNDED and self.source_pack is None:
            raise ValueError("source_grounded production requires a source_pack")
        return self


class PlanBatch(StrictModel):
    id: str
    title: str
    module_names: list[str] = Field(min_length=1, max_length=3)
    expected_node_count: int = Field(ge=1, le=200)
    depends_on: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class ExecutionPlan(StrictModel):
    request_id: str
    rationale: str
    batches: list[PlanBatch] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ExecutionPlan":
        ids = [batch.id for batch in self.batches]
        if len(ids) != len(set(ids)):
            raise ValueError("batch ids must be unique")
        known = set(ids)
        for batch in self.batches:
            missing = set(batch.depends_on) - known
            if missing:
                raise ValueError(f"batch {batch.id} has unknown dependencies: {sorted(missing)}")
            if batch.id in batch.depends_on:
                raise ValueError(f"batch {batch.id} cannot depend on itself")
        return self


class ObservableSignal(StrictModel):
    id: str
    observer: Observer
    behavior: str = Field(min_length=5)
    context: str = Field(min_length=3)
    non_example: str = Field(min_length=3)


class ProbeOptionDraft(StrictModel):
    id: str
    label: str
    direction: EvidenceDirection
    evidence_tag: str
    strength: float = Field(ge=0, le=1)


class ProbeBlueprint(StrictModel):
    audience: Observer
    stem: str = Field(min_length=8)
    options: list[ProbeOptionDraft] = Field(min_length=2, max_length=6)
    evidence_needed: list[str] = Field(min_length=1)


class KnowledgeNode(StrictModel):
    id: str
    subject: Subject
    grade_min: int = Field(ge=1, le=12)
    grade_max: int = Field(ge=1, le=12)
    module: str
    name: str
    definition: str = Field(min_length=10)
    core_thinking: list[str] = Field(min_length=1)
    citations: list[SourceCitation] = Field(default_factory=list)


class KnowledgeRelation(StrictModel):
    source_node_id: str
    target_node_id: str
    relation_type: RelationType
    rationale: str = Field(min_length=5)
    citations: list[SourceCitation] = Field(default_factory=list)


class LearningBlock(StrictModel):
    id: str
    node_id: str
    title: str
    description: str = Field(min_length=8)
    essence: str = Field(min_length=8)
    block_type: str
    observable_signals: list[ObservableSignal] = Field(min_length=1)
    probe_blueprints: list[ProbeBlueprint] = Field(min_length=1)
    citations: list[SourceCitation] = Field(default_factory=list)


class KnowledgeArtifact(StrictModel):
    schema_version: str = "1.0"
    recipe_id: str
    request_id: str
    batch_id: str
    candidate_id: str
    provider_name: str
    nodes: list[KnowledgeNode] = Field(min_length=1)
    relations: list[KnowledgeRelation] = Field(default_factory=list)
    learning_blocks: list[LearningBlock] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)


class ValidationIssue(StrictModel):
    code: str
    severity: IssueSeverity
    message: str
    path: str | None = None


class RubricScore(StrictModel):
    dimension: str
    score: int = Field(ge=0, le=100)
    rationale: str


class SupervisionReport(StrictModel):
    selected_candidate_id: str | None = None
    scores: list[RubricScore] = Field(min_length=1)
    issues: list[ValidationIssue] = Field(default_factory=list)
    final_score: int = Field(ge=0, le=100)
    decision: Decision
    rerun_instructions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_score_policy(self) -> "SupervisionReport":
        expected = (
            Decision.PASS
            if self.final_score >= 90
            else Decision.PARTIAL_RERUN
            if self.final_score >= 70
            else Decision.FULL_RERUN
        )
        if self.decision != Decision.HUMAN_REVIEW and self.decision != expected:
            raise ValueError(f"decision {self.decision} does not match score policy {expected}")
        if self.decision == Decision.PASS and not self.selected_candidate_id:
            raise ValueError("a passing report must select a candidate")
        return self


class DiagnosticProbeOption(StrictModel):
    id: str
    label: str
    direction: EvidenceDirection
    evidence_tag: str
    strength: float = Field(ge=0, le=1)


class DiagnosticProbe(StrictModel):
    id: str
    artifact_candidate_id: str
    subject: Subject
    grade_min: int
    grade_max: int
    module: str
    node_id: str
    learning_block_id: str
    audience: Observer
    stem: str
    options: list[DiagnosticProbeOption]
    evidence_needed: list[str]
    source_citations: list[SourceCitation]


class ReleaseManifest(StrictModel):
    release_id: str
    version: str
    recipe_id: str
    evidence_mode: EvidenceMode
    created_at: datetime = Field(default_factory=utc_now)
    state: ReviewState
    source_pack_id: str | None = None
    artifact_digest: str
    probe_digest: str
    approved_by: str | None = None
    notes: str = ""


class ReleaseBundle(StrictModel):
    manifest: ReleaseManifest
    artifacts: list[KnowledgeArtifact] = Field(min_length=1)
    probes: list[DiagnosticProbe] = Field(min_length=1)


class ProviderConfig(StrictModel):
    name: str
    role: Literal[
        "planner",
        "executor",
        "supervisor",
        "outline",
        "knowledge_point",
        "graph",
    ]
    model: str
    base_url: str
    api_key_env: str
    enabled: bool = True
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=6000, ge=256, le=32000)
    timeout_seconds: int = Field(default=90, ge=5, le=600)
    thinking: Literal["enabled", "disabled"] = "disabled"
    reasoning_effort: Literal["high", "max"] | None = None


class ProviderSet(StrictModel):
    providers: list[ProviderConfig] = Field(min_length=3)

    def by_role(self, role: str) -> list[ProviderConfig]:
        return [item for item in self.providers if item.enabled and item.role == role]

    @model_validator(mode="after")
    def ensure_required_roles(self) -> "ProviderSet":
        if len(self.by_role("planner")) != 1:
            raise ValueError("exactly one enabled planner is required")
        if len(self.by_role("supervisor")) != 1:
            raise ValueError("exactly one enabled supervisor is required")
        if len(self.by_role("executor")) < 2:
            raise ValueError("at least two enabled executors are required for independent candidates")
        return self


class CurriculumProviderSet(StrictModel):
    """Provider roles for the three-stage curriculum production pipeline."""

    providers: list[ProviderConfig] = Field(min_length=3)

    def by_role(self, role: str) -> list[ProviderConfig]:
        return [item for item in self.providers if item.enabled and item.role == role]

    @model_validator(mode="after")
    def ensure_curriculum_roles(self) -> "CurriculumProviderSet":
        for role in ("outline", "knowledge_point", "graph"):
            if len(self.by_role(role)) < 2:
                raise ValueError(f"at least two enabled {role} providers are required")
        if len(self.by_role("supervisor")) != 1:
            raise ValueError("exactly one enabled supervisor provider is required")
        return self


class RubricDimension(StrictModel):
    name: str
    weight: float = Field(gt=0, le=1)
    instructions: str


class ProductionRecipe(StrictModel):
    id: str
    name: str
    artifact_kind: ArtifactKind
    subject: Subject
    planner_instructions: str
    executor_instructions: str
    rubric: list[RubricDimension] = Field(min_length=1)
    high_risk: bool = False
    requires_human_approval: bool = False

    @model_validator(mode="after")
    def validate_rubric_weights(self) -> "ProductionRecipe":
        total = sum(item.weight for item in self.rubric)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"rubric weights must add up to 1.0, got {total}")
        return self


class ProductionRun(StrictModel):
    id: str = Field(default_factory=lambda: f"run-{uuid4().hex}")
    request: ProductionRequest
    status: Literal["created", "planned", "running", "needs_human", "completed", "failed"] = "created"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    plan: ExecutionPlan | None = None
    accepted_candidate_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class ProductionOutcome(StrictModel):
    run: ProductionRun
    artifacts: list[KnowledgeArtifact] = Field(default_factory=list)
    reports: list[SupervisionReport] = Field(default_factory=list)
