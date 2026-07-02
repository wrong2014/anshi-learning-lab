from __future__ import annotations

import json

from .models import (
    EvidenceMode,
    ExecutionPlan,
    KnowledgeArtifact,
    PlanBatch,
    ProductionRecipe,
    ProductionRequest,
    SupervisionReport,
    ValidationIssue,
)


BASE_POLICY = """
你是青少年数理化学习问题资料生产系统的后台模块。
不得使用“粗心”“不努力”“态度不端正”“笨”等主观标签。
诊断内容只能表示待验证的学习假设，不得进行心理或医学诊断。
只输出一个合法 JSON 对象，不要输出 Markdown、解释或代码围栏。
""".strip()


def _schema_text(model_type: type) -> str:
    return json.dumps(model_type.model_json_schema(), ensure_ascii=False)


def _evidence_policy(request: ProductionRequest) -> str:
    if request.evidence_mode == EvidenceMode.SOURCE_GROUNDED:
        return """
当前模式：source_grounded。
所有事实必须来自本次提供的来源包；来源不足时必须缩小结论，禁止用记忆补齐。
不得创建来源包中不存在的 source_id。每个知识点、关系和学习卡点必须至少有一条精确引用。
""".strip()
    return """
当前模式：model_distillation。
目标是榨干大语言模型已有的学科知识、教学经验和学习卡点经验，不需要外部来源包。
请主动展开：知识点、前置依赖、常见误解、隐性概念、可观察学习信号、诊断追问蓝图。
不得伪造教材、论文、课程标准或网页引用；source_ids 和所有 citations 必须输出空数组。
对无法确定的内容要表述为“待验证学习假设”，但不要因为没有来源包而缩小覆盖面。
""".strip()


def _request_payload(request: ProductionRequest) -> str:
    return request.model_dump_json(
        exclude={"source_pack": {"documents": {"__all__": {"content"}}}}
    )


def planner_prompts(request: ProductionRequest, recipe: ProductionRecipe) -> tuple[str, str]:
    system = f"{BASE_POLICY}\n\n{_evidence_policy(request)}\n\n你当前担任 Planner。\n{recipe.planner_instructions}"
    source_pack_text = request.source_pack.model_dump_json() if request.source_pack else "无来源包；本次必须使用 model_distillation。"
    user = (
        "请根据生产请求生成执行计划。\n"
        "model_distillation 模式下每个 batch.source_ids 必须是空数组；source_grounded 模式下只能使用来源包中存在的来源ID。\n"
        f"输出必须符合 ExecutionPlan JSON Schema：{_schema_text(ExecutionPlan)}\n\n"
        f"生产请求：{_request_payload(request)}\n\n"
        f"来源包：{source_pack_text}"
    )
    return system, user


def executor_prompts(
    request: ProductionRequest,
    recipe: ProductionRecipe,
    batch: PlanBatch,
    provider_name: str,
    attempt: int,
    feedback: list[str],
) -> tuple[str, str]:
    system = f"{BASE_POLICY}\n\n{_evidence_policy(request)}\n\n你当前担任 Executor。\n{recipe.executor_instructions}"
    source_documents = request.source_pack.documents if request.source_pack else []
    selected_sources = [item for item in source_documents if item.id in batch.source_ids]
    identity = {
        "schema_version": "1.0",
        "recipe_id": recipe.id,
        "request_id": request.id,
        "batch_id": batch.id,
        "candidate_id": f"{batch.id}-{provider_name}-attempt-{attempt}",
        "provider_name": provider_name,
    }
    user = (
        "请完成当前批次并输出 KnowledgeArtifact。identity 中的字段必须原样写入。\n"
        "model_distillation 模式下 source_ids、nodes[].citations、relations[].citations、learning_blocks[].citations 必须是空数组；"
        "source_grounded 模式下每个知识点、关系和学习卡点必须至少有一条精确引用。"
        "每个知识点必须至少包含一个学习卡点；每个卡点必须包含可观察信号和追问蓝图。\n"
        f"输出必须符合 KnowledgeArtifact JSON Schema：{_schema_text(KnowledgeArtifact)}\n\n"
        f"identity：{json.dumps(identity, ensure_ascii=False)}\n"
        f"批次：{batch.model_dump_json()}\n"
        f"上轮修正要求：{json.dumps(feedback, ensure_ascii=False)}\n"
        f"可使用来源：{json.dumps([item.model_dump(mode='json') for item in selected_sources], ensure_ascii=False)}"
    )
    return system, user


def supervisor_prompts(
    request: ProductionRequest,
    recipe: ProductionRecipe,
    batch: PlanBatch,
    candidates: list[KnowledgeArtifact],
    deterministic_issues: dict[str, list[ValidationIssue]],
) -> tuple[str, str]:
    rubric = [item.model_dump(mode="json") for item in recipe.rubric]
    system = (
        f"{BASE_POLICY}\n\n{_evidence_policy(request)}\n\n你当前担任 Supervisor。"
        "硬校验错误不能被模型评分覆盖；存在硬错误的候选不得选为通过候选。"
        "model_distillation 模式下重点审查覆盖面、内部一致性、教学洞察密度和可观察性；不要因为没有来源引用而扣分。"
        "source_grounded 模式下重点审查引用是否支撑主张。"
        "最终分数必须是按 rubric 权重计算后的整数。"
        "阈值严格为：90-100 pass，70-89 partial_rerun，0-69 full_rerun。"
    )
    candidate_payload = [candidate.model_dump(mode="json") for candidate in candidates]
    issue_payload = {
        key: [issue.model_dump(mode="json") for issue in value]
        for key, value in deterministic_issues.items()
    }
    user = (
        f"审查批次：{batch.model_dump_json()}\n"
        f"审查量表：{json.dumps(rubric, ensure_ascii=False)}\n"
        f"候选：{json.dumps(candidate_payload, ensure_ascii=False)}\n"
        f"硬校验结果：{json.dumps(issue_payload, ensure_ascii=False)}\n\n"
        f"输出必须符合 SupervisionReport JSON Schema：{_schema_text(SupervisionReport)}"
    )
    return system, user
