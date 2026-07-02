from __future__ import annotations

import json

from .curriculum_models import (
    CurriculumKnowledgeNetwork,
    CurriculumEvidencePage,
    CurriculumOutline,
    CurriculumPipelineRequest,
    CurriculumRelation,
    CurriculumSourceCatalog,
    KnowledgePointBatch,
    OutlineNode,
)
from .models import SupervisionReport, ValidationIssue


POLICY = """
你是中国义务教育数理化知识网络生产系统的后台智能体。
课程范围必须由教育部课程标准证据确定，模型记忆不能扩张官方大纲。
必须区分课标原文、从课标作出的结构化归纳、以及需要后续核验的知识点细化。
只输出合法 JSON，不输出 Markdown。稳定 ID 只能使用小写 ASCII 字母、数字、点、下划线和连字符。
""".strip()


def _schema(model: type) -> str:
    return json.dumps(model.model_json_schema(), ensure_ascii=False)


def outline_prompts(
    request: CurriculumPipelineRequest,
    catalog: CurriculumSourceCatalog,
    seed: CurriculumOutline,
    feedback: list[str] | None = None,
) -> tuple[str, str]:
    system = POLICY + "\n\n你是大纲审计智能体。已核验种子就是本轮冻结的完整任务树。"
    user = (
        "逐项核对请求、来源目录与种子，然后原样返回种子。"
        "不得增加、删除、重排或改写任何节点、字段、引用与元数据。"
        "知识点细化属于下一阶段，绝不能通过新增 stage_task 代替。\n"
        f"请求：{request.model_dump_json()}\n"
        f"来源目录：{catalog.model_dump_json()}\n"
        f"已核验种子：{seed.model_dump_json()}\n"
        f"上轮修正要求：{json.dumps(feedback or [], ensure_ascii=False)}\n"
        f"输出 Schema：{_schema(CurriculumOutline)}"
    )
    return system, user


def point_prompts(
    task: OutlineNode,
    evidence_pages: list[CurriculumEvidencePage],
    feedback: list[str] | None = None,
) -> tuple[str, str]:
    system = POLICY + "\n\n你是知识点智能体。你每次只处理一个大纲叶子，不能跳到其他任务。"
    user = (
        "穷举该任务下达到课标要求所需的原子知识点。每个点必须可单独判断是否掌握，"
        "必须逐点引用给定 OCR 证据页，引用中的 page_start 与 page_end 必须是同一个逻辑页，"
        "excerpt 必须是某一个证据页 text 字段中连续存在的原文片段。"
        "若一句话跨越两个逻辑页，必须拆成两条单页引用，或只引用其中一页内完整存在的片段；"
        "严禁把相邻页文字拼接成一条 excerpt。不得把教材章节名冒充知识点。"
        "若任务属于综合与实践，必须先从证据中识别全部命名主题或活动，"
        "每个主题或活动至少建立一个可诊断的知识点，不得只抽取部分示例。"
        "数学必须填写表征、关键程序和应用情境；科学必须填写探究实践；"
        "物理必须区分概念、公式、适用条件、概念公式关联和物理情境；"
        "化学必须标明记忆/推理/混合类型，以及宏观—微观—符号转换。"
        f"任务：{task.model_dump_json()}\n"
        f"官方课标 OCR 证据页：{json.dumps([page.model_dump(mode='json') for page in evidence_pages], ensure_ascii=False)}\n"
        f"上轮修正要求：{json.dumps(feedback or [], ensure_ascii=False)}\n"
        f"输出 Schema：{_schema(KnowledgePointBatch)}"
    )
    return system, user


