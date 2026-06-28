from __future__ import annotations

from typing import Any

from .factor_rules import FACTOR_ACTIONS
from .models import (
    AMPLIFIER_LABELS,
    CATEGORY_LABELS,
    AmplifierCode,
    DiagnosticCategory,
    FactorCode,
    Subject,
)
from .verification_actions import get_verification_action


RESULT_CATALOG_VERSION = "2026.06-v1"


SUBJECT_LABELS: dict[Subject, str] = {
    Subject.MATH: "数学",
    Subject.PHYSICS: "物理",
    Subject.CHEMISTRY: "化学",
    Subject.UNKNOWN: "理科",
}


CATEGORY_DESCRIPTIONS: dict[DiagnosticCategory, str] = {
    DiagnosticCategory.A_FOUNDATION: "眼前这道题只是表面，真正需要先确认的是旧知识、概念含义或错误理解从哪里断开。",
    DiagnosticCategory.B_REPRESENTATION: "孩子可能看见了题目，却没有把文字、符号、图形和条件稳定地转成可用的解题信息。",
    DiagnosticCategory.C_MODELING: "孩子并非完全听不懂，而是还不能独立把情境中的关系搭起来，所以题目一变就容易失去入口。",
    DiagnosticCategory.D_EXECUTION: "思路可能已经出现，但步骤、计算、单位或多条件处理还没有形成稳定流程。",
    DiagnosticCategory.E_SELF_REGULATION: "卡住之后的定位、复盘和情绪恢复没有形成闭环，导致当时看懂了也难以变成下一次会做。",
}


DEFAULT_FACTOR_BY_CATEGORY: dict[DiagnosticCategory, FactorCode] = {
    DiagnosticCategory.A_FOUNDATION: FactorCode.F02_CONCEPT,
    DiagnosticCategory.B_REPRESENTATION: FactorCode.F04_REPRESENTATION,
    DiagnosticCategory.C_MODELING: FactorCode.F05_MODEL_TRANSFER,
    DiagnosticCategory.D_EXECUTION: FactorCode.F06_EXECUTION,
    DiagnosticCategory.E_SELF_REGULATION: FactorCode.F07_METACOGNITION,
}


_PREVIEW_EVIDENCE: dict[tuple[Subject, DiagnosticCategory], list[str]] = {
    (Subject.MATH, DiagnosticCategory.A_FOUNDATION): ["公式能背出来，但问为什么这样用时说不清", "基础题换一种问法就开始犹豫"],
    (Subject.MATH, DiagnosticCategory.B_REPRESENTATION): ["题目条件看到了，列式时却没有放进去", "图形标记和限制词容易漏掉"],
    (Subject.MATH, DiagnosticCategory.C_MODELING): ["应用题能复述题意，但列不出数量关系", "例题会做，换一个生活情境就不会"],
    (Subject.MATH, DiagnosticCategory.D_EXECUTION): ["思路大致正确，但符号和中间步骤反复出错", "条件一多就容易跳步"],
    (Subject.MATH, DiagnosticCategory.E_SELF_REGULATION): ["看答案时觉得懂了，隔天仍不能独立重做", "错后说不清第一处从哪里开始偏"],
    (Subject.PHYSICS, DiagnosticCategory.A_FOUNDATION): ["公式会背，但每个物理量的意义讲不清", "适用条件稍微变化就容易套错"],
    (Subject.PHYSICS, DiagnosticCategory.B_REPRESENTATION): ["题目中的物理量没有完整进入过程图", "隐含条件和方向信息容易漏掉"],
    (Subject.PHYSICS, DiagnosticCategory.C_MODELING): ["场景能读懂，但对象、过程和定律连不起来", "综合题不知道先分析哪个对象"],
    (Subject.PHYSICS, DiagnosticCategory.D_EXECUTION): ["公式选对后，代入、单位或正负号反复出错", "多步推导做到中间容易丢信息"],
    (Subject.PHYSICS, DiagnosticCategory.E_SELF_REGULATION): ["一卡住就很快找答案，缺少独立推进", "看懂解析后没有延迟复测"],
    (Subject.CHEMISTRY, DiagnosticCategory.A_FOUNDATION): ["守恒、化合价或微粒观念解释不清", "概念题做错时仍很确定自己的理解"],
    (Subject.CHEMISTRY, DiagnosticCategory.B_REPRESENTATION): ["实验现象、粒子变化和方程式对不上", "符号和反应条件没有进入表达"],
    (Subject.CHEMISTRY, DiagnosticCategory.C_MODELING): ["反应规律学过，换一种物质就不会迁移", "实验情境变化后找不到反应关系"],
    (Subject.CHEMISTRY, DiagnosticCategory.D_EXECUTION): ["思路大致有了，但配平或关系量反复出错", "计算步骤一多就容易漏项"],
    (Subject.CHEMISTRY, DiagnosticCategory.E_SELF_REGULATION): ["看解析时明白，第二天仍不能独立完成", "错后只改答案，没有找到概念断点"],
}


