from __future__ import annotations

from collections import defaultdict
import re

from .models import FactorCode, Subject


OPTION_WEIGHTS: dict[str, dict[FactorCode, float]] = {
    "concern_understand_but_cannot_solve": {
        FactorCode.F05_MODEL_TRANSFER: 2,
        FactorCode.F04_REPRESENTATION: 1,
    },
    "concern_repeated_wrong": {
        FactorCode.F07_METACOGNITION: 1.5,
        FactorCode.F08_STRATEGY: 1.5,
        FactorCode.F06_EXECUTION: 1,
    },
    "concern_ai_answer_machine": {
        FactorCode.F10_SUPPORT_AI: 2.5,
        FactorCode.F08_STRATEGY: 1,
    },
    "concern_parent_help_gets_worse": {
        FactorCode.F10_SUPPORT_AI: 2,
        FactorCode.F09_EMOTION: 1,
    },
    "concern_unclear": {
        FactorCode.F07_METACOGNITION: 1,
    },
    "subject_math": {},
    "subject_physics": {},
    "subject_chemistry": {},
    "stuck_read_problem": {FactorCode.F03_LANGUAGE_SYMBOL: 3, FactorCode.F07_METACOGNITION: 1},
    "stuck_concept_formula": {FactorCode.F02_CONCEPT: 3, FactorCode.F01_PRIOR_KNOWLEDGE: 1},
    "stuck_transform": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "stuck_select_method": {FactorCode.F05_MODEL_TRANSFER: 3, FactorCode.F04_REPRESENTATION: 1},
    "stuck_execution": {FactorCode.F06_EXECUTION: 3, FactorCode.F07_METACOGNITION: 1, FactorCode.F11_ATTENTION_EXECUTIVE: 1},
    "stuck_repeat_after_answer": {FactorCode.F07_METACOGNITION: 2, FactorCode.F08_STRATEGY: 3},
    "stuck_emotional_avoidance": {FactorCode.F09_EMOTION: 3},
    "stuck_attention_overload": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F06_EXECUTION: 1},
    "stuck_confident_wrong_idea": {FactorCode.F12_MISCONCEPTION: 3, FactorCode.F02_CONCEPT: 1},
    "parent_explain_full_solution": {FactorCode.F10_SUPPORT_AI: 3, FactorCode.F08_STRATEGY: 1},
    "parent_add_more_exercises": {FactorCode.F08_STRATEGY: 2, FactorCode.F10_SUPPORT_AI: 1},
    "parent_ask_breakpoint": {FactorCode.F07_METACOGNITION: -1, FactorCode.F10_SUPPORT_AI: -1},
    "parent_ai_gives_answer": {FactorCode.F10_SUPPORT_AI: 3, FactorCode.F08_STRATEGY: 2},
    "parent_review_then_retest": {FactorCode.F08_STRATEGY: -1, FactorCode.F07_METACOGNITION: -1},
    "child_does_not_understand_question": {FactorCode.F03_LANGUAGE_SYMBOL: 3},
    "child_cannot_draw_or_formulate": {FactorCode.F04_REPRESENTATION: 3},
    "child_cannot_choose_formula": {FactorCode.F05_MODEL_TRANSFER: 3},
    "child_calculation_or_units_messy": {FactorCode.F06_EXECUTION: 3},
    "child_understands_answer_then_forgets": {FactorCode.F07_METACOGNITION: 2, FactorCode.F08_STRATEGY: 2},
    "math_same_template_ok_variant_fail": {FactorCode.F05_MODEL_TRANSFER: 3},
    "math_symbol_condition_missed": {FactorCode.F03_LANGUAGE_SYMBOL: 2, FactorCode.F04_REPRESENTATION: 2},
    "math_multi_condition_overload": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F03_LANGUAGE_SYMBOL: 1},
    "physics_no_diagram": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "physics_formula_without_quantity_meaning": {FactorCode.F02_CONCEPT: 2, FactorCode.F05_MODEL_TRANSFER: 2},
    "physics_naive_force_motion": {FactorCode.F12_MISCONCEPTION: 3, FactorCode.F02_CONCEPT: 1},
    "physics_direction_sign_confusion": {FactorCode.F06_EXECUTION: 2, FactorCode.F11_ATTENTION_EXECUTIVE: 1},
    "chem_symbol_equation_mismatch": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F03_LANGUAGE_SYMBOL: 1},
    "chem_rule_cannot_transfer": {FactorCode.F05_MODEL_TRANSFER: 3},
    "chem_conservation_or_valence_misconception": {FactorCode.F12_MISCONCEPTION: 3, FactorCode.F02_CONCEPT: 1},
    "probe_template_ok_variant_fail": {FactorCode.F05_MODEL_TRANSFER: 3},
    "probe_knows_relation_not_formula": {FactorCode.F05_MODEL_TRANSFER: 2, FactorCode.F04_REPRESENTATION: 1},
    "probe_text_to_diagram_hard": {FactorCode.F04_REPRESENTATION: 3},
    "probe_diagram_to_formula_hard": {FactorCode.F04_REPRESENTATION: 2, FactorCode.F05_MODEL_TRANSFER: 1},
    "probe_ai_answer_first": {FactorCode.F10_SUPPORT_AI: 3, FactorCode.F08_STRATEGY: 1},
    "probe_parent_takes_over": {FactorCode.F10_SUPPORT_AI: 2, FactorCode.F07_METACOGNITION: 1},
    "probe_cannot_name_breakpoint": {FactorCode.F07_METACOGNITION: 3},
    "probe_only_reads_answer": {FactorCode.F08_STRATEGY: 3, FactorCode.F07_METACOGNITION: 1},
    "probe_emotion_blocks_start": {FactorCode.F09_EMOTION: 3},
    "probe_many_conditions_overload": {FactorCode.F11_ATTENTION_EXECUTIVE: 3},
    "probe_confident_but_wrong_rule": {FactorCode.F12_MISCONCEPTION: 3},
}


