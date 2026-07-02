from __future__ import annotations

import json

from .models import (
    ArtifactKind,
    ExecutionPlan,
    PlanBatch,
    ProductionRecipe,
    ProductionRequest,
    SupervisionReport,
    ValidationIssue,
)
from .specialized_models import CoreThinkingArtifact, PsychologyArtifact, SpecializedArtifact
from .specialized_taxonomy import PSYCHOLOGY_DIMENSION_TAXONOMY


SPECIALIZED_BASE_POLICY = """
你是青少年数理化学习问题资料生产系统的后台模块。
不得使用“粗心”“不努力”“态度不端正”“笨”等主观标签。
输出 JSON 的任何字段都不得出现“粗心”“不努力”“态度不端正”“笨”“智商低”
或“家长做错了”这些字符序列，即使是否定句、引语、学生自述或“笨拙”等复合词也不允许。
请改写为可观察行为或中性表述，例如“操作不熟练”“担心被负面评价”“认为自己能力不足”。
诊断内容只能表述为待验证的学习假设，不得进行心理或医学诊断。
所有事实性主张必须由本次提供的来源支持；来源不足时缩小结论，禁止凭记忆补齐。
只能输出一个合法 JSON 对象，不要输出 Markdown、解释或代码围栏。
""".strip()


def _schema(model_type: type) -> str:
    return json.dumps(model_type.model_json_schema(), ensure_ascii=False)


def _recipe_name(recipe: ProductionRecipe) -> str:
    return {
        "math_core_thinking_v1": "数学核心思维资料",
        "physics_core_thinking_v1": "物理核心思维资料",
        "chemistry_core_thinking_v1": "化学核心思维资料",
        "learning_psychology_cognition_v1": "青少年学习心理与认知发展资料",
    }.get(recipe.id, recipe.name)


def _rubric_payload(recipe: ProductionRecipe) -> list[dict]:
    instructions = {
        "completeness": "检查维度、关系、请求模块和适用学段是否完整覆盖。",
        "definition_evidence": "检查定义及学段结论是否由精确来源支持。",
        "depth": "检查通俗本质是否揭示真正的思维过程。",
        "observability": "检查教师、家长、学习者三类信号是否具体可观察。",
        "stage_progression": "检查小学到初中的进阶是否连续、无空档和重叠。",
        "thinking_relations": "检查依赖与支持关系是否只使用真实稳定 ID，且方向合理。",
        "consistency": "检查术语、ID、关系和结构是否一致。",
        "model_thinking_relation": "检查每种物理思维与模型建构的关系。",
        "math_boundary": "检查物理思维与数学工具的边界是否明确。",
        "chemical_uniqueness": "检查是否体现研究物质及其变化的化学独特性。",
        "macro_micro_symbolic": "检查宏观—微观—符号表征转换是否准确深入。",
        "physics_distinction": "检查化学思维与物理同类思维的边界是否明确。",
        "theory_authenticity": "检查理论名称、定义和来源真实性。",
        "intervention_boundary": "检查 AI 支持边界和专业转介红线。",
        "mechanism": "检查与学习表现的关联机制。",
        "subject_scenarios": "检查数理化场景是否完整准确。",
    }
    return [
        {
            **item.model_dump(mode="json"),
            "instructions": instructions.get(item.name, item.instructions),
        }
        for item in recipe.rubric
    ]


def specialized_planner_prompts(
    request: ProductionRequest,
    recipe: ProductionRecipe,
) -> tuple[str, str]:
    if recipe.artifact_kind == ArtifactKind.PSYCHOLOGY_COGNITION:
        planning_rules = (
            "心理、认知、动机三个 layer 不得混在同一批；按心理→认知→动机顺序，"
            "每批最多三个模块。12 个请求模块必须各出现一次且只能出现一次。"
        )
    else:
        planning_rules = "请求中的每个模块必须各出现一次且只能出现一次。"
    system = (
        f"{SPECIALIZED_BASE_POLICY}\n\n"
        f"你是 {_recipe_name(recipe)}的 Planner。"
        "只依据来源包规划完整维度，不得用记忆扩展理论或课标清单。"
        "规划要覆盖请求中的每个模块；每批最多包含三个请求模块，并按依赖顺序排列。"
        "expected_node_count 表示该批预计产出的思维维度数量，应与任务粒度一致，不能写成字数或 token 数。"
        f"{planning_rules}"
    )
    user = (
        "把范围拆成可独立审查的批次。batch.source_ids 只能来自来源包。\n"
        f"请求：{request.model_dump_json()}\n"
        f"来源包：{request.source_pack.model_dump_json() if request.source_pack else 'MISSING'}\n"
        f"输出 Schema：{_schema(ExecutionPlan)}"
    )
    return system, user


