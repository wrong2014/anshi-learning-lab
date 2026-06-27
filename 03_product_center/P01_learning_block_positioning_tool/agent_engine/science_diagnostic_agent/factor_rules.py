from __future__ import annotations

from collections import defaultdict
import re

from .models import (
    FactorCode, Subject,
    StuckCategory, Amplifier,
    CATEGORY_LABELS, AMPLIFIER_LABELS,
    FACTOR_TO_CATEGORY, FACTOR_TO_AMPLIFIER,
)


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
    # P1 新增：6 个缺失因子的自适应追问权重
    "probe_can_recite_not_explain": {FactorCode.F02_CONCEPT: 3},
    "probe_confuses_similar_concepts": {FactorCode.F02_CONCEPT: 2, FactorCode.F01_PRIOR_KNOWLEDGE: 1},
    "probe_cannot_give_example": {FactorCode.F02_CONCEPT: 3, FactorCode.F04_REPRESENTATION: 1},
    "probe_misreads_keyword": {FactorCode.F03_LANGUAGE_SYMBOL: 3},
    "probe_cannot_parse_diagram": {FactorCode.F03_LANGUAGE_SYMBOL: 2, FactorCode.F04_REPRESENTATION: 2},
    "probe_symbol_confusion": {FactorCode.F03_LANGUAGE_SYMBOL: 3, FactorCode.F02_CONCEPT: 1},
    "probe_calculation_error": {FactorCode.F06_EXECUTION: 3, FactorCode.F11_ATTENTION_EXECUTIVE: 1},
    "probe_skip_steps": {FactorCode.F06_EXECUTION: 3, FactorCode.F07_METACOGNITION: 1},
    "probe_no_check": {FactorCode.F06_EXECUTION: 2, FactorCode.F08_STRATEGY: 2},
    "probe_simple_ok_complex_fail": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "probe_loses_condition": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F03_LANGUAGE_SYMBOL: 1},
    "probe_mid_step_forget": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F06_EXECUTION: 1},
    "probe_wrong_causal": {FactorCode.F12_MISCONCEPTION: 3, FactorCode.F02_CONCEPT: 1},
    "probe_intuitive_rule": {FactorCode.F12_MISCONCEPTION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "probe_previous_mislearn": {FactorCode.F12_MISCONCEPTION: 2, FactorCode.F01_PRIOR_KNOWLEDGE: 2},
    "probe_forgot_previous": {FactorCode.F01_PRIOR_KNOWLEDGE: 3},
    "probe_knows_but_cant_use": {FactorCode.F01_PRIOR_KNOWLEDGE: 2, FactorCode.F05_MODEL_TRANSFER: 2},
    "probe_gap_specific_topic": {FactorCode.F01_PRIOR_KNOWLEDGE: 2, FactorCode.F12_MISCONCEPTION: 1},
    # P3 动态学科探针权重 — 数学
    "math_calc_carry_borrow": {FactorCode.F06_EXECUTION: 3},
    "math_calc_miscopy": {FactorCode.F06_EXECUTION: 2, FactorCode.F11_ATTENTION_EXECUTIVE: 2},
    "math_calc_decimal_point": {FactorCode.F06_EXECUTION: 3, FactorCode.F02_CONCEPT: 1},
    "math_calc_multistep_break": {FactorCode.F06_EXECUTION: 2, FactorCode.F11_ATTENTION_EXECUTIVE: 2},
    "math_concept_recite_only": {FactorCode.F02_CONCEPT: 3},
    "math_concept_confuse": {FactorCode.F02_CONCEPT: 3, FactorCode.F01_PRIOR_KNOWLEDGE: 1},
    "math_concept_real_meaning": {FactorCode.F02_CONCEPT: 3, FactorCode.F07_METACOGNITION: 1},
    "math_read_miss_condition": {FactorCode.F03_LANGUAGE_SYMBOL: 3, FactorCode.F11_ATTENTION_EXECUTIVE: 1},
    "math_read_unsure_keyword": {FactorCode.F03_LANGUAGE_SYMBOL: 3},
    "math_read_not_understand_ask": {FactorCode.F03_LANGUAGE_SYMBOL: 3, FactorCode.F07_METACOGNITION: 1},
    "math_trans_text_to_expr": {FactorCode.F04_REPRESENTATION: 3},
    "math_trans_cant_draw": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "math_trans_table_relation": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "math_method_no_idea": {FactorCode.F05_MODEL_TRANSFER: 3},
    "math_method_unsure": {FactorCode.F05_MODEL_TRANSFER: 3, FactorCode.F07_METACOGNITION: 1},
    "math_method_right_but_why": {FactorCode.F05_MODEL_TRANSFER: 2, FactorCode.F02_CONCEPT: 2},
    "math_repeat_same_ok_variant_fail": {FactorCode.F05_MODEL_TRANSFER: 2, FactorCode.F08_STRATEGY: 2},
    "math_repeat_understand_then_forget": {FactorCode.F08_STRATEGY: 3, FactorCode.F07_METACOGNITION: 1},
    "math_repeat_only_cram": {FactorCode.F08_STRATEGY: 3},
    "math_attn_multi_condition": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F03_LANGUAGE_SYMBOL: 1},
    "math_attn_composite": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "math_attn_midway_forget": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F06_EXECUTION: 1},
    "math_wrong_causal_direction": {FactorCode.F12_MISCONCEPTION: 3, FactorCode.F02_CONCEPT: 1},
    "math_wrong_intuitive_rule": {FactorCode.F12_MISCONCEPTION: 3},
    "math_wrong_previous_misunderstand": {FactorCode.F12_MISCONCEPTION: 2, FactorCode.F01_PRIOR_KNOWLEDGE: 2},
    # P3 动态学科探针权重 — 物理
    "phys_calc_unit_direction": {FactorCode.F06_EXECUTION: 3, FactorCode.F11_ATTENTION_EXECUTIVE: 1},
    "phys_calc_formula_sub": {FactorCode.F06_EXECUTION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "phys_calc_multistep_lost": {FactorCode.F06_EXECUTION: 2, FactorCode.F11_ATTENTION_EXECUTIVE: 2},
    "phys_concept_formula_no_meaning": {FactorCode.F02_CONCEPT: 2, FactorCode.F05_MODEL_TRANSFER: 2},
    "phys_concept_naive_theory": {FactorCode.F12_MISCONCEPTION: 3, FactorCode.F02_CONCEPT: 1},
    "phys_concept_cant_explain": {FactorCode.F02_CONCEPT: 3, FactorCode.F07_METACOGNITION: 1},
    "phys_read_miss_condition": {FactorCode.F03_LANGUAGE_SYMBOL: 3},
    "phys_read_unsure_scene": {FactorCode.F03_LANGUAGE_SYMBOL: 2, FactorCode.F04_REPRESENTATION: 2},
    "phys_trans_no_diagram": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "phys_trans_scene_to_model": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "phys_method_no_idea": {FactorCode.F05_MODEL_TRANSFER: 3},
    "phys_method_confuse_law": {FactorCode.F05_MODEL_TRANSFER: 3, FactorCode.F02_CONCEPT: 1},
    "phys_repeat_template_ok": {FactorCode.F05_MODEL_TRANSFER: 2, FactorCode.F08_STRATEGY: 2},
    "phys_repeat_forget_quickly": {FactorCode.F08_STRATEGY: 3, FactorCode.F07_METACOGNITION: 1},
    "phys_attn_multi_object": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F04_REPRESENTATION: 1},
    "phys_attn_composite": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "phys_wrong_force_motion": {FactorCode.F12_MISCONCEPTION: 3},
    "phys_wrong_current_consumed": {FactorCode.F12_MISCONCEPTION: 3},
    # P3 动态学科探针权重 — 化学
    "chem_calc_balance": {FactorCode.F06_EXECUTION: 3, FactorCode.F04_REPRESENTATION: 1},
    "chem_calc_valence": {FactorCode.F06_EXECUTION: 3, FactorCode.F02_CONCEPT: 1},
    "chem_calc_mole_mass": {FactorCode.F06_EXECUTION: 3, FactorCode.F04_REPRESENTATION: 1},
    "chem_concept_particle_confuse": {FactorCode.F02_CONCEPT: 3, FactorCode.F12_MISCONCEPTION: 1},
    "chem_concept_conservation": {FactorCode.F02_CONCEPT: 3, FactorCode.F12_MISCONCEPTION: 1},
    "chem_read_miss_condition": {FactorCode.F03_LANGUAGE_SYMBOL: 3},
    "chem_read_unsure_symbol": {FactorCode.F03_LANGUAGE_SYMBOL: 3},
    "chem_trans_macro_micro": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F03_LANGUAGE_SYMBOL: 1},
    "chem_trans_equation_to_scene": {FactorCode.F04_REPRESENTATION: 3, FactorCode.F05_MODEL_TRANSFER: 1},
    "chem_method_no_idea": {FactorCode.F05_MODEL_TRANSFER: 3},
    "chem_method_cant_transfer": {FactorCode.F05_MODEL_TRANSFER: 3},
    "chem_repeat_template_ok": {FactorCode.F05_MODEL_TRANSFER: 2, FactorCode.F08_STRATEGY: 2},
    "chem_repeat_forget_quickly": {FactorCode.F08_STRATEGY: 3, FactorCode.F07_METACOGNITION: 1},
    "chem_attn_multi_step": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F06_EXECUTION: 1},
    "chem_attn_mix_calc": {FactorCode.F11_ATTENTION_EXECUTIVE: 3, FactorCode.F04_REPRESENTATION: 1},
    "chem_wrong_valence_misconception": {FactorCode.F12_MISCONCEPTION: 3},
    "chem_wrong_reaction_rule": {FactorCode.F12_MISCONCEPTION: 3},
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
    # P1 新增标签
    "probe_can_recite_not_explain": "能背定义公式但不能用自己的话解释",
    "probe_confuses_similar_concepts": "容易混淆相似概念",
    "probe_cannot_give_example": "举不出生活中的例子或反例",
    "probe_misreads_keyword": "关键词、条件或单位常看错",
    "probe_cannot_parse_diagram": "题目里的图表看不懂或漏信息",
    "probe_symbol_confusion": "符号或术语容易搞混",
    "probe_calculation_error": "计算或单位转换常出错",
    "probe_skip_steps": "步骤跳太快，中间缺了关键一步",
    "probe_no_check": "做完不检查或检查也看不出来",
    "probe_simple_ok_complex_fail": "简单题没问题，综合题就乱",
    "probe_loses_condition": "多条件时经常漏掉一两个",
    "probe_mid_step_forget": "做到一半忘了前面算什么",
    "probe_wrong_causal": "因果方向搞反了",
    "probe_intuitive_rule": "用生活直觉代替学科规则",
    "probe_previous_mislearn": "之前学的内容本身就理解错了",
    "probe_forgot_previous": "之前学过的内容忘了",
    "probe_knows_but_cant_use": "知道学过但想不起来怎么用",
    "probe_gap_specific_topic": "只有某个特定章节/知识点有问题",
    # P3 动态探针标签 — 数学
    "math_calc_carry_borrow": "进退位、借位容易错",
    "math_calc_miscopy": "抄错数字、符号或漏写",
    "math_calc_decimal_point": "小数点、分数约分常出错",
    "math_calc_multistep_break": "多步计算中间某步断掉或记错",
    "math_concept_recite_only": "公式定义会背但不会解释",
    "math_concept_confuse": "容易混淆相似概念或公式",
    "math_concept_real_meaning": "说不清算式每一步在算什么",
    "math_read_miss_condition": "漏看条件、数字或单位",
    "math_read_unsure_keyword": "不确定关键词意思",
    "math_read_not_understand_ask": "读完不知道题目到底问什么",
    "math_trans_text_to_expr": "文字描述转不成算式或方程",
    "math_trans_cant_draw": "不会画线段图或示意图",
    "math_trans_table_relation": "不会列表格或梳理数量关系",
    "math_method_no_idea": "不知道用什么公式或方法",
    "math_method_unsure": "感觉会用但不确定对不对",
    "math_method_right_but_why": "经常选对但说不清为什么",
    "math_repeat_same_ok_variant_fail": "同款题当时能做换个数就不会",
    "math_repeat_understand_then_forget": "当时说懂过两天完全不记得",
    "math_repeat_only_cram": "主要靠考前突击考完就忘",
    "math_attn_multi_condition": "条件超过3个就开始丢",
    "math_attn_composite": "单独知识点会综合题就乱",
    "math_attn_midway_forget": "做到后面忘了前面算什么",
    "math_wrong_causal_direction": "因果关系搞反了",
    "math_wrong_intuitive_rule": "用生活经验代替数学规则",
    "math_wrong_previous_misunderstand": "之前某个知识点就理解错了",
    # P3 动态探针标签 — 物理
    "phys_calc_unit_direction": "单位、方向、正负号容易搞混",
    "phys_calc_formula_sub": "公式会选但代入数字总出错",
    "phys_calc_multistep_lost": "多步推导中间漏了关键一步",
    "phys_concept_formula_no_meaning": "公式会背但每个量代表什么说不清",
    "phys_concept_naive_theory": "容易被直觉经验带偏",
    "phys_concept_cant_explain": "能算对但讲不出为什么",
    "phys_read_miss_condition": "漏看条件或物理量",
    "phys_read_unsure_scene": "不确定题目描述的是什么场景",
    "phys_trans_no_diagram": "不画受力图或过程图就套公式",
    "phys_trans_scene_to_model": "文字场景转化不成物理模型",
    "phys_method_no_idea": "不知道用哪个公式或定律",
    "phys_method_confuse_law": "混淆相似定律或公式",
    "phys_repeat_template_ok": "同类题能做换个情景就不会",
    "phys_repeat_forget_quickly": "看懂后过两天又不会了",
    "phys_attn_multi_object": "涉及多物体或多过程就乱",
    "phys_attn_composite": "力学电学混合题理不清",
    "phys_wrong_force_motion": "力与运动关系直觉错误",
    "phys_wrong_current_consumed": "认为电流会被用电器消耗",
    # P3 动态探针标签 — 化学
    "chem_calc_balance": "方程式配平容易出错",
    "chem_calc_valence": "化合价或化学式写错",
    "chem_calc_mole_mass": "物质的量或质量计算混乱",
    "chem_concept_particle_confuse": "分不清原子、分子、离子",
    "chem_concept_conservation": "守恒观念没有真正建立",
    "chem_read_miss_condition": "漏看物质状态或反应条件",
    "chem_read_unsure_symbol": "化学式或符号不认识",
    "chem_trans_macro_micro": "宏观现象和微观粒子对不上",
    "chem_trans_equation_to_scene": "方程式和实验场景联系不起来",
    "chem_method_no_idea": "不知道从哪个物质或反应入手",
    "chem_method_cant_transfer": "反应规律换到新物质就不会用",
    "chem_repeat_template_ok": "同类题换物质就不会",
    "chem_repeat_forget_quickly": "看完答案过两天忘",
    "chem_attn_multi_step": "推断流程一多就乱",
    "chem_attn_mix_calc": "实验加计算混合题理不清",
    "chem_wrong_valence_misconception": "化合价或电子观念理解偏差",
    "chem_wrong_reaction_rule": "反应规律用反或套错",
}


