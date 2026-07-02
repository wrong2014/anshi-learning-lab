from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MaterialLayer = Literal["knowledge_graph", "core_thinking", "psychology_cognition"]
ApprovalScope = Literal[
    "published",
    "internal_conditionally_approved",
    "human_review_required",
]
SafetyLevel = Literal["standard", "sensitive", "referral"]
RetrievalSubject = Literal["math", "science", "physics", "chemistry"]
RetrievalActor = Literal["parent", "learner", "teacher", "system"]


class RetrievalUnit(BaseModel):
    """The smallest traceable passage that may be returned by retrieval."""

    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(min_length=3)
    layer: MaterialLayer
    unit_type: str = Field(min_length=3)
    source_id: str = Field(min_length=3)
    parent_id: str = Field(min_length=3)
    source_artifact: str = Field(min_length=3)
    source_path: str = Field(min_length=2)
    material_version: str = Field(min_length=1)
    approval_scope: ApprovalScope
    safety_level: SafetyLevel = "standard"
    title: str = Field(min_length=1)
    text: str = Field(min_length=2)
    subject: RetrievalSubject | None = None
    grade_min: int | None = Field(default=None, ge=1, le=9)
    grade_max: int | None = Field(default=None, ge=1, le=9)
    actor: RetrievalActor | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_grade_range(self) -> "RetrievalUnit":
        if (self.grade_min is None) != (self.grade_max is None):
            raise ValueError("grade_min and grade_max must be set together")
        if self.grade_min is not None and self.grade_min > self.grade_max:
            raise ValueError("grade_min cannot exceed grade_max")
        return self


class RetrievalEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    relation_type: str
    rationale: str = ""
    layer: MaterialLayer
    source_artifact: str
    source_path: str


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_digests: dict[str, str]
    source_versions: dict[str, str]
    unit_counts: dict[str, int]
    edge_counts: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


class NormalizedCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: CorpusManifest
    units: list[RetrievalUnit]
    edges: list[RetrievalEdge]


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    subjects: list[RetrievalSubject] = Field(default_factory=list)
    grade: int | None = Field(default=None, ge=1, le=9)
    layers: list[MaterialLayer] = Field(default_factory=list)
    unit_types: list[str] = Field(default_factory=list)
    actors: list[RetrievalActor] = Field(default_factory=list)
    approval_scopes: list[ApprovalScope] = Field(default_factory=list)
    safety_levels: list[SafetyLevel] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=1, le=50)
    include_graph_neighbors: bool = True
    graph_limit: int = Field(default=4, ge=0, le=20)


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: RetrievalUnit
    score: float
    lexical_score: float | None = None
    vector_score: float | None = None
    matched_by: list[Literal["lexical", "vector", "graph", "exact"]]
    via_relation: str | None = None


class RetrievalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: RetrievalQuery
    index_version: str
    embedding_model: str | None = None
    hits: list[RetrievalHit]
    warnings: list[str] = Field(default_factory=list)
