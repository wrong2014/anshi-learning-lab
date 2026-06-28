from __future__ import annotations

from .models import CATEGORY_LABELS, DiagnosticCategory, FactorCode, Subject
from .models import UIBlock, UIBlockType, UIOption


def opening_story_question() -> UIBlock:
    return UIBlock(
        id="opening_story",
        type=UIBlockType.SHORT_TEXT,
        title="最近哪件事最让你担心？",
        body="像发微信一样说一段就行：哪一科，发生了什么，孩子怎么反应，你当时怎么帮。",
        options=[
            UIOption(id="example_1", label="课堂像听懂了，一做题就不会启动"),
            UIOption(id="example_2", label="错题反复错，看答案懂了下次又不会"),
            UIOption(id="example_3", label="孩子一遇到难题就想让 AI 给答案"),
            UIOption(id="example_4", label="我越帮越累，关系也更紧"),
        ],
        allow_skip=False,
    )


def subject_question() -> UIBlock:
    return UIBlock(
        id="subject_select",
        type=UIBlockType.SINGLE_CHOICE,
        title="这件事主要发生在哪一科？",
        body="先固定一科，结果才会更准。其他科目可以下一轮再看。",
        options=[
            UIOption(id="subject_math", label="数学"),
            UIOption(id="subject_physics", label="物理"),
            UIOption(id="subject_chemistry", label="化学"),
        ],
        allow_skip=False,
    )


def recent_scene_question() -> UIBlock:
    return UIBlock(
        id="recent_scene",
        type=UIBlockType.SHORT_TEXT,
        title="用几句话还原最近一次现场",
        body="不用写作文。只说三件事：发生了什么、孩子怎么反应、你当时怎么帮。",
        allow_skip=False,
    )


def stuck_step_question() -> UIBlock:
    return UIBlock(
        id="stuck_step",
        type=UIBlockType.SINGLE_CHOICE,
        title="如果只看这一次，孩子更像卡在哪一步？",
        options=[
            UIOption(id="stuck_read_problem", label="读不懂题 / 关键词不确定"),
            UIOption(id="stuck_concept_formula", label="概念或公式知道，但说不清"),
            UIOption(id="stuck_transform", label="不知道怎么画图、列式或转化"),
            UIOption(id="stuck_select_method", label="不知道选哪个方法或公式"),
            UIOption(id="stuck_execution", label="会做但步骤、计算、单位、检查总出错"),
            UIOption(id="stuck_repeat_after_answer", label="看了答案懂，过两天又不会"),
            UIOption(id="stuck_emotional_avoidance", label="一看到题就烦、急、想逃"),
        ],
        allow_skip=True,
    )


def parent_support_question() -> UIBlock:
    return UIBlock(
        id="parent_support",
        type=UIBlockType.MULTI_CHOICE,
        title="你当时一般会怎么帮？",
        body="这不是判断你对错，而是看支持方式有没有和孩子卡点错位。",
        options=[
            UIOption(id="parent_explain_full_solution", label="直接讲完整解法"),
            UIOption(id="parent_add_more_exercises", label="加题量"),
            UIOption(id="parent_ask_breakpoint", label="让孩子先说从哪一步不会"),
            UIOption(id="parent_ai_gives_answer", label="让 AI 讲答案或直接给答案"),
            UIOption(id="parent_review_then_retest", label="先复盘，再隔天复测"),
        ],
        allow_skip=True,
    )


def child_checkpoint_question() -> UIBlock:
    return UIBlock(
        id="child_checkpoint",
        type=UIBlockType.CHILD_CHECKPOINT,
        title="孩子如果愿意，只补充一句：从哪一步开始不知道怎么往下走？",
        options=[
            UIOption(id="child_does_not_understand_question", label="题目读完就不知道在问什么"),
            UIOption(id="child_cannot_draw_or_formulate", label="知道题意，但不知道怎么画图或列式"),
            UIOption(id="child_cannot_choose_formula", label="知道要用公式，但不知道选哪个"),
            UIOption(id="child_calculation_or_units_messy", label="公式选了，但代入、单位或计算乱"),
            UIOption(id="child_understands_answer_then_forgets", label="答案看懂了，但下次还是不会"),
        ],
        allow_skip=True,
    )


