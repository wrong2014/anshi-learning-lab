"""
诊断结果目录 —— 15 条预设诊断结果模板（3 学科 × 5 类别）及 build_result_payload() 构建函数。
"""
from __future__ import annotations

from typing import Any

from .models import FactorCode, Subject, DiagnosticCategory, AmplifierCode
from .verification_actions import get_verification_action, get_uncertainties

# ---------------------------------------------------------------------------
# 版本号
# ---------------------------------------------------------------------------
RESULT_CATALOG_VERSION = "2.0"

# ---------------------------------------------------------------------------
# 标签映射
# ---------------------------------------------------------------------------
SUBJECT_LABELS: dict[Subject, str] = {
    Subject.MATH: "数学",
    Subject.PHYSICS: "物理",
    Subject.CHEMISTRY: "化学",
}

CATEGORY_LABELS: dict[DiagnosticCategory, str] = {
    DiagnosticCategory.A_FOUNDATION: "基础概念不稳",
    DiagnosticCategory.B_REPRESENTATION: "信息表征卡点",
    DiagnosticCategory.C_MODELING: "建模迁移困难",
    DiagnosticCategory.D_EXECUTION: "执行流程不稳",
    DiagnosticCategory.E_SELF_REGULATION: "自我调节薄弱",
}

CATEGORY_DESCRIPTIONS: dict[DiagnosticCategory, str] = {
    DiagnosticCategory.A_FOUNDATION: (
        "孩子可能看起来在学，但底层概念的理解还没有真正稳固，"
        "导致新内容无法与旧知识建立联系。"
    ),
    DiagnosticCategory.B_REPRESENTATION: (
        "孩子可能看见了题目，却没有把文字、符号、图形和条件"
        "稳定地转成可用的解题信息。"
    ),
    DiagnosticCategory.C_MODELING: (
        "孩子并非完全听不懂，而是还不能独立把情境中的关系搭起来，"
        "所以题目一变就容易失去入口。"
    ),
    DiagnosticCategory.D_EXECUTION: (
        "思路可能已经出现，但步骤、计算、单位或多条件处理"
        "还没有形成稳定流程。"
    ),
    DiagnosticCategory.E_SELF_REGULATION: (
        "卡住之后的定位、复盘和情绪恢复没有形成闭环，"
        "导致当时看懂了也难以变成下一次会做。"
    ),
}

AMPLIFIER_LABELS: dict[AmplifierCode, str] = {
    AmplifierCode.F_REPAIR_LOOP: "错题修复还没形成闭环",
    AmplifierCode.G_EXAM_RHYTHM: "考试过程与节奏问题",
    AmplifierCode.H_AVOIDANCE: "出现了回避或挫败感",
}

# 每个类别对应的默认主因子
DEFAULT_FACTOR_BY_CATEGORY: dict[DiagnosticCategory, FactorCode] = {
    DiagnosticCategory.A_FOUNDATION: FactorCode.F02_CONCEPT,
    DiagnosticCategory.B_REPRESENTATION: FactorCode.F04_REPRESENTATION,
    DiagnosticCategory.C_MODELING: FactorCode.F05_MODEL_TRANSFER,
    DiagnosticCategory.D_EXECUTION: FactorCode.F06_EXECUTION,
    DiagnosticCategory.E_SELF_REGULATION: FactorCode.F07_METACOGNITION,
}

# ---------------------------------------------------------------------------
# 因子行动指南（与 factor_rules.py 中 FACTOR_ACTIONS 保持一致）
# ---------------------------------------------------------------------------
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
}