def graph_prompts(
    outline: CurriculumOutline,
    point_batches: list[KnowledgePointBatch],
    feedback: list[str] | None = None,
    *,
    scope_note: str = "",
    existing_relations: list[CurriculumRelation] | None = None,
    compact_points: bool = False,
) -> tuple[str, str]:
    system = POLICY + "\n\n你是领域智能体的关系阶段 Executor。你只建立有明确教学含义的知识关系，不能为了图看起来密集而连边。"
    all_points = [point for batch in point_batches for point in batch.points]
    points = (
        [
            {
                "id": point.id,
                "outline_node_id": point.outline_node_id,
                "subject": point.subject.value,
                "name": point.name,
                "definition": point.definition,
                "core_thinking": point.core_thinking,
            }
            for point in all_points
        ]
        if compact_points
        else [point.model_dump(mode="json") for point in all_points]
    )
    relation_schema = {
        "type": "object",
        "properties": {
            "relations": {"type": "array", "items": CurriculumRelation.model_json_schema()}
        },
        "required": ["relations"],
        "additionalProperties": False,
    }
    user = (
        "建立 prerequisite、progresses_to、supports、transfers_to、bridges_to、parallel 关系。"
        "重点检查小学科学到初中物理/化学的 bridges_to；prerequisite 的方向是前置点指向后续点。"
        "只能使用上述六种关系类型，不得创造 enables 等新枚举。"
        "系统检查同学段内直接依赖、相邻学段进阶、跨学段迁移，并补足明显孤立的知识点；"
        "面积公式、模型推导、表征转换等有明确教学顺序的内容不得误标为 parallel。"
        "关系端点只能来自给定知识点。课标未直接声明的教学推断可以不带引用，但 rationale 必须明确。\n"
        f"本批范围：{scope_note}\n"
        f"大纲：{outline.model_dump_json()}\n"
        f"知识点：{json.dumps(points, ensure_ascii=False)}\n"
        f"已有关系（不得重复）：{json.dumps([item.model_dump(mode='json') for item in (existing_relations or [])], ensure_ascii=False)}\n"
        f"上轮修正要求：{json.dumps(feedback or [], ensure_ascii=False)}\n"
        f"输出 Schema：{json.dumps(relation_schema, ensure_ascii=False)}"
    )
    return system, user


CURRICULUM_RUBRIC = {
    "completeness": 0.25,
    "accuracy": 0.25,
    "source_grounding": 0.20,
    "consistency": 0.15,
    "subject_fidelity": 0.15,
}


def curriculum_supervisor_prompts(
    *,
    stage: str,
    unit_id: str,
    candidates: list[dict],
    issues_by_candidate: dict[str, list[ValidationIssue]],
    context: dict | None = None,
) -> tuple[str, str]:
    system = (
        POLICY
        + "\n\n你是课标知识图谱 Supervisor。硬校验错误不能被评分覆盖，"
        "有硬错误的候选不得被选中。按完整性、准确性、来源扎根、结构一致性、学科忠实度评分。"
        "最终分数必须按给定权重计算并四舍五入。阈值严格为：90-100 pass，"
        "70-89 partial_rerun，0-69 full_rerun。只能依据当前 Schema、审查上下文与硬校验评分，"
        "不得建议 Schema 不存在的层级或字段。outline 阶段的冻结种子无需扩写；"
        "候选若精确保留冻结种子且无硬错误，应判定为 pass。"
    )
    serialized_issues = {
        candidate_id: [issue.model_dump(mode="json") for issue in issues]
        for candidate_id, issues in issues_by_candidate.items()
    }
    user = (
        f"阶段：{stage}\n"
        f"执行单元：{unit_id}\n"
        f"审查上下文：{json.dumps(context or {}, ensure_ascii=False)}\n"
        f"量表与权重：{json.dumps(CURRICULUM_RUBRIC, ensure_ascii=False)}\n"
        f"候选：{json.dumps(candidates, ensure_ascii=False)}\n"
        f"硬校验：{json.dumps(serialized_issues, ensure_ascii=False)}\n"
        f"输出 Schema：{_schema(SupervisionReport)}"
    )
    return system, user
