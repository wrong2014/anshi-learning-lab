from __future__ import annotations


PSYCHOLOGY_DIMENSION_TAXONOMY: dict[str, tuple[str, str]] = {
    "学业自我效能感": ("psychology.academic-self-efficacy", "psychology"),
    "不可控感与习得性无助风险": (
        "psychology.learned-helplessness-risk",
        "psychology",
    ),
    "完美主义相关困扰": ("psychology.perfectionism-distress", "psychology"),
    "考试焦虑": ("psychology.test-anxiety", "psychology"),
    "学校倦怠": ("psychology.school-burnout", "psychology"),
    "认知负荷": ("cognition.cognitive-load", "cognition"),
    "工作记忆": ("cognition.working-memory", "cognition"),
    "注意调控": ("cognition.attentional-control", "cognition"),
    "元认知监控": ("cognition.metacognitive-monitoring", "cognition"),
    "内在与外在动机": ("motivation.intrinsic-extrinsic", "motivation"),
    "成就目标取向": ("motivation.achievement-goals", "motivation"),
    "自我决定与基本心理需要": (
        "motivation.self-determination-needs",
        "motivation",
    ),
}


PSYCHOLOGY_ID_TO_NAME = {
    dimension_id: name
    for name, (dimension_id, _layer) in PSYCHOLOGY_DIMENSION_TAXONOMY.items()
}


PSYCHOLOGY_THEORY_SOURCE_BY_MODULE = {
    "学业自我效能感": "theory-self-efficacy-bandura-1977",
    "不可控感与习得性无助风险": "theory-learned-helplessness-update-2016",
    "完美主义相关困扰": "theory-clinical-perfectionism-shafran-2002",
    "考试焦虑": "theory-test-anxiety-adolescents-torrano-2020",
    "学校倦怠": "theory-school-burnout-salmela-aro-2009",
    "认知负荷": "theory-cognitive-load-sweller-1988",
    "工作记忆": "theory-working-memory-baddeley-2000",
    "注意调控": "theory-attentional-control-eysenck-2007",
    "元认知监控": "theory-metacognition-flavell-1979",
    "内在与外在动机": "theory-intrinsic-extrinsic-ryan-deci-2000",
    "成就目标取向": "theory-achievement-goals-elliot-mcgregor-2001",
    "自我决定与基本心理需要": "theory-self-determination-ryan-deci-2000",
}


PSYCHOLOGY_GUIDELINE_SOURCE_IDS = (
    "guideline-who-adolescent-mental-health-2025",
    "guideline-unicef-teen-support-referral",
    "guideline-nimh-child-adolescent-warning-signs",
)