# ---------------------------------------------------------------------------
# 预览证据（3 学科 × 5 类别 = 15 条）
# ---------------------------------------------------------------------------
_PREVIEW_EVIDENCE: dict[tuple[Subject, DiagnosticCategory], list[str]] = {
    # ── 数学 ──
    (Subject.MATH, DiagnosticCategory.A_FOUNDATION): [
        "公式能背出来，但问为什么这样用时说不清",
        "基础题换一种问法就开始犹豫",
    ],
    (Subject.MATH, DiagnosticCategory.B_REPRESENTATION): [
        "题目条件都读到了，但画不出关系图或列不出式子",
        "数学符号和文字叙述之间的转换经常出错",
    ],
    (Subject.MATH, DiagnosticCategory.C_MODELING): [
        "应用题能复述题意，但列不出数量关系",
        "例题会做，换一个生活情境就不会",
    ],
    (Subject.MATH, DiagnosticCategory.D_EXECUTION): [
        "思路讲得出来，但一动笔就在符号或计算上出错",
        "多步骤的解法到后半段就容易丢条件",
    ],
    (Subject.MATH, DiagnosticCategory.E_SELF_REGULATION): [
        "看答案的时候觉得自己会了，但独立做就不行",
        "不知道自己具体卡在哪一步，只说整道题不会",
    ],

    # ── 物理 ──
    (Subject.PHYSICS, DiagnosticCategory.A_FOUNDATION): [
        "公式会背，但说不清每个物理量代表什么",
        "同一个概念换一种说法就认不出来了",
    ],
    (Subject.PHYSICS, DiagnosticCategory.B_REPRESENTATION): [
        "不画受力图或过程图就直接套公式",
        "题目给了多个物理量，但不知道哪些是有用的",
    ],
    (Subject.PHYSICS, DiagnosticCategory.C_MODELING): [
        "单个过程能分析，多过程串联就理不清",
        "换一个物理场景，之前会的定律就不知道怎么用了",
    ],
    (Subject.PHYSICS, DiagnosticCategory.D_EXECUTION): [
        "公式选对了，但代入数值或单位换算时出错",
        "方向正负号经常搞反，导致最终结果错误",
    ],
    (Subject.PHYSICS, DiagnosticCategory.E_SELF_REGULATION): [
        "讲解完觉得懂了，但第二天同类题还是不会",
        "遇到复杂题目会直接放弃，不愿意尝试拆解",
    ],

    # ── 化学 ──
    (Subject.CHEMISTRY, DiagnosticCategory.A_FOUNDATION): [
        "能说出反应现象，但解释不了微观粒子层面发生了什么",
        "化学概念之间的联系建立不起来，零散地记忆",
    ],
    (Subject.CHEMISTRY, DiagnosticCategory.B_REPRESENTATION): [
        "宏观现象、微观粒子变化和化学符号三者对不上",
        "能描述实验现象，但写不出对应的化学方程式",
    ],
    (Subject.CHEMISTRY, DiagnosticCategory.C_MODELING): [
        "学过的反应规律换一种物质就不会迁移",
        "实验设计类题目找不到切入点",
    ],
    (Subject.CHEMISTRY, DiagnosticCategory.D_EXECUTION): [
        "方程式配平经常出错或遗漏条件",
        "化学计算中关系量的换算总是弄混",
    ],
    (Subject.CHEMISTRY, DiagnosticCategory.E_SELF_REGULATION): [
        "错题订正了但不知道自己错在哪个环节",
        "看完答案能理解，但隔天独立写就想不起来",
    ],
}


# ---------------------------------------------------------------------------
# 构建结果 payload
# ---------------------------------------------------------------------------
def build_result_payload(
    *,
    subject: Subject,
    grade_label: str,
    category: DiagnosticCategory,
    primary_factor: FactorCode,
    amplifier: AmplifierCode | None,
    evidence: list[str],
    uncertainties: list[str],
    confidence: str,
) -> dict[str, Any]:
    """
    根据诊断结论组装完整的结果字典，供前端渲染结果卡片使用。
    """
    # 基础标签
    category_label = CATEGORY_LABELS[category]
    category_description = CATEGORY_DESCRIPTIONS[category]
    subject_label = SUBJECT_LABELS.get(subject, str(subject.value))

    # 因子行动
    factor_action = FACTOR_ACTIONS.get(primary_factor, {})

    # 放大因子
    amplifier_label = AMPLIFIER_LABELS.get(amplifier) if amplifier else None  # type: ignore[arg-type]

    # 验证动作
    verification_action = get_verification_action(category, subject)

    # 不确定性
    missing_information = get_uncertainties(category, subject)

    # branch_id：类别 + 学科 唯一标识
    branch_id = f"{category.value}__{subject.value}"

    # 组装公开摘要
    summary_parts = [
        f"目前更像是「{category_label}」在优先影响这次{subject_label}学习。",
        category_description,
    ]
    if amplifier and amplifier_label:
        summary_parts.append(f"同时，{amplifier_label}，所以同一个问题可能会反复出现。")
    summary_parts.append(
        "这只是基于对话的初步定位，今晚的小验证会比继续刷题更有信息量。"
    )
    public_summary = " ".join(summary_parts)

    # 诊断升级建议
    diagnostic_upgrade = (
        "如果验证结果与定位一致，可以进入「一家一案」获得完整学习路径；"
        "如果发现新信息，可以随时回来补充，系统会更新定位。"
    )

    return {
        "branch_id": branch_id,
        "catalog_version": RESULT_CATALOG_VERSION,
        "subject": subject.value,
        "subject_label": subject_label,
        "grade_label": grade_label,
        "confidence": confidence,
        "primary_category": category.value,
        "primary_category_label": category_label,
        "primary_factor": primary_factor.value,
        "primary_desc": factor_action.get("start", ""),
        "secondary_factors": [],
        "amplifier": amplifier.value if amplifier else None,
        "amplifier_label": amplifier_label,
        "evidence": evidence,
        "uncertainties": uncertainties,
        "missing_information": missing_information,
        "verification_action": verification_action,
        "parent_common_mistake": factor_action.get("mistake", ""),
        "next_7_days_stop": factor_action.get("stop", ""),
        "next_7_days_start": factor_action.get("start", ""),
        "public_summary": public_summary,
        "diagnostic_upgrade": diagnostic_upgrade,
    }
