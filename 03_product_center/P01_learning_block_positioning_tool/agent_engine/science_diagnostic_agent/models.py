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


class DiagnosticCategory(str, Enum):
    """5 大诊断类别（降维后）"""
    A_FOUNDATION = "foundation"        # 基础概念不稳
    B_REPRESENTATION = "representation" # 信息表征卡点
    C_MODELING = "modeling"            # 建模迁移困难
    D_EXECUTION = "execution"          # 执行流程不稳
    E_SELF_REGULATION = "self_regulation"  # 自我调节薄弱


class AmplifierCode(str, Enum):
    """3 个放大因素（不能做主因）"""
    F_REPAIR_LOOP = "repair_loop"      # 错题修复还没形成闭环
    G_EXAM_RHYTHM = "exam_rhythm"      # 考试过程与节奏问题
    H_AVOIDANCE = "avoidance"          # 数理化回避或挫败感


# 10因子 → 5大类 的映射
FACTOR_TO_CATEGORY: dict[FactorCode, DiagnosticCategory] = {
    FactorCode.F01_PRIOR_KNOWLEDGE: DiagnosticCategory.A_FOUNDATION,
    FactorCode.F02_CONCEPT: DiagnosticCategory.A_FOUNDATION,
    FactorCode.F03_LANGUAGE_SYMBOL: DiagnosticCategory.B_REPRESENTATION,
    FactorCode.F04_REPRESENTATION: DiagnosticCategory.B_REPRESENTATION,
    FactorCode.F05_MODEL_TRANSFER: DiagnosticCategory.C_MODELING,
    FactorCode.F06_EXECUTION: DiagnosticCategory.D_EXECUTION,
    FactorCode.F07_METACOGNITION: DiagnosticCategory.E_SELF_REGULATION,
    FactorCode.F08_STRATEGY: DiagnosticCategory.E_SELF_REGULATION,
    FactorCode.F09_EMOTION: DiagnosticCategory.E_SELF_REGULATION,
    FactorCode.F10_SUPPORT_AI: DiagnosticCategory.E_SELF_REGULATION,
}


# 类别中文标签
CATEGORY_LABELS: dict[DiagnosticCategory, str] = {
    DiagnosticCategory.A_FOUNDATION: "基础概念不稳",
    DiagnosticCategory.B_REPRESENTATION: "信息表征卡点",
    DiagnosticCategory.C_MODELING: "建模迁移困难",
    DiagnosticCategory.D_EXECUTION: "执行流程不稳",
    DiagnosticCategory.E_SELF_REGULATION: "自我调节薄弱",
}


# 放大器中文标签
AMPLIFIER_LABELS: dict[AmplifierCode, str] = {
    AmplifierCode.F_REPAIR_LOOP: "错题修复还没形成闭环",
    AmplifierCode.G_EXAM_RHYTHM: "考试过程与节奏问题",
    AmplifierCode.H_AVOIDANCE: "出现了回避或挫败感",
}


class DiagnosticCategory(str, Enum):
    """诊断结果的五大类别（A–E）"""
    A_FOUNDATION = "A_foundation"
    B_REPRESENTATION = "B_representation"
    C_MODELING = "C_modeling"
    D_EXECUTION = "D_execution"
    E_SELF_REGULATION = "E_self_regulation"


class AmplifierCode(str, Enum):
    """放大因子代码（F–H）"""
    F_REPAIR_LOOP = "F_repair_loop"
    G_EXAM_RHYTHM = "G_exam_rhythm"
    H_AVOIDANCE = "H_avoidance"


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
