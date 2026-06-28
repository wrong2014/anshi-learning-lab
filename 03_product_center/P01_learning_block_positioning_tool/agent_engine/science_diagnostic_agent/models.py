from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Subject(str, Enum):
    MATH = "math"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    UNKNOWN = "unknown"


class Actor(str, Enum):
    PARENT = "parent"
    CHILD = "child"
    SYSTEM = "system"


class FactorCode(str, Enum):
    F01_PRIOR_KNOWLEDGE = "F01_prior_knowledge_gap"
    F02_CONCEPT = "F02_concept_understanding_unstable"
    F03_LANGUAGE_SYMBOL = "F03_subject_language_symbol_difficulty"
    F04_REPRESENTATION = "F04_representation_conversion_difficulty"
    F05_MODEL_TRANSFER = "F05_modeling_transfer_difficulty"
    F06_EXECUTION = "F06_execution_instability"
    F07_METACOGNITION = "F07_metacognition_review_weak"
    F08_STRATEGY = "F08_learning_strategy_inefficient"
    F09_EMOTION = "F09_emotion_motivation_self_efficacy"
    F10_SUPPORT_AI = "F10_family_support_ai_misaligned"
    F11_ATTENTION_EXECUTIVE = "F11_attention_working_memory_load"
    F12_MISCONCEPTION = "F12_misconception_naive_theory_interference"


class DiagnosticCategory(str, Enum):
    """Parent-facing summary layer; detailed factor scores stay internal."""

    A_FOUNDATION = "A_foundation_and_concept"
    B_REPRESENTATION = "B_language_and_representation"
    C_MODELING = "C_modeling_and_transfer"
    D_EXECUTION = "D_execution_and_cognitive_load"
    E_SELF_REGULATION = "E_self_regulation_and_emotion"


class AmplifierCode(str, Enum):
    """Context that can amplify a learning bottleneck without replacing it."""

    F_SUPPORT = "F_support_and_ai_mismatch"
    G_EXAM_CONTEXT = "G_exam_context_and_pace"
    H_RHYTHM = "H_sleep_and_learning_rhythm"


CATEGORY_LABELS: dict[DiagnosticCategory, str] = {
    DiagnosticCategory.A_FOUNDATION: "知识基础与概念建构",
    DiagnosticCategory.B_REPRESENTATION: "题意理解与表征转换",
    DiagnosticCategory.C_MODELING: "关系建模与迁移",
    DiagnosticCategory.D_EXECUTION: "步骤执行与认知负荷",
    DiagnosticCategory.E_SELF_REGULATION: "自主纠错与学习状态",
}


AMPLIFIER_LABELS: dict[AmplifierCode, str] = {
    AmplifierCode.F_SUPPORT: "帮助方式可能跳过了孩子自己的思考",
    AmplifierCode.G_EXAM_CONTEXT: "考试节奏会放大平时已有的卡点",
    AmplifierCode.H_RHYTHM: "睡眠与学习节律可能让状态更不稳定",
}


FACTOR_TO_CATEGORY: dict[FactorCode, DiagnosticCategory] = {
    FactorCode.F01_PRIOR_KNOWLEDGE: DiagnosticCategory.A_FOUNDATION,
    FactorCode.F02_CONCEPT: DiagnosticCategory.A_FOUNDATION,
    FactorCode.F12_MISCONCEPTION: DiagnosticCategory.A_FOUNDATION,
    FactorCode.F03_LANGUAGE_SYMBOL: DiagnosticCategory.B_REPRESENTATION,
    FactorCode.F04_REPRESENTATION: DiagnosticCategory.B_REPRESENTATION,
    FactorCode.F05_MODEL_TRANSFER: DiagnosticCategory.C_MODELING,
    FactorCode.F06_EXECUTION: DiagnosticCategory.D_EXECUTION,
    FactorCode.F11_ATTENTION_EXECUTIVE: DiagnosticCategory.D_EXECUTION,
    FactorCode.F07_METACOGNITION: DiagnosticCategory.E_SELF_REGULATION,
    FactorCode.F08_STRATEGY: DiagnosticCategory.E_SELF_REGULATION,
    FactorCode.F09_EMOTION: DiagnosticCategory.E_SELF_REGULATION,
}


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendedPath(str, Enum):
    P02 = "P02_parent_ai_workshop"
    P03 = "P03_one_family_one_plan"
    HUMAN_REVIEW = "human_review"
    NOT_FIT = "not_fit"


class UIBlockType(str, Enum):
    MESSAGE = "message"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    SCALE = "scale"
    SHORT_TEXT = "short_text"
    CHILD_CHECKPOINT = "child_checkpoint"
    RESULT_CARD = "result_card"


class UIOption(BaseModel):
    id: str
    label: str
    hint: str | None = None


class UIBlock(BaseModel):
    id: str
    type: UIBlockType
    title: str
    body: str | None = None
    options: list[UIOption] = Field(default_factory=list)
    allow_skip: bool = True


class AnswerEvent(BaseModel):
    question_id: str
    actor: Actor = Actor.PARENT
    selected_option_ids: list[str] = Field(default_factory=list)
    free_text: str | None = None


class EvidenceItem(BaseModel):
    source: Actor
    text: str
    related_factors: list[FactorCode] = Field(default_factory=list)


class FactorScore(BaseModel):
    factor: FactorCode
    raw_score: float
    normalized_score: float
    evidence: list[str] = Field(default_factory=list)


class FactorScoringResult(BaseModel):
    subject: Subject
    scores: list[FactorScore]
    top_factors: list[FactorCode]
    confidence: Confidence
    risk_flags: list[str] = Field(default_factory=list)


class DiagnosticSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    subject: Subject = Subject.UNKNOWN
    answers: list[AnswerEvent] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    completed_question_ids: list[str] = Field(default_factory=list)


class DiagnosisResult(BaseModel):
    session_id: str
    subject: Subject
    primary_factor: FactorCode
    secondary_factors: list[FactorCode] = Field(default_factory=list)
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    parent_common_mistake: str
    next_7_days_stop: str
    next_7_days_start: str
    recommended_path: RecommendedPath
    human_review_needed: bool = False
    public_summary: str


ProviderName = Literal["deepseek", "doubao"]


class LLMProviderConfig(BaseModel):
    provider: ProviderName
    api_key: str | None = None
    base_url: str | None = None
    text_model: str | None = None
    vision_model: str | None = None
    asr_app_id: str | None = None
    tts_app_id: str | None = None


class ExtractedSignals(BaseModel):
    option_ids: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


class ProviderStatus(BaseModel):
    enable_llm: bool
    default_text_provider: str
    deepseek_ready: bool
    doubao_ready: bool
    deepseek_model: str | None = None
    doubao_text_model: str | None = None
    mode: str