SUBJECT_PRIORS: dict[Subject, dict[FactorCode, float]] = {
    Subject.MATH: {
        FactorCode.F04_REPRESENTATION: 0.3,
        FactorCode.F05_MODEL_TRANSFER: 0.3,
        FactorCode.F06_EXECUTION: 0.2,
        FactorCode.F11_ATTENTION_EXECUTIVE: 0.2,
    },
    Subject.PHYSICS: {
        FactorCode.F04_REPRESENTATION: 0.4,
        FactorCode.F05_MODEL_TRANSFER: 0.4,
        FactorCode.F02_CONCEPT: 0.2,
        FactorCode.F12_MISCONCEPTION: 0.2,
    },
    Subject.CHEMISTRY: {
        FactorCode.F03_LANGUAGE_SYMBOL: 0.3,
        FactorCode.F04_REPRESENTATION: 0.4,
        FactorCode.F01_PRIOR_KNOWLEDGE: 0.2,
        FactorCode.F12_MISCONCEPTION: 0.2,
    },
    Subject.UNKNOWN: {},
}


FACTOR_PUBLIC_LABELS: dict[FactorCode, str] = {
    FactorCode.F01_PRIOR_KNOWLEDGE: "前置知识缺口",
    FactorCode.F02_CONCEPT: "概念理解不稳",
    FactorCode.F03_LANGUAGE_SYMBOL: "学科语言与符号理解困难",
    FactorCode.F04_REPRESENTATION: "表征转换困难",
    FactorCode.F05_MODEL_TRANSFER: "建模与迁移困难",
    FactorCode.F06_EXECUTION: "程序执行不稳定",
    FactorCode.F07_METACOGNITION: "元认知与复盘薄弱",
    FactorCode.F08_STRATEGY: "学习策略低效",
    FactorCode.F09_EMOTION: "情绪动机与自我效能受损",
    FactorCode.F10_SUPPORT_AI: "家庭支持与 AI 使用失位",
    FactorCode.F11_ATTENTION_EXECUTIVE: "注意与工作记忆负荷过高",
    FactorCode.F12_MISCONCEPTION: "错误概念或朴素经验干扰",
}