def subject_specific_question(subject_value: str) -> UIBlock:
    if subject_value == "math":
        return UIBlock(
            id="math_probe",
            type=UIBlockType.SINGLE_CHOICE,
            title="数学里更像哪种情况？",
            options=[
                UIOption(id="math_same_template_ok_variant_fail", label="例题同款能做，变式不会"),
                UIOption(id="math_symbol_condition_missed", label="题干条件、符号或图形关系常漏掉"),
            ],
        )
    if subject_value == "physics":
        return UIBlock(
            id="physics_probe",
            type=UIBlockType.SINGLE_CHOICE,
            title="物理里更像哪种情况？",
            options=[
                UIOption(id="physics_no_diagram", label="不画过程图、受力图或电路图就直接套公式"),
                UIOption(id="physics_formula_without_quantity_meaning", label="公式会背，但每个量代表什么说不清"),
            ],
        )
    return UIBlock(
        id="chemistry_probe",
        type=UIBlockType.SINGLE_CHOICE,
        title="化学里更像哪种情况？",
        options=[
            UIOption(id="chem_symbol_equation_mismatch", label="现象、粒子变化和方程式对不上"),
            UIOption(id="chem_rule_cannot_transfer", label="反应规律换到新物质就不会用"),
        ],
    )


def adaptive_probe_question(top_factors: list[FactorCode]) -> UIBlock:
    factor_set = set(top_factors)

    if FactorCode.F10_SUPPORT_AI in factor_set:
        return UIBlock(
            id="adaptive_probe",
            type=UIBlockType.SINGLE_CHOICE,
            title="我再确认一个关键点：孩子卡住时，帮助方式更像哪一种？",
            body="这个问题会影响后面的支持建议。",
            options=[
                UIOption(id="probe_ai_answer_first", label="AI 或大人很快给完整答案"),
                UIOption(id="probe_parent_takes_over", label="父母会接管思路，孩子主要听"),
                UIOption(id="probe_cannot_name_breakpoint", label="孩子说不清自己从哪一步不会"),
                UIOption(id="probe_only_reads_answer", label="主要看懂答案，但缺少隔天复测"),
            ],
            allow_skip=True,
        )

    if FactorCode.F04_REPRESENTATION in factor_set and FactorCode.F05_MODEL_TRANSFER in factor_set:
        return UIBlock(
            id="adaptive_probe",
            type=UIBlockType.SINGLE_CHOICE,
            title="最后区分一下：更像是哪种“不会启动”？",
            options=[
                UIOption(id="probe_text_to_diagram_hard", label="题目文字转不成图、式子或关系"),
                UIOption(id="probe_diagram_to_formula_hard", label="图或关系有了，但不知道用哪个公式/方法"),
                UIOption(id="probe_template_ok_variant_fail", label="例题同款能做，换情境就不会"),
                UIOption(id="probe_knows_relation_not_formula", label="知道大概有关，但说不清量之间怎么连起来"),
            ],
            allow_skip=True,
        )

    if FactorCode.F07_METACOGNITION in factor_set or FactorCode.F08_STRATEGY in factor_set:
        return UIBlock(
            id="adaptive_probe",
            type=UIBlockType.SINGLE_CHOICE,
            title="错题之后通常会发生什么？",
            options=[
                UIOption(id="probe_cannot_name_breakpoint", label="孩子说不清第一处断点"),
                UIOption(id="probe_only_reads_answer", label="看懂答案，但很少隔天独立重做"),
                UIOption(id="probe_template_ok_variant_fail", label="同款题能做，换个说法又不会"),
                UIOption(id="probe_ai_answer_first", label="容易直接让 AI 给答案"),
            ],
            allow_skip=True,
        )

    if FactorCode.F09_EMOTION in factor_set:
        return UIBlock(
            id="adaptive_probe",
            type=UIBlockType.SINGLE_CHOICE,
            title="孩子遇到这类题时，最明显的反应是什么？",
            options=[
                UIOption(id="probe_emotion_blocks_start", label="明显烦躁、紧张或直接逃开"),
                UIOption(id="probe_cannot_name_breakpoint", label="说不清哪里不会，只说不会"),
                UIOption(id="probe_ai_answer_first", label="马上想找答案"),
            ],
            allow_skip=True,
        )

    return UIBlock(
        id="adaptive_probe",
        type=UIBlockType.SINGLE_CHOICE,
        title="最后确认一下：哪句话最像这次卡住？",
        options=[
            UIOption(id="probe_template_ok_variant_fail", label="例题同款能做，变式不会"),
            UIOption(id="probe_text_to_diagram_hard", label="题目转不成图、式子或关系"),
            UIOption(id="probe_cannot_name_breakpoint", label="说不清第一处断点"),
            UIOption(id="probe_only_reads_answer", label="看懂答案，但缺少复测"),
        ],
        allow_skip=True,
    )