def result_branch_id(subject: Subject, category: DiagnosticCategory) -> str:
    return f"{subject.value}.{category.name.lower()}.v1"


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
    subject_label = SUBJECT_LABELS[subject]
    category_label = CATEGORY_LABELS[category]
    category_description = CATEGORY_DESCRIPTIONS[category]
    amplifier_label = AMPLIFIER_LABELS.get(amplifier, "") if amplifier else ""
    action = FACTOR_ACTIONS[primary_factor]
    verification = get_verification_action(category, subject)

    summary = f"目前更像是「{category_label}」在优先影响这次{subject_label}学习。{category_description}"
    if amplifier_label:
        summary += f" 同时，{amplifier_label}，所以同一个问题可能会反复出现。"
    summary += " 这只是基于对话的初步定位，今晚的小验证会比继续刷题更有信息量。"

    return {
        "branch_id": result_branch_id(subject, category),
        "catalog_version": RESULT_CATALOG_VERSION,
        "subject": subject.value,
        "subject_label": subject_label,
        "grade_label": grade_label,
        "confidence": confidence,
        "primary_category": category.value,
        "primary_category_label": category_label,
        "primary_factor": category_label,
        "primary_desc": category_description,
        "secondary_factors": [],
        "amplifier": amplifier.value if amplifier else None,
        "amplifier_label": amplifier_label or None,
        "evidence": evidence,
        "uncertainties": uncertainties,
        "missing_information": uncertainties,
        "verification_action": verification,
        "parent_common_mistake": action["mistake"],
        "next_7_days_stop": action["stop"],
        "next_7_days_start": action["start"],
        "public_summary": summary,
        "diagnostic_upgrade": (
            f"这次对话已经把范围缩到「{category_label}」。如果要确认它在什么题型、"
            f"哪一步反复出现，下一步应核对孩子最近 1-2 张{subject_label}试卷和真实演算过程。"
            "重点不是再看一次分数，而是比较多张卷子里重复出现的第一处断点。"
        ),
    }


def build_result_preview(
    subject_value: str,
    category_value: str,
    amplifier_value: str | None = None,
    grade_label: str = "初二",
) -> dict[str, Any]:
    subject = Subject(subject_value)
    category = DiagnosticCategory(category_value)
    if subject == Subject.UNKNOWN:
        raise ValueError("Preview subject must be math, physics, or chemistry")
    amplifier = AmplifierCode(amplifier_value) if amplifier_value else None
    return build_result_payload(
        subject=subject,
        grade_label=grade_label,
        category=category,
        primary_factor=DEFAULT_FACTOR_BY_CATEGORY[category],
        amplifier=amplifier,
        evidence=list(_PREVIEW_EVIDENCE[(subject, category)]),
        uncertainties=[
            "还没有核对孩子的真实卷面和演算过程。",
            "还需要区分这是长期稳定模式，还是最近一次考试中的偶发现象。",
        ],
        confidence="medium",
    )


def list_result_catalog() -> dict[str, Any]:
    subjects = [Subject.MATH, Subject.PHYSICS, Subject.CHEMISTRY]
    categories = list(DiagnosticCategory)
    return {
        "version": RESULT_CATALOG_VERSION,
        "subjects": [{"id": item.value, "label": SUBJECT_LABELS[item]} for item in subjects],
        "categories": [
            {
                "id": item.value,
                "label": CATEGORY_LABELS[item],
                "description": CATEGORY_DESCRIPTIONS[item],
            }
            for item in categories
        ],
        "amplifiers": [
            {"id": item.value, "label": AMPLIFIER_LABELS[item]}
            for item in AmplifierCode
        ],
        "branches": [
            {
                "id": result_branch_id(subject, category),
                "subject": subject.value,
                "subject_label": SUBJECT_LABELS[subject],
                "category": category.value,
                "category_label": CATEGORY_LABELS[category],
                "verification_title": get_verification_action(category, subject)["title"],
            }
            for subject in subjects
            for category in categories
        ],
    }