def specialized_executor_prompts(
    request: ProductionRequest,
    recipe: ProductionRecipe,
    batch: PlanBatch,
    provider_name: str,
    attempt: int,
    feedback: list[str],
) -> tuple[str, str]:
    if recipe.artifact_kind == ArtifactKind.CORE_THINKING:
        model_type = CoreThinkingArtifact
        requirements = (
            "必须给出有来源的学术定义、通俗本质、学段特征、缺失时的可观察表现、"
            "思维依赖与支持关系、发展路径和学科专用画像。"
            "每个维度必须同时给出 teacher、parent、learner 三类观察信号。"
            "每个 batch.module_names 恰好对应一个维度，dimension.name 必须与模块名一致；"
            "不得把课标中的下位表现另行扩成额外维度，可放入 profile 或 development_path。"
            "depends_on 和 supports 只能填写当前 artifact.dimensions 中实际存在的稳定 ID，"
            "禁止填写中文名称、未定义 ID 或自身 ID；如果没有可靠的本批关系就输出空数组。"
            "学段特征应在该维度适用的年级范围内连续，不得出现空档或重叠。"
        )
    elif recipe.artifact_kind == ArtifactKind.PSYCHOLOGY_COGNITION:
        model_type = PsychologyArtifact
        taxonomy = {
            name: {"id": dimension_id, "layer": layer}
            for name, (dimension_id, layer) in PSYCHOLOGY_DIMENSION_TAXONOMY.items()
        }
        requirements = (
            "这是教育资料，不是诊断工具。理论来源必须真实并引用 theory-* 来源；"
            "安全边界必须引用 guideline-* 来源。每个 batch.module_names 恰好对应一个同名维度，"
            "维度 id 和 layer 必须严格使用下列规范映射："
            f"{json.dumps(taxonomy, ensure_ascii=False)}。"
            "数学、物理、化学场景必须齐全；家长与学生信号各至少三条，信号只能是观察线索，"
            "不能当作疾病判定。may_lead_to 和 may_be_caused_by 只能填写上述规范 ID，"
            "表达有来源支持的可能关联，禁止写成确定因果。"
            "severity 必须区分正常波动、持续并影响学习/生活而需要支持、需要专业帮助三档。"
            "ai_support_scope 至少三项，只能包括学习任务拆分、记录、反思、沟通准备等低风险教育支持，"
            "不得包含诊断、治疗、危机处置或替代专业人员。referral_conditions 至少三项，"
            "必须同时覆盖持续数周或功能受损，以及自伤、自杀、伤害他人等需立即求助的安全风险。"
        )
    else:
        raise ValueError(f"unsupported specialized artifact kind: {recipe.artifact_kind}")
    selected_sources = [
        source.model_dump(mode="json")
        for source in request.source_pack.documents  # type: ignore[union-attr]
        if source.id in batch.source_ids
    ]
    identity = {
        "artifact_kind": recipe.artifact_kind.value,
        "schema_version": "1.0",
        "recipe_id": recipe.id,
        "request_id": request.id,
        "batch_id": batch.id,
        "candidate_id": f"{batch.id}-{provider_name}-attempt-{attempt}",
        "provider_name": provider_name,
    }
    system = (
        f"{SPECIALIZED_BASE_POLICY}\n\n你是 {_recipe_name(recipe)}的 Executor。\n"
        "所有学术主张必须引用本批来源；来源不足时缩小结论，禁止编造。"
    )
    user = (
        f"{requirements}\n"
        f"identity 字段必须原样输出：{json.dumps(identity, ensure_ascii=False)}\n"
        f"批次：{batch.model_dump_json()}\n"
        f"上轮修正要求：{json.dumps(feedback, ensure_ascii=False)}\n"
        f"可用来源：{json.dumps(selected_sources, ensure_ascii=False)}\n"
        f"输出 Schema：{_schema(model_type)}"
    )
    return system, user


def specialized_supervisor_prompts(
    request: ProductionRequest,
    recipe: ProductionRecipe,
    batch: PlanBatch,
    candidates: list[SpecializedArtifact],
    issues_by_candidate: dict[str, list[ValidationIssue]],
) -> tuple[str, str]:
    if recipe.artifact_kind == ArtifactKind.PSYCHOLOGY_COGNITION:
        specialized_rules = (
            "这是高风险资料。逐项核对 theory_citations 是否来自真实理论来源，"
            "citations 是否包含专业安全指南。理论来源虚构、把相关写成确定因果、"
            "把观察信号写成诊断标准、AI 边界过宽、或转介条件漏掉持续功能受损与紧急安全风险，"
            "任一出现都禁止 pass，并应 full_rerun 或 human_review。"
            "每个批次模块必须一一对应同名维度，id/layer 和关联目标必须符合规范分类。"
            "PsychologyDimension 只有 parent_signals 和 learner_signals，数理化课堂表现写在"
            "subject_scenarios 中；Schema 没有 teacher_signals，禁止要求候选新增该字段或因此扣分。"
        )
    else:
        specialized_rules = (
            "检查每个核心思维维度是否同时有教师、家长、学习者三类可观察信号。"
            "检查 depends_on/supports 是否只引用当前候选中真实存在的稳定 ID。"
            "引用只能放在每个 dimension.citations 中，Schema 不存在顶层 citations，"
            "禁止提出添加顶层 citations。每个 batch.module_names 必须恰好对应一个同名维度，"
            "不得额外扩写下位维度。"
        )
    system = (
        f"{SPECIALIZED_BASE_POLICY}\n\n你是 {_recipe_name(recipe)}的 Supervisor。"
        "硬校验错误不能被评分覆盖。逐条核查来源是否真正支持定义、学段进阶和关系。"
        f"{specialized_rules}"
        "最终分数按量表权重计算：90–100 pass，70–89 partial_rerun，0–69 full_rerun。"
        "若硬校验存在 error，禁止 pass。"
    )
    user = (
        f"批次：{batch.model_dump_json()}\n"
        f"量表：{json.dumps(_rubric_payload(recipe), ensure_ascii=False)}\n"
        f"候选：{json.dumps([item.model_dump(mode='json') for item in candidates], ensure_ascii=False)}\n"
        f"硬校验：{json.dumps({key: [issue.model_dump(mode='json') for issue in value] for key, value in issues_by_candidate.items()}, ensure_ascii=False)}\n"
        f"输出 Schema：{_schema(SupervisionReport)}"
    )
    return system, user
