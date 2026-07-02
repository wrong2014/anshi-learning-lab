from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import (
    ArtifactKind,
    ExecutionPlan,
    Observer,
    ProductionRequest,
    ReviewState,
    SourceCitation,
    StrictModel,
    Subject,
    SupervisionReport,
    utc_now,
)


class StageFeature(StrictModel):
    grade_min: int = Field(ge=1, le=9)
    grade_max: int = Field(ge=1, le=9)
    expectation: str = Field(min_length=8)
    typical_transition: str = Field(min_length=8)

    @model_validator(mode="after")
    def validate_range(self) -> "StageFeature":
        if self.grade_min > self.grade_max:
            raise ValueError("grade_min cannot exceed grade_max")
        return self


class ThinkingObservableSignal(StrictModel):
    observer: Observer
    behavior: str = Field(min_length=8)
    context: str = Field(min_length=5)
    likely_breakpoint: str = Field(min_length=8)


class MathThinkingProfile(StrictModel):
    kind: Literal["math"] = "math"
    mathematical_manifestations: list[str] = Field(min_length=1)
    related_knowledge_areas: list[str] = Field(min_length=1)


class PhysicsThinkingProfile(StrictModel):
    kind: Literal["physics"] = "physics"
    relation_to_model_thinking: str = Field(min_length=8)
    boundary_with_mathematics: str = Field(min_length=8)
    physical_manifestations: list[str] = Field(min_length=1)


class ChemistryThinkingProfile(StrictModel):
    kind: Literal["chemistry"] = "chemistry"
    chemical_uniqueness: str = Field(min_length=8)
    distinction_from_physics: str = Field(min_length=8)
    chemical_manifestations: list[str] = Field(min_length=1)


class CoreThinkingDimension(StrictModel):
    id: str
    subject: Subject
    name: str
    academic_definition: str = Field(min_length=12)
    plain_essence: str = Field(min_length=8)
    observable_deficits: list[ThinkingObservableSignal] = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    supports: list[str] = Field(default_factory=list)
    stage_features: list[StageFeature] = Field(min_length=1)
    development_path: list[str] = Field(min_length=1)
    profile: Annotated[
        MathThinkingProfile | PhysicsThinkingProfile | ChemistryThinkingProfile,
        Field(discriminator="kind"),
    ]
    citations: list[SourceCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def subject_matches_profile(self) -> "CoreThinkingDimension":
        expected = {
            Subject.MATH: "math",
            Subject.PHYSICS: "physics",
            Subject.CHEMISTRY: "chemistry",
        }.get(self.subject)
        if expected is None:
            raise ValueError("core thinking dimensions only support math, physics and chemistry")
        if self.profile.kind != expected:
            raise ValueError(f"subject {self.subject.value} requires {expected} profile")
        return self


class CoreThinkingArtifact(StrictModel):
    artifact_kind: Literal["core_thinking"] = "core_thinking"
    schema_version: str = "1.0"
    recipe_id: str
    request_id: str
    batch_id: str
    candidate_id: str
    provider_name: str
    dimensions: list[CoreThinkingDimension] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class SubjectLearningScenario(StrictModel):
    subject: Literal["math", "physics", "chemistry"]
    manifestation: str = Field(min_length=8)


class SeverityBoundary(StrictModel):
    normal_range: str = Field(min_length=8)
    support_needed: str = Field(min_length=8)
    professional_help: str = Field(min_length=8)


class PsychologyDimension(StrictModel):
    id: str
    layer: Literal["psychology", "cognition", "motivation"]
    name: str
    theory_name: str
    academic_definition: str = Field(min_length=12)
    theory_citations: list[SourceCitation] = Field(min_length=1)
    subject_scenarios: list[SubjectLearningScenario] = Field(min_length=3)
    parent_signals: list[str] = Field(min_length=3)
    learner_signals: list[str] = Field(min_length=3)
    achievement_mechanism: str = Field(min_length=12)
    severity: SeverityBoundary
    may_lead_to: list[str] = Field(default_factory=list)
    may_be_caused_by: list[str] = Field(default_factory=list)
    ai_support_scope: list[str] = Field(min_length=1)
    referral_conditions: list[str] = Field(min_length=1)
    citations: list[SourceCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def require_all_subject_scenarios(self) -> "PsychologyDimension":
        subjects = {item.subject for item in self.subject_scenarios}
        if subjects != {"math", "physics", "chemistry"}:
            raise ValueError("psychology dimensions require math, physics and chemistry scenarios")
        return self


class PsychologyArtifact(StrictModel):
    artifact_kind: Literal["psychology_cognition"] = "psychology_cognition"
    schema_version: str = "1.0"
    recipe_id: str
    request_id: str
    batch_id: str
    candidate_id: str
    provider_name: str
    dimensions: list[PsychologyDimension] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


SpecializedArtifact = Annotated[
    CoreThinkingArtifact | PsychologyArtifact,
    Field(discriminator="artifact_kind"),
]


class SpecializedProductionRun(StrictModel):
    id: str
    request: ProductionRequest
    status: Literal["created", "planned", "running", "needs_human", "completed", "failed"]
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    plan: ExecutionPlan | None = None
    accepted_candidate_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class SpecializedProductionOutcome(StrictModel):
    run: SpecializedProductionRun
    artifacts: list[SpecializedArtifact] = Field(default_factory=list)
    reports: list[SupervisionReport] = Field(default_factory=list)


class SpecializedReleaseManifest(StrictModel):
    release_id: str
    version: str
    recipe_id: str
    artifact_kind: ArtifactKind
    created_at: datetime = Field(default_factory=utc_now)
    state: ReviewState = ReviewState.PUBLISHED
    source_pack_id: str
    artifact_digest: str
    approved_by: str | None = None
    notes: str = ""


class SpecializedReleaseBundle(StrictModel):
    manifest: SpecializedReleaseManifest
    artifacts: list[SpecializedArtifact] = Field(min_length=1)
