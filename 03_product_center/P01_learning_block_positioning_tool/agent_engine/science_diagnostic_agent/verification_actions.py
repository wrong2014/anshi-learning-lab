from __future__ import annotations

from .models import DiagnosticCategory, Subject


VerificationAction = dict[str, str]


_ACTIONS: dict[tuple[DiagnosticCategory, Subject], VerificationAction] = {
    (DiagnosticCategory.A_FOUNDATION, Subject.MATH): {
        "title": "不用计算，先讲清一个概念",
        "steps": "从最近错题里挑一个概念或公式，让孩子不用课本原话解释它，再举一个不能使用它的反例。全程先不讲答案。",
        "observe": "观察孩子是旧知识想不起来、概念含义说不清，还是带着一个很确定但错误的理解。",
    },
    (DiagnosticCategory.A_FOUNDATION, Subject.PHYSICS): {
        "title": "把公式里的每个量说成人话",
        "steps": "从错题中挑一个公式，让孩子逐个说明物理量、单位、方向和适用条件，再举一个不能直接套用的情形。",
        "observe": "观察他是只记住了字母，还是能解释量与量之间真正的物理关系。",
    },
    (DiagnosticCategory.A_FOUNDATION, Subject.CHEMISTRY): {
        "title": "把宏观现象讲到微观粒子",
        "steps": "选一个最近学过的反应，让孩子分别说出现象、粒子发生了什么、为什么守恒，再写对应符号。",
        "observe": "观察概念、微粒观念和符号表达中，第一处对不上的地方。",
    },
    (DiagnosticCategory.B_REPRESENTATION, Subject.MATH): {
        "title": "只做题意翻译，不急着算",
        "steps": "拿一道错题，让孩子圈出已知量、目标量和限制条件，再把文字改写成图、表或关系式。先停在列式前。",
        "observe": "观察信息是没读到、读到了没理解，还是理解了却没有进入关系式。",
    },
    (DiagnosticCategory.B_REPRESENTATION, Subject.PHYSICS): {
        "title": "先列物理量，再画过程图",
        "steps": "遮住答案，让孩子列出所有物理量、单位和隐含条件，然后画受力图、过程图或电路图，不做计算。",
        "observe": "观察哪一个条件、符号或过程没有进入图和后续分析。",
    },
    (DiagnosticCategory.B_REPRESENTATION, Subject.CHEMISTRY): {
        "title": "做一张现象—粒子—符号三列表",
        "steps": "把一道错题分成三列：看到了什么、粒子怎么变、用什么方程式或符号表示，让孩子逐列对应。",
        "observe": "观察三种表征从哪一列开始断开，而不是只看方程式最后配没配平。",
    },
    (DiagnosticCategory.C_MODELING, Subject.MATH): {
        "title": "遮住数字，先画解题地图",
        "steps": "遮住应用题里的数字，只让孩子说清对象、数量关系、先求什么后求什么，并画出关系图。",
        "observe": "观察他能否找到第一条关系，以及换一个问法后这条关系是否还认得出来。",
    },
    (DiagnosticCategory.C_MODELING, Subject.PHYSICS): {
        "title": "先拆对象和过程，再选定律",
        "steps": "让孩子把题目按对象和过程分段，每段只写状态、变化和可能使用的定律，最后再决定公式。",
        "observe": "观察是对象没分清、过程没拆开，还是定律的适用边界不清。",
    },
    (DiagnosticCategory.C_MODELING, Subject.CHEMISTRY): {
        "title": "先找物质关系，再写方程式",
        "steps": "让孩子先用箭头画出反应物、生成物、条件和守恒关系，再尝试写方程式，不直接套模板。",
        "observe": "观察换一种物质或实验情境后，原有规律还能不能正确迁移。",
    },
    (DiagnosticCategory.D_EXECUTION, Subject.MATH): {
        "title": "只找第一处跑偏，不重算整题",
        "steps": "让孩子逐行圈出数字、符号、变形和单位，并与正确过程对照，只标记第一处不一致。",
        "observe": "观察错误是否总发生在同一种运算、符号或多步骤衔接位置。",
    },
    (DiagnosticCategory.D_EXECUTION, Subject.PHYSICS): {
        "title": "逐行检查公式、代入、单位和方向",
        "steps": "拿一道思路基本正确的错题，按公式选择、数值代入、单位换算、方向正负四步逐项核对。",
        "observe": "观察是固定流程没有建立，还是步骤一多后工作记忆开始丢信息。",
    },
    (DiagnosticCategory.D_EXECUTION, Subject.CHEMISTRY): {
        "title": "把化学计算拆成四个检查点",
        "steps": "按化学式或方程式、关系量、代入、单位与有效数字四步检查，只找第一处错误。",
        "observe": "观察错误是否稳定集中在配平、关系量或计算执行中的同一位置。",
    },
    (DiagnosticCategory.E_SELF_REGULATION, Subject.MATH): {
        "title": "让孩子自己标出第一处不会",
        "steps": "把答案收起来，只问孩子从哪一句、哪一步开始不确定，并让他写下一步想尝试什么；隔天再独立做一次。",
        "observe": "观察他能否识别断点，以及看懂答案后的理解能否保留到第二天。",
    },
    (DiagnosticCategory.E_SELF_REGULATION, Subject.PHYSICS): {
        "title": "先说断点，再决定要不要看提示",
        "steps": "让孩子先指出是场景、图、定律还是计算处卡住，只给对应的一小条提示，隔天用同类变式复测。",
        "observe": "观察孩子是否能在不拿完整答案的情况下继续推进，以及遇错后的情绪恢复速度。",
    },
    (DiagnosticCategory.E_SELF_REGULATION, Subject.CHEMISTRY): {
        "title": "把错题复盘变成一次延迟复测",
        "steps": "让孩子先说自己在哪个概念、符号或反应关系处卡住，只看最小提示，24 小时后独立重做。",
        "observe": "观察他能否说出断点，并把当天的看懂变成第二天仍能独立完成。",
    },
}


_GENERIC_ACTION: VerificationAction = {
    "title": "只找第一处卡点",
    "steps": "拿最近一道错题，先不讲答案，让孩子指出从哪一句或哪一步开始不确定，并说出下一步想尝试什么。",
    "observe": "观察第一处断点发生在理解、转化、方法选择、执行还是复盘。",
}


def get_verification_action(
    category: DiagnosticCategory,
    subject: Subject,
) -> VerificationAction:
    return dict(_ACTIONS.get((category, subject), _GENERIC_ACTION))