def accumulate_scores(subject: Subject, option_ids: list[str], decay_prior: bool = True) -> dict[FactorCode, float]:
    """计算因子得分。

    decay_prior=True（默认）时，学科先验权重随 option 数量衰减：
    每多一个 option 衰减 25%，4 个以上时先验归零，完全由证据驱动。
    """
    scores: dict[FactorCode, float] = defaultdict(float)
    option_count = len(option_ids)

    # P2 修复：先验权重随证据积累衰减
    decay = max(0.0, 1.0 - 0.25 * option_count) if decay_prior else 1.0
    if decay > 0:
        for factor, value in SUBJECT_PRIORS.get(subject, {}).items():
            scores[factor] += value * decay

    for option_id in option_ids:
        for factor, value in OPTION_WEIGHTS.get(option_id, {}).items():
            scores[factor] += value

    return dict(scores)


TEXT_SIGNAL_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = [
    # 概念理解问题 (→ A)
    (re.compile(r"概念.*不懂|概念.*不清|不理解|不知道.*意思|不懂.*概念|概念.*模糊|基础.*不牢|基础.*差|基础.*不稳|没.*理解|理解不了|从来没懂|一直.*不懂|原理.*不懂|定义.*不清|背不下|记不住公式|公式.*意思|讲不清|解释不清|表达不出|说.*不出来"), ["stuck_concept_formula"]),
    # 听懂但不会做
    (re.compile(r"听懂|听得懂|课堂.*懂|课上.*懂"), ["concern_understand_but_cannot_solve"]),
    # 不会启动/选方法 (→ B)
    (re.compile(r"不会做|做不出来|不会启动|无从下手|不知道.*开始|不知道.*选|不知道.*用|选.*哪个|哪个.*公式|哪个.*方法"), ["stuck_select_method"]),
    # 错题反复 (→ F)
    (re.compile(r"错题|反复错|总错|下次.*不会|看答案.*懂"), ["concern_repeated_wrong", "stuck_repeat_after_answer"]),
    # AI/答案依赖 (→ F)
    (re.compile(r"AI|豆包|DeepSeek|ChatGPT|搜答案|查答案"), ["concern_ai_answer_machine", "parent_ai_gives_answer"]),
    # 家长讲完整解法 (→ F)
    (re.compile(r"我.*讲|直接讲|讲完整|完整解法"), ["parent_explain_full_solution"]),
    # 建模/方法选择 (→ B/E)
    (re.compile(r"关系|建模|模型|公式.*选|选.*公式|方法.*选"), ["stuck_select_method"]),
    # 表征转换 (→ C)
    (re.compile(r"画图|受力图|过程图|电路图|列式|转化"), ["stuck_transform"]),
    # 计算执行 (→ D)
    (re.compile(r"计算|单位|步骤|检查|粗心|算错|算不对|加减|乘除|进退位|借位|移项"), ["stuck_execution"]),
    # 应用题/综合题 (→ E)
    (re.compile(r"应用题|综合题|大题|不会.*列|列.*式子|列.*方程|换.*题|变.*题|换个.*就不会|换情境|生活题"), ["stuck_select_method", "math_repeat_same_ok_variant_fail"]),
    # 注意力/多条件 (→ C/D)
    (re.compile(r"条件.*多|综合题.*乱|丢条件|漏条件|记不住|一下.*乱|题目.*长|题干.*长"), ["stuck_attention_overload", "probe_many_conditions_overload"]),
    # 错误概念/直觉 (→ A)
    (re.compile(r"想当然|很有把握.*错|很笃定.*错|理解.*偏|概念.*错|直觉|方向.*反"), ["stuck_confident_wrong_idea", "probe_confident_but_wrong_rule"]),
    # 物理方向符号
    (re.compile(r"方向|正负号|符号.*乱"), ["physics_direction_sign_confusion"]),
    # 情绪/回避 (→ H)
    (re.compile(r"烦|急|崩|哭|逃|不想|抗拒|关系.*紧|吵|怕.*数学|讨厌|紧张|焦虑|没信心"), ["concern_parent_help_gets_worse", "stuck_emotional_avoidance"]),
    # 考试问题 (→ G)
    (re.compile(r"考试.*错|考试.*不会|一考试|平时.*会.*考试|平时.*对.*考试|大考|考场|时间.*不够|来不及|做不完"), ["stuck_execution"]),
    # 读题问题 (→ C)
    (re.compile(r"读题|审题|看题|看错|漏看|看漏|没看到|没注意.*条件|没注意.*单位|题目.*没看清|题目.*理解错|题目.*读错"), ["stuck_read_problem"]),
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


# ---- V2 类别评分 ----

def accumulate_category_scores(
    subject: Subject,
    option_ids: list[str],
    decay_prior: bool = True,
) -> tuple[dict[StuckCategory, float], dict[Amplifier, float]]:
    """V2 类别评分：从旧因子权重聚合为主卡点 + 放大器得分。

    放大器权重系数 0.5，确保不抢主卡点位置。
    返回 (category_scores, amplifier_scores)。
    """
    factor_scores = accumulate_scores(subject, option_ids, decay_prior=decay_prior)
    if not factor_scores:
        factor_scores = {FactorCode.F07_METACOGNITION: 1.0}

    category_scores: dict[StuckCategory, float] = defaultdict(float)
    amplifier_scores: dict[Amplifier, float] = defaultdict(float)

    for factor, score in factor_scores.items():
        cat = FACTOR_TO_CATEGORY.get(factor)
        if cat:
            category_scores[cat] += score
        amp = FACTOR_TO_AMPLIFIER.get(factor)
        if amp:
            amplifier_scores[amp] += score * 0.5

    return dict(category_scores), dict(amplifier_scores)


def top_category(
    subject: Subject,
    option_ids: list[str],
) -> tuple[StuckCategory | None, Amplifier | None]:
    """返回最高分的 (主卡点, 放大器)。"""
    cat_scores, amp_scores = accumulate_category_scores(subject, option_ids)
    if not cat_scores:
        return None, None
    top_cat = max(cat_scores, key=lambda k: cat_scores[k])
    top_amp = max(amp_scores, key=lambda k: amp_scores[k]) if amp_scores else None
    return top_cat, top_amp
