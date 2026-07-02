from __future__ import annotations

from .models import ArtifactKind, ProductionRecipe, RubricDimension, Subject


COMMON_RUBRIC = [
    RubricDimension(name="completeness", weight=0.20, instructions="检查范围覆盖、字段完整和关系完整。"),
    RubricDimension(name="accuracy", weight=0.25, instructions="逐条检查定义、关系和事实是否由给定来源支持。"),
    RubricDimension(name="depth", weight=0.20, instructions="检查卡点本质是否揭示了学习过程中的第一处断点。"),
    RubricDimension(name="observability", weight=0.20, instructions="检查信号是否能被家长、教师或学生具体观察。"),
    RubricDimension(name="consistency", weight=0.15, instructions="检查术语、粒度、ID和格式是否一致。"),
]

MATH_THINKING_RUBRIC = [
    RubricDimension(name="completeness", weight=0.15, instructions="检查思维维度、关系和学段覆盖。"),
    RubricDimension(name="definition_evidence", weight=0.20, instructions="检查学术定义及其来源依据。"),
    RubricDimension(name="depth", weight=0.15, instructions="检查通俗本质是否揭示真正思维过程。"),
    RubricDimension(name="observability", weight=0.15, instructions="检查缺失表现是否具体可观察。"),
    RubricDimension(name="stage_progression", weight=0.15, instructions="检查小学到初中的发展进阶。"),
    RubricDimension(name="thinking_relations", weight=0.10, instructions="检查思维依赖与支撑关系。"),
    RubricDimension(name="consistency", weight=0.10, instructions="检查术语与结构一致。"),
]

PHYSICS_THINKING_RUBRIC = [
    RubricDimension(name="completeness", weight=0.10, instructions="检查物理思维维度覆盖。"),
    RubricDimension(name="definition_evidence", weight=0.15, instructions="检查定义与来源。"),
    RubricDimension(name="model_thinking_relation", weight=0.20, instructions="检查每种思维与物理模型思维的关系。"),
    RubricDimension(name="math_boundary", weight=0.15, instructions="检查物理思维和数学工具边界。"),
    RubricDimension(name="observability", weight=0.15, instructions="检查缺失表现是否可观察。"),
    RubricDimension(name="stage_progression", weight=0.15, instructions="检查学段进阶。"),
    RubricDimension(name="consistency", weight=0.10, instructions="检查术语一致。"),
]

CHEMISTRY_THINKING_RUBRIC = [
    RubricDimension(name="completeness", weight=0.10, instructions="检查化学思维维度覆盖。"),
    RubricDimension(name="definition_evidence", weight=0.15, instructions="检查定义与来源。"),
    RubricDimension(name="chemical_uniqueness", weight=0.20, instructions="检查化学学科独特性。"),
    RubricDimension(name="macro_micro_symbolic", weight=0.20, instructions="检查宏观—微观—符号转化深度。"),
    RubricDimension(name="physics_distinction", weight=0.10, instructions="检查与物理同类思维的区别。"),
    RubricDimension(name="observability", weight=0.15, instructions="检查缺失表现是否可观察。"),
    RubricDimension(name="consistency", weight=0.10, instructions="检查术语一致。"),
]

PSYCHOLOGY_RUBRIC = [
    RubricDimension(name="theory_authenticity", weight=0.25, instructions="逐条核查理论名称、定义和来源真实性。"),
    RubricDimension(name="intervention_boundary", weight=0.25, instructions="检查 AI 支持边界和专业转介红线。"),
    RubricDimension(name="observability", weight=0.15, instructions="检查家长和学生信号是否具体。"),
    RubricDimension(name="mechanism", weight=0.15, instructions="检查与学习表现的关联机制。"),
    RubricDimension(name="subject_scenarios", weight=0.10, instructions="检查数理化场景是否完整准确。"),
    RubricDimension(name="consistency", weight=0.10, instructions="检查术语与严重程度一致。"),
]