_CATEGORY_OPTION_IDS: dict[DiagnosticCategory, str] = {
    DiagnosticCategory.A_FOUNDATION: "category_hint_foundation",
    DiagnosticCategory.B_REPRESENTATION: "category_hint_representation",
    DiagnosticCategory.C_MODELING: "category_hint_modeling",
    DiagnosticCategory.D_EXECUTION: "category_hint_execution",
    DiagnosticCategory.E_SELF_REGULATION: "category_hint_self_regulation",
}


_CATEGORY_HINTS: dict[Subject, dict[DiagnosticCategory, str]] = {
    Subject.MATH: {
        DiagnosticCategory.A_FOUNDATION: "基础概念、公式含义或旧知识本身就不稳",
        DiagnosticCategory.B_REPRESENTATION: "题目条件、符号或图形没有顺利进入列式",
        DiagnosticCategory.C_MODELING: "题意大致明白，但关系建不起来，题一变就不会",
        DiagnosticCategory.D_EXECUTION: "思路可能有了，但运算、符号或多步骤中间出错",
        DiagnosticCategory.E_SELF_REGULATION: "看答案像是懂了，之后仍不会或不愿再碰",
    },
    Subject.PHYSICS: {
        DiagnosticCategory.A_FOUNDATION: "物理量和公式会背，但真正含义或适用条件不清",
        DiagnosticCategory.B_REPRESENTATION: "题目条件没有顺利转成受力图、过程图或电路图",
        DiagnosticCategory.C_MODELING: "场景能读懂，但对象、过程和定律连不起来",
        DiagnosticCategory.D_EXECUTION: "公式大致选对，但单位、方向、代入或多步推导出错",
        DiagnosticCategory.E_SELF_REGULATION: "卡住后很快看答案，之后仍不能独立完成",
    },
    Subject.CHEMISTRY: {
        DiagnosticCategory.A_FOUNDATION: "概念、微粒观念、守恒或化合价本身不稳",
        DiagnosticCategory.B_REPRESENTATION: "现象、粒子变化和符号方程式对不上",
        DiagnosticCategory.C_MODELING: "规律学过，但换物质或实验情境就不会用",
        DiagnosticCategory.D_EXECUTION: "思路大致有了，但配平、关系量或计算步骤出错",
        DiagnosticCategory.E_SELF_REGULATION: "看答案时明白，隔天仍不会或开始回避",
    },
}


