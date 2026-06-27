from __future__ import annotations

from .models import FactorCode, StuckCategory, Amplifier
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


# ---- V2 类别追问 ----

CATEGORY_PROBE_OPTIONS: dict[StuckCategory, list[UIOption]] = {
    StuckCategory.A_CONCEPT: [
        UIOption(id='cat_A_knows_nothing', label='题目一出现，就不知道这些概念是什么意思'),
        UIOption(id='cat_A_knows_formula', label='能说出公式，但不知道为什么要这样用'),
        UIOption(id='cat_A_understands_answer', label='看答案能懂，自己做又不会'),
        UIOption(id='cat_A_unsure', label='不确定'),
    ],
    StuckCategory.B_RULE_BOUNDARY: [
        UIOption(id='cat_B_rule_wrong', label='规则或定律本身记错了'),
        UIOption(id='cat_B_rule_when', label='规则记得，但不知道什么时候能用'),
        UIOption(id='cat_B_rule_variant', label='题目稍微换个问法，就不知道该用哪条'),
        UIOption(id='cat_B_rule_confident_wrong', label='做错时往往还觉得自己是对的'),
        UIOption(id='cat_B_unsure', label='不确定'),
    ],
    StuckCategory.C_INFO_SYMBOL: [
        UIOption(id='cat_C_miss_read', label='读题时，限制词、单位、条件没注意到'),
        UIOption(id='cat_C_miss_list', label='列式或画图时，条件看到了但没放进去'),
        UIOption(id='cat_C_miss_diagram', label='图形或示意图里的标记、符号容易看漏'),
        UIOption(id='cat_C_miss_midway', label='步骤一多，做到中间忘了前面的条件'),
        UIOption(id='cat_C_unsure', label='不确定'),
    ],
    StuckCategory.D_EXECUTION: [
        UIOption(id='cat_D_basic_ops', label='加减乘除、进退位、借位容易错'),
        UIOption(id='cat_D_sign_paren', label='符号、括号、移项容易漏'),
        UIOption(id='cat_D_decimal_fraction', label='小数点、分数约分、通分容易错'),
        UIOption(id='cat_D_mid_step_miss', label='思路对，但中间总少一步或多一步'),
        UIOption(id='cat_D_unsure', label='不确定'),
    ],
    StuckCategory.E_MODELING: [
        UIOption(id='cat_E_cant_read', label='题目读不进去，不知道已知什么'),
        UIOption(id='cat_E_cant_formulate', label='知道题目说了什么，但不会列式或画图'),
        UIOption(id='cat_E_wrong_relation', label='能列式，但列出来的关系总不对'),
        UIOption(id='cat_E_template_only', label='例题会，换成生活题或综合题就不会'),
        UIOption(id='cat_E_unsure', label='不确定'),
    ],
}

AMPLIFIER_PROBE_OPTIONS: dict[Amplifier, list[UIOption]] = {
    Amplifier.F_FIX_LOOP: [
        UIOption(id='amp_F_find_breakpoint', label='能自己找到第一处错在哪里'),
        UIOption(id='amp_F_read_answer', label='看完整答案后觉得自己懂了'),
        UIOption(id='amp_F_parent_explain', label='家长或大人会直接讲完整解法'),
        UIOption(id='amp_F_redo_similar', label='立刻再刷类似题'),
        UIOption(id='amp_F_ai_search', label='很快找 AI 或搜答案'),
        UIOption(id='amp_F_unsure', label='不确定'),
    ],
    Amplifier.G_EXAM_PACE: [
        UIOption(id='amp_G_homework_ok_exam_fail', label='平时会，考试就错'),
        UIOption(id='amp_G_first_half_ok', label='前半卷还可以，后半卷明显乱'),
        UIOption(id='amp_G_stuck_affects', label='一道题卡住就影响后面的题'),
        UIOption(id='amp_G_time_short', label='时间总是不够'),
        UIOption(id='amp_G_always_unstable', label='平时也不稳'),
        UIOption(id='amp_G_unsure', label='不确定'),
    ],
    Amplifier.H_AVOIDANCE: [
        UIOption(id='amp_H_try_first', label='先自己试一下再来问'),
        UIOption(id='amp_H_instant_answer', label='一卡住就马上找答案或 AI'),
        UIOption(id='amp_H_frustrated', label='一错就烦，不愿再看'),
        UIOption(id='amp_H_afraid', label='怕被批评，不愿说自己不会'),
        UIOption(id='amp_H_no_avoidance', label='还没有明显回避'),
    ],
}


def category_probe(category: StuckCategory) -> UIBlock:
    '''V2：按主卡点类别给关键追问'''
    options = CATEGORY_PROBE_OPTIONS.get(category, CATEGORY_PROBE_OPTIONS[StuckCategory.D_EXECUTION])
    titles = {
        StuckCategory.A_CONCEPT: '孩子遇到这类题时，更像哪一种？',
        StuckCategory.B_RULE_BOUNDARY: '孩子做错的时候，更像哪一种？',
        StuckCategory.C_INFO_SYMBOL: '这种错最常发生在哪一刻？',
        StuckCategory.D_EXECUTION: '你看到的计算错误，更像哪一种？',
        StuckCategory.E_MODELING: '孩子卡住时，更像哪一种？',
    }
    return UIBlock(
        id='category_probe',
        type=UIBlockType.SINGLE_CHOICE,
        title=titles.get(category, '更像哪一种？'),
        options=list(options),
        allow_skip=True,
    )


def amplifier_probe(amplifier: Amplifier) -> UIBlock:
    '''V2：按放大器类别给追问'''
    options = AMPLIFIER_PROBE_OPTIONS.get(amplifier, [])
    titles = {
        Amplifier.F_FIX_LOOP: '孩子做错以后，通常最像哪一种？',
        Amplifier.G_EXAM_PACE: '平时作业和考试相比，差别更像哪一种？',
        Amplifier.H_AVOIDANCE: '孩子遇到难题时，更像哪一种？',
    }
    return UIBlock(
        id='amplifier_probe',
        type=UIBlockType.SINGLE_CHOICE,
        title=titles.get(amplifier, '更像哪一种？'),
        options=list(options),
        allow_skip=True,
    )