FACTOR_ACTIONS: dict[FactorCode, dict[str, str]] = {
    FactorCode.F01_PRIOR_KNOWLEDGE: {
        "stop": "先不要直接加新题量。",
        "start": "选一道卡住的题，倒查它需要调用的旧知识，只补最小缺口。",
        "mistake": "把新内容学不稳误认为孩子不努力。",
    },
    FactorCode.F02_CONCEPT: {
        "stop": "先不要只让孩子背定义和公式。",
        "start": "让孩子用自己的话解释概念，并举一个反例或生活例子。",
        "mistake": "以为会背公式就等于理解了。",
    },
    FactorCode.F03_LANGUAGE_SYMBOL: {
        "stop": "先不要急着讲解法。",
        "start": "让孩子圈出题干关键词、符号和单位，先确认读题没有偏差。",
        "mistake": "忽略题干语言和符号误读。",
    },
    FactorCode.F04_REPRESENTATION: {
        "stop": "先不要直接代公式。",
        "start": "每题先做一句话到图、图到式子的转换练习。",
        "mistake": "跳过画图、列关系和表征转换。",
    },
    FactorCode.F05_MODEL_TRANSFER: {
        "stop": "先不要讲完整解法或刷同类题。",
        "start": "让孩子说出题目中哪些量有关，以及为什么选择这个方法。",
        "mistake": "把建模迁移困难当成题量不够。",
    },
    FactorCode.F06_EXECUTION: {
        "stop": "先不要只批评粗心。",
        "start": "固定检查清单：审题条件、步骤、单位、计算、答案回看。",
        "mistake": "把可训练的流程问题都归成粗心。",
    },
    FactorCode.F07_METACOGNITION: {
        "stop": "先不要替孩子总结哪里不会。",
        "start": "每次只要求孩子标出第一处断点：从哪一句、哪一步开始不会。",
        "mistake": "父母替孩子复盘，孩子自己没有看见断点。",
    },
    FactorCode.F08_STRATEGY: {
        "stop": "先不要只看答案或机械刷题。",
        "start": "建立 48 小时复测：看懂答案后隔天独立重做。",
        "mistake": "把看懂答案当成真正掌握。",
    },
    FactorCode.F09_EMOTION: {
        "stop": "先不要在情绪高点继续追问和讲题。",
        "start": "降低任务颗粒度，只处理一道题中的一个断点。",
        "mistake": "把回避和怕错简单理解成态度问题。",
    },
    FactorCode.F10_SUPPORT_AI: {
        "stop": "先不要让父母或 AI 直接给完整答案。",
        "start": "把 AI 改成追问者：先问孩子从哪一步不会，再生成复测题。",
        "mistake": "用更强的讲解和监督替代孩子思考。",
    },
    FactorCode.F11_ATTENTION_EXECUTIVE: {
        "stop": "先不要一次讲完整道综合题。",
        "start": "把题目拆成条件清单、目标量、第一步三个小格，让孩子每次只处理一格。",
        "mistake": "把工作记忆过载误认为孩子粗心或不认真。",
    },
    FactorCode.F12_MISCONCEPTION: {
        "stop": "先不要只纠正答案或套公式。",
        "start": "让孩子先说出自己的判断理由，再用一个反例或小实验把错误概念显出来。",
        "mistake": "只讲正确规则，没有先看见孩子原来的错误理解。",
    },
}


OPTION_PUBLIC_LABELS: dict[str, str] = {
    "concern_understand_but_cannot_solve": "课堂像是听懂了，一做题就不会启动",
    "concern_repeated_wrong": "错题反复错，看答案懂了下次又不会",
    "concern_ai_answer_machine": "孩子一遇到难题就想让 AI 给答案",
    "concern_parent_help_gets_worse": "父母越帮越累，关系也更紧",
    "concern_unclear": "说不清，只觉得最近理科越来越不稳",
    "subject_math": "数学",
    "subject_physics": "物理",
    "subject_chemistry": "化学",
    "stuck_read_problem": "读题或关键词不确定",
    "stuck_concept_formula": "概念或公式说不清",
    "stuck_transform": "画图、列式或转化困难",
    "stuck_select_method": "不知道选哪个方法或公式",
    "stuck_execution": "步骤、计算、单位或检查不稳",
    "stuck_repeat_after_answer": "看懂答案后过两天又不会",
    "stuck_emotional_avoidance": "一看到题就烦、急或想逃",
    "stuck_attention_overload": "条件一多就乱、丢条件或跳步骤",
    "stuck_confident_wrong_idea": "孩子很笃定，但判断规则本身错了",
    "parent_explain_full_solution": "父母直接讲完整解法",
    "parent_add_more_exercises": "父母倾向加题量",
    "parent_ask_breakpoint": "父母会问孩子从哪一步不会",
    "parent_ai_gives_answer": "AI 或大人较快给完整答案",
    "parent_review_then_retest": "会复盘并隔天复测",
    "child_does_not_understand_question": "孩子说题目读完就不知道在问什么",
    "child_cannot_draw_or_formulate": "孩子知道题意但不会画图或列式",
    "child_cannot_choose_formula": "孩子不知道选哪个公式或方法",
    "child_calculation_or_units_messy": "孩子代入、单位或计算混乱",
    "child_understands_answer_then_forgets": "孩子看懂答案但下次还是不会",
    "math_same_template_ok_variant_fail": "数学例题同款能做，变式不会",
    "math_symbol_condition_missed": "数学题干条件、符号或图形关系常漏掉",
    "math_multi_condition_overload": "数学多条件题容易丢条件或乱套关系",
    "physics_no_diagram": "物理不画过程图、受力图或电路图就套公式",
    "physics_formula_without_quantity_meaning": "物理公式会背但量的意义说不清",
    "physics_naive_force_motion": "物理中被直觉经验带偏",
    "physics_direction_sign_confusion": "物理方向、正负号或单位容易混乱",
    "chem_symbol_equation_mismatch": "化学现象、粒子变化和方程式对不上",
    "chem_rule_cannot_transfer": "化学反应规律换到新物质就不会用",
    "chem_conservation_or_valence_misconception": "化学守恒、化合价或微粒观念理解偏了",
    "probe_template_ok_variant_fail": "例题同款能做，换情境就不会",
    "probe_knows_relation_not_formula": "知道大概有关，但说不清量之间怎么连起来",
    "probe_text_to_diagram_hard": "题目文字转不成图、式子或关系",
    "probe_diagram_to_formula_hard": "图或关系有了，但不知道用哪个公式或方法",
    "probe_ai_answer_first": "AI 或大人很快给完整答案",
    "probe_parent_takes_over": "父母会接管思路，孩子主要听",
    "probe_cannot_name_breakpoint": "孩子说不清第一处断点",
    "probe_only_reads_answer": "看懂答案，但很少隔天独立重做",
    "probe_emotion_blocks_start": "明显烦躁、紧张或直接逃开",
    "probe_many_conditions_overload": "条件一多就乱，容易丢条件或跳步骤",
    "probe_confident_but_wrong_rule": "孩子很有把握，但用的是错误规则或直觉",
}


