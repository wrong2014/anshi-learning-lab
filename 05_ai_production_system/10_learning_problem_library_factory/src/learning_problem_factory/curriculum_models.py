from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal
from datetime import datetime

from pydantic import Field, model_validator

from .models import ID_PATTERN, ReviewState, StrictModel, Subject, utc_now


class OutlineLevel(str, Enum):
    COURSE = "course"
    DOMAIN = "domain"
    THEME = "theme"
    STAGE_TASK = "stage_task"


class CoverageState(str, Enum):
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"


class CurriculumSource(StrictModel):
    id: str
    title: str
    subject: Subject
    authority: str
    edition: str
    official_url: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_count: int = Field(ge=1)
    logical_page_offset: int = Field(default=7, ge=0)
    text_layer: Literal["native", "ocr_required"]
    locally_verified: bool = False


class CurriculumSourceCatalog(StrictModel):
    schema_version: str = "1.0"
    notice_url: str
    sources: list[CurriculumSource] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sources(self) -> "CurriculumSourceCatalog":
        ids = [item.id for item in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("curriculum source ids must be unique")
        return self


class CurriculumCitation(StrictModel):
    source_id: str
    locator: str
    excerpt: str = Field(min_length=2)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_pages(self) -> "CurriculumCitation":
        if (self.page_start is None) != (self.page_end is None):
            raise ValueError("page_start and page_end must be set together")
        if self.page_start is not None and self.page_start > self.page_end:
            raise ValueError("page_start cannot exceed page_end")
        return self


class CurriculumEvidencePage(StrictModel):
    source_id: str
    pdf_page: int = Field(ge=1)
    logical_page: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CurriculumEvidencePack(StrictModel):
    schema_version: str = "1.0"
    ocr_engine: str
    pages: list[CurriculumEvidencePage] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_pages(self) -> "CurriculumEvidencePack":
        keys = [(page.source_id, page.pdf_page) for page in self.pages]
        if len(keys) != len(set(keys)):
            raise ValueError("evidence pages must be unique by source_id and pdf_page")
        return self


class OutlineNode(StrictModel):
    id: str
    parent_id: str | None = None
    level: OutlineLevel
    subject: Subject
    title: str
    grade_min: int = Field(ge=1, le=9)
    grade_max: int = Field(ge=1, le=9)
    expected_min_points: int = Field(default=1, ge=0, le=200)
    citations: list[CurriculumCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_node(self) -> "OutlineNode":
        if not ID_PATTERN.fullmatch(self.id):
            raise ValueError("outline node id must be stable lowercase ASCII")
        if self.parent_id is not None and not ID_PATTERN.fullmatch(self.parent_id):
            raise ValueError("outline parent id must be stable lowercase ASCII")
        if self.grade_min > self.grade_max:
            raise ValueError("grade_min cannot exceed grade_max")
        if self.level == OutlineLevel.STAGE_TASK and self.expected_min_points < 1:
            raise ValueError("stage tasks must expect at least one knowledge point")
        return self


class CurriculumOutline(StrictModel):
    schema_version: str = "1.0"
    title: str
    subjects: list[Subject] = Field(min_length=1)
    nodes: list[OutlineNode] = Field(min_length=1)


class MathKnowledgeProfile(StrictModel):
    kind: Literal["math"] = "math"
    representations: list[str] = Field(min_length=1)
    key_procedures: list[str] = Field(default_factory=list)
    application_contexts: list[str] = Field(default_factory=list)


class ScienceKnowledgeProfile(StrictModel):
    kind: Literal["science"] = "science"
    inquiry_practices: list[str] = Field(min_length=1)
    crosscutting_concepts: list[
        Literal["物质与能量", "结构与功能", "系统与模型", "稳定与变化"]
    ] = Field(default_factory=list)


class PhysicsFormula(StrictModel):
    expression: str
    quantity_meanings: str = Field(min_length=3)
    conditions: str = Field(min_length=3)


class PhysicsKnowledgeProfile(StrictModel):
    kind: Literal["physics"] = "physics"
    concept_definition: str = Field(min_length=8)
    formulae: list[PhysicsFormula] = Field(default_factory=list)
    concept_formula_links: list[str] = Field(default_factory=list)
    physical_contexts: list[str] = Field(min_length=1)
    cross_module_dependencies: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def formulae_require_links(self) -> "PhysicsKnowledgeProfile":
        if self.formulae and not self.concept_formula_links:
            raise ValueError("physics formulae require concept_formula_links")
        return self


class ChemistryKnowledgeProfile(StrictModel):
    kind: Literal["chemistry"] = "chemistry"
    knowledge_type: Literal["memory", "reasoning", "mixed"]
    macro_micro_symbolic: bool
    representation_links: list[str] = Field(default_factory=list)
    experiment_contexts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def macro_micro_requires_links(self) -> "ChemistryKnowledgeProfile":
        if self.macro_micro_symbolic and not self.representation_links:
            raise ValueError("macro/micro/symbolic knowledge requires representation_links")
        return self


class KnowledgePoint(StrictModel):
    id: str
    outline_node_id: str
    subject: Subject
    grade_min: int = Field(ge=1, le=9)
    grade_max: int = Field(ge=1, le=9)
    name: str
    definition: str = Field(min_length=8)
    learning_expectation: str = Field(min_length=8)
    concept_kind: Literal["concept", "procedure", "representation", "practice", "application"]
    core_thinking: list[str] = Field(min_length=1)
    subject_profile: Annotated[
        MathKnowledgeProfile | ScienceKnowledgeProfile | PhysicsKnowledgeProfile | ChemistryKnowledgeProfile,
        Field(discriminator="kind"),
    ]
    aliases: list[str] = Field(default_factory=list)
    citations: list[CurriculumCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_point(self) -> "KnowledgePoint":
        if not ID_PATTERN.fullmatch(self.id):
            raise ValueError("knowledge point id must be stable lowercase ASCII")
        if self.grade_min > self.grade_max:
            raise ValueError("grade_min cannot exceed grade_max")
        expected_profile = {
            Subject.MATH: "math",
            Subject.SCIENCE: "science",
            Subject.PHYSICS: "physics",
            Subject.CHEMISTRY: "chemistry",
        }.get(self.subject)
        if expected_profile != self.subject_profile.kind:
            raise ValueError(
                f"subject {self.subject.value} requires {expected_profile} subject_profile"
            )
        return self


class KnowledgePointBatch(StrictModel):
    outline_node_id: str
    points: list[KnowledgePoint] = Field(min_length=1)


class CurriculumRelationType(str, Enum):
    PREREQUISITE = "prerequisite"
    PROGRESSES_TO = "progresses_to"
    SUPPORTS = "supports"
    TRANSFERS_TO = "transfers_to"
    BRIDGES_TO = "bridges_to"
    PARALLEL = "parallel"


class CurriculumRelation(StrictModel):
    source_point_id: str
    target_point_id: str
    relation_type: CurriculumRelationType
    rationale: str = Field(min_length=8)
    citations: list[CurriculumCitation] = Field(default_factory=list)


class CurriculumRelationBatch(StrictModel):
    relations: list[CurriculumRelation] = Field(default_factory=list)


class CoverageEntry(StrictModel):
    outline_node_id: str
    expected_min_points: int = Field(ge=1)
    actual_points: int = Field(ge=0)
    state: CoverageState
    missing_reason: str | None = None

    @model_validator(mode="after")
    def state_matches_counts(self) -> "CoverageEntry":
        expected = (
            CoverageState.EMPTY
            if self.actual_points == 0
            else CoverageState.COMPLETE
            if self.actual_points >= self.expected_min_points
            else CoverageState.PARTIAL
        )
        if self.state != expected:
            raise ValueError(f"coverage state must be {expected.value}")
        if self.state != CoverageState.COMPLETE and not self.missing_reason:
            raise ValueError("incomplete coverage requires a missing_reason")
        return self


class CurriculumKnowledgeNetwork(StrictModel):
    schema_version: str = "1.0"
    outline: CurriculumOutline
    points: list[KnowledgePoint] = Field(min_length=1)
    relations: list[CurriculumRelation] = Field(default_factory=list)
    coverage: list[CoverageEntry] = Field(min_length=1)


class CurriculumPipelineRequest(StrictModel):
    id: str
    title: str
    subjects: list[Subject] = Field(min_length=1)
    grade_min: int = Field(default=1, ge=1, le=9)
    grade_max: int = Field(default=9, ge=1, le=9)
    require_complete_coverage: bool = True
    max_reruns: int = Field(default=2, ge=0, le=5)

    @model_validator(mode="after")
    def validate_scope(self) -> "CurriculumPipelineRequest":
        if self.grade_min > self.grade_max:
            raise ValueError("grade_min cannot exceed grade_max")
        return self


class CurriculumReleaseManifest(StrictModel):
    release_id: str
    version: str
    request_id: str
    state: ReviewState = ReviewState.PUBLISHED
    created_at: datetime = Field(default_factory=utc_now)
    source_catalog_digest: str
    evidence_digest: str
    network_digest: str
    notes: str = ""


class CurriculumReleaseBundle(StrictModel):
    manifest: CurriculumReleaseManifest
    network: CurriculumKnowledgeNetwork