def category_candidate_question(
    subject: Subject,
    categories: list[DiagnosticCategory],
) -> UIBlock:
    ordered = list(dict.fromkeys(categories))
    for category in DiagnosticCategory:
        if len(ordered) >= 3:
            break
        if category not in ordered:
            ordered.append(category)

    labels = _CATEGORY_HINTS.get(subject, _CATEGORY_HINTS[Subject.MATH])
    options = [
        UIOption(id=_CATEGORY_OPTION_IDS[category], label=labels[category])
        for category in ordered[:3]
    ]
    return UIBlock(
        id="diagnostic_category_candidates",
        type=UIBlockType.SINGLE_CHOICE,
        title="更像从哪一处开始卡住？",
        body="先选最接近的一项；不确定也可以直接补充。",
        options=options,
        allow_skip=True,
    )


_CATEGORY_PROBES: dict[DiagnosticCategory, list[UIOption]] = {
    DiagnosticCategory.A_FOUNDATION: [
        UIOption(id="probe_foundation_old_knowledge", label="一追问就会牵出以前学过、现在已经不稳的知识"),
        UIOption(id="probe_foundation_explain", label="会背定义或公式，但用自己的话解释不清"),
        UIOption(id="probe_foundation_confident_wrong", label="孩子很确定自己的理解，可规则或因果方向本身错了"),
    ],
    DiagnosticCategory.B_REPRESENTATION: [
        UIOption(id="probe_representation_misread", label="关键词、符号、单位或限制条件没有读准确"),
        UIOption(id="probe_representation_convert", label="题意能复述，但转不成图、式子、方程式或过程关系"),
        UIOption(id="probe_representation_midway_loss", label="条件开始时看到了，做到中间却丢了"),
    ],
    DiagnosticCategory.C_MODELING: [
        UIOption(id="probe_modeling_cannot_start", label="知道题目在说什么，但找不到第一条关系"),
        UIOption(id="probe_modeling_variant", label="例题同款会做，换情境或综合起来就不会"),
        UIOption(id="probe_modeling_method_boundary", label="方法和公式都学过，但不知道此时该选哪一个"),
    ],
    DiagnosticCategory.D_EXECUTION: [
        UIOption(id="probe_execution_repeated_detail", label="同一种符号、运算、单位或步骤错误反复出现"),
        UIOption(id="probe_execution_many_conditions", label="简单步骤能做，条件或步骤一多就乱"),
        UIOption(id="probe_execution_exam_only", label="平时大致会，一到考试或限时就明显失稳"),
    ],
    DiagnosticCategory.E_SELF_REGULATION: [
        UIOption(id="probe_regulation_no_breakpoint", label="错后说不清自己从哪一步开始偏了"),
        UIOption(id="probe_regulation_answer_only", label="看答案时觉得懂了，但之后不能独立重做"),
        UIOption(id="probe_regulation_avoidance", label="一遇到难题就明显烦躁、紧张或不愿继续"),
    ],
}


def category_detail_question(category: DiagnosticCategory) -> UIBlock:
    return UIBlock(
        id="diagnostic_category_detail",
        type=UIBlockType.SINGLE_CHOICE,
        title=f"关于「{CATEGORY_LABELS[category]}」，哪一种最接近？",
        body="这一步用来区分真正该先处理的细节。",
        options=list(_CATEGORY_PROBES[category]),
        allow_skip=True,
    )


def context_amplifier_question() -> UIBlock:
    return UIBlock(
        id="diagnostic_context_check",
        type=UIBlockType.MULTI_CHOICE,
        title="还有哪些情况会让它变得更明显？",
        body="可以多选；这些只是放大因素，不会被当成孩子学不好的根因。",
        options=[
            UIOption(id="context_support_takes_over", label="大人或 AI 很快接过思路并给出完整过程"),
            UIOption(id="context_exam_drop", label="平时作业尚可，考试时错误明显增多"),
            UIOption(id="context_time_pressure", label="时间总是不够，一道题卡住会拖累后面"),
            UIOption(id="context_sleep_short", label="近期睡眠不足、容易困或反应慢"),
            UIOption(id="context_fatigue", label="晚间学习时明显疲劳，状态波动大"),
            UIOption(id="context_none_obvious", label="暂时没有明显情况"),
        ],
        allow_skip=True,
    )