def accumulate_scores(subject: Subject, option_ids: list[str]) -> dict[FactorCode, float]:
    scores: dict[FactorCode, float] = defaultdict(float)
    for factor, value in SUBJECT_PRIORS.get(subject, {}).items():
        scores[factor] += value

    for option_id in option_ids:
        for factor, value in OPTION_WEIGHTS.get(option_id, {}).items():
            scores[factor] += value

    return dict(scores)


TEXT_SIGNAL_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"听懂|听得懂|课堂.*懂|课上.*懂"), ["concern_understand_but_cannot_solve"]),
    (re.compile(r"不会做|做不出来|不会启动|无从下手|不知道.*开始"), ["stuck_select_method"]),
    (re.compile(r"错题|反复错|总错|下次.*不会|看答案.*懂"), ["concern_repeated_wrong", "stuck_repeat_after_answer"]),
    (re.compile(r"AI|豆包|DeepSeek|ChatGPT|答案"), ["concern_ai_answer_machine", "parent_ai_gives_answer"]),
    (re.compile(r"我.*讲|直接讲|讲完整|完整解法"), ["parent_explain_full_solution"]),
    (re.compile(r"关系|建模|模型|公式.*选|选.*公式|方法.*选"), ["stuck_select_method"]),
    (re.compile(r"画图|受力图|过程图|电路图|列式|转化"), ["stuck_transform"]),
    (re.compile(r"计算|单位|步骤|检查|粗心"), ["stuck_execution"]),
    (re.compile(r"条件.*多|综合题.*乱|丢条件|漏条件|记不住|一下.*乱"), ["stuck_attention_overload", "probe_many_conditions_overload"]),
    (re.compile(r"想当然|很有把握.*错|很笃定.*错|理解.*偏|概念.*错|直觉"), ["stuck_confident_wrong_idea", "probe_confident_but_wrong_rule"]),
    (re.compile(r"方向|正负号|符号.*乱"), ["physics_direction_sign_confusion"]),
    (re.compile(r"烦|急|崩|哭|逃|不想|抗拒|关系.*紧|吵"), ["concern_parent_help_gets_worse", "stuck_emotional_avoidance"]),
]


def infer_subject_from_text(text: str) -> Subject:
    if re.search(r"数学|函数|几何|方程|代数|证明", text):
        return Subject.MATH
    if re.search(r"物理|受力|电路|力学|压强|浮力|运动|能量", text):
        return Subject.PHYSICS
    if re.search(r"化学|方程式|配平|离子|化合价|酸碱盐|实验", text):
        return Subject.CHEMISTRY
    return Subject.UNKNOWN


def infer_option_ids_from_text(text: str) -> list[str]:
    option_ids: list[str] = []
    for pattern, ids in TEXT_SIGNAL_PATTERNS:
        if pattern.search(text):
            option_ids.extend(ids)
    return list(dict.fromkeys(option_ids))