RECIPES: dict[str, ProductionRecipe] = {
    "math_knowledge_graph_v1": ProductionRecipe(
        id="math_knowledge_graph_v1",
        name="数学知识图谱与学习卡点资料",
        artifact_kind=ArtifactKind.KNOWLEDGE_GRAPH,
        subject=Subject.MATH,
        planner_instructions=(
            "只能依据来源包列出的课程范围规划，不得自行补写课程目录。"
            "按依赖顺序拆批，每批最多三个子模块，并明确每批使用的来源。"
        ),
        executor_instructions=(
            "产出数学知识点、前后置关系、常见学习卡点、可观察信号和诊断追问蓝图。"
            "定义与依赖关系必须逐条引用来源；卡点描述必须定位第一处断点，"
            "不得使用粗心、不努力、笨等主观标签。"
        ),
        rubric=COMMON_RUBRIC,
    ),
    "physics_knowledge_graph_v1": ProductionRecipe(
        id="physics_knowledge_graph_v1",
        name="物理知识图谱与学习卡点资料",
        artifact_kind=ArtifactKind.KNOWLEDGE_GRAPH,
        subject=Subject.PHYSICS,
        planner_instructions="依据来源规划模块，显式标注跨模块依赖并按依赖顺序拆批。",
        executor_instructions="区分概念、公式和物理情境建模，产出可观察卡点及追问蓝图。",
        rubric=COMMON_RUBRIC,
    ),
    "chemistry_knowledge_graph_v1": ProductionRecipe(
        id="chemistry_knowledge_graph_v1",
        name="化学知识图谱与学习卡点资料",
        artifact_kind=ArtifactKind.KNOWLEDGE_GRAPH,
        subject=Subject.CHEMISTRY,
        planner_instructions="依据来源规划模块，标注记忆、推理与混合内容的覆盖。",
        executor_instructions="显式描述宏观现象、微观粒子和符号表达之间的转换卡点。",
        rubric=COMMON_RUBRIC,
    ),
    "math_core_thinking_v1": ProductionRecipe(
        id="math_core_thinking_v1",
        name="数学核心思维资料",
        artifact_kind=ArtifactKind.CORE_THINKING,
        subject=Subject.MATH,
        planner_instructions="只依据来源包中的思维框架规划层级与依赖。",
        executor_instructions="产出有来源的定义、阶段特征、缺失表现和可观察追问。",
        rubric=MATH_THINKING_RUBRIC,
    ),
    "physics_core_thinking_v1": ProductionRecipe(
        id="physics_core_thinking_v1",
        name="物理核心思维资料",
        artifact_kind=ArtifactKind.CORE_THINKING,
        subject=Subject.PHYSICS,
        planner_instructions="依据来源规划物理思维，明确其与模型思维的关系。",
        executor_instructions="区分物理思维与数学工具，产出阶段特征和可观察卡点。",
        rubric=PHYSICS_THINKING_RUBRIC,
    ),
    "chemistry_core_thinking_v1": ProductionRecipe(
        id="chemistry_core_thinking_v1",
        name="化学核心思维资料",
        artifact_kind=ArtifactKind.CORE_THINKING,
        subject=Subject.CHEMISTRY,
        planner_instructions="依据来源规划化学思维，优先处理宏观与微观转化。",
        executor_instructions="说明化学学科独特性，区分化学守恒与物理守恒。",
        rubric=CHEMISTRY_THINKING_RUBRIC,
    ),
    "learning_psychology_cognition_v1": ProductionRecipe(
        id="learning_psychology_cognition_v1",
        name="青少年学习心理与认知发展资料",
        artifact_kind=ArtifactKind.PSYCHOLOGY_COGNITION,
        subject=Subject.CROSS_SUBJECT,
        planner_instructions="仅规划来源包明确覆盖的成熟理论与维度，不得扩展未经引用的概念。",
        executor_instructions=(
            "理论来源必须真实可定位；明确AI支持边界和专业转介红线；"
            "不得进行心理或医学诊断，不得承诺干预效果。"
        ),
        rubric=PSYCHOLOGY_RUBRIC,
        high_risk=True,
        requires_human_approval=True,
    ),
}


def get_recipe(recipe_id: str) -> ProductionRecipe:
    try:
        return RECIPES[recipe_id]
    except KeyError as exc:
        raise KeyError(f"unknown recipe: {recipe_id}") from exc


def list_recipes() -> list[ProductionRecipe]:
    return list(RECIPES.values())
