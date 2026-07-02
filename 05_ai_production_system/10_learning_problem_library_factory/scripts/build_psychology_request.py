from __future__ import annotations

from pathlib import Path

from learning_problem_factory.models import (
    EvidenceMode,
    ProductionRequest,
    ProductionScope,
    SourceDocument,
    SourceKind,
    SourcePack,
    Subject,
)
from learning_problem_factory.specialized_taxonomy import (
    PSYCHOLOGY_DIMENSION_TAXONOMY,
)


ROOT = Path(__file__).resolve().parents[1]


def paper(
    *,
    id: str,
    title: str,
    authors: str,
    year: str,
    locator: str,
    evidence: str,
) -> SourceDocument:
    return SourceDocument(
        id=id,
        title=title,
        kind=SourceKind.ACADEMIC_PAPER,
        publisher_or_author=authors,
        edition_or_year=year,
        locator=locator,
        content=evidence,
        verified_by_human=False,
    )


def guideline(
    *,
    id: str,
    title: str,
    publisher: str,
    year: str,
    locator: str,
    evidence: str,
) -> SourceDocument:
    return SourceDocument(
        id=id,
        title=title,
        kind=SourceKind.PROFESSIONAL_GUIDELINE,
        publisher_or_author=publisher,
        edition_or_year=year,
        locator=locator,
        content=evidence,
        verified_by_human=False,
    )


def main() -> None:
    documents = [
        paper(
            id="theory-self-efficacy-bandura-1977",
            title="Self-efficacy: Toward a Unifying Theory of Behavioral Change",
            authors="Albert Bandura",
            year="1977",
            locator="Psychological Review 84(2), 191–215; https://doi.org/10.1037/0033-295X.84.2.191",
            evidence=(
                "证据卡：自我效能感指个体对自己能否组织并完成特定行动的能力判断，"
                "它会影响是否开始应对、投入多少努力以及遇到困难时坚持多久。效能信息可来自"
                "成功经验、替代经验、言语劝导和生理情绪状态。边界：它是任务与情境相关的信念，"
                "不是固定人格、真实能力测验或疾病诊断；低效能感只能形成待验证的学习假设。"
            ),
        ),
        paper(
            id="theory-learned-helplessness-update-2016",
            title="Learned Helplessness at Fifty: Insights from Neuroscience",
            authors="Steven F. Maier; Martin E. P. Seligman",
            year="2016",
            locator="Psychological Review 123(4), 349–367; https://doi.org/10.1037/rev0000033; PMCID: PMC4920136",
            evidence=(
                "证据卡：原作者回顾了不可控厌恶事件之后减少尝试的现象，并明确修订早期解释："
                "不能简单说个体‘学会了无助’，控制感及其神经机制更复杂。教育场景中只能描述"
                "反复失败或不可控体验后出现的低控制预期、减少尝试等风险线索。边界：动物实验"
                "不能直接推断学生状态，也不能把短暂放弃、抑郁或创伤等同于习得性无助。"
            ),
        ),
        paper(
            id="theory-clinical-perfectionism-shafran-2002",
            title="Clinical Perfectionism: A Cognitive–Behavioural Analysis",
            authors="Roz Shafran; Zafra Cooper; Christopher G. Fairburn",
            year="2002",
            locator="Behaviour Research and Therapy 40(7), 773–791; https://doi.org/10.1016/S0005-7967(01)00059-6",
            evidence=(
                "证据卡：该分析把具有临床意义的完美主义核心描述为：个人自我评价过度依赖于"
                "追求并达到自己设定的高要求，即使这种追求已带来不利后果。教育资料可观察反复"
                "检查、因怕不完美而拖延或回避、结果不理想时全盘否定自我。边界：高标准本身不"
                "等于问题，‘完美主义相关困扰’不是诊断名称，临床概念不得由 AI 判定。"
            ),
        ),
        paper(
            id="theory-test-anxiety-adolescents-torrano-2020",
            title="Test Anxiety in Adolescent Students",
            authors="Rosa Torrano et al.",
            year="2020",
            locator="Frontiers in Psychology 11:612270; https://doi.org/10.3389/fpsyg.2020.612270",
            evidence=(
                "证据卡：该青少年研究依据焦虑的多反应系统，区分考试情境中的认知想法、"
                "生理反应与行为表现，并比较不同考试类型和学业变量。可支持把担忧、身体唤醒、"
                "回避或答题受阻分别记录，而不是笼统贴标签。边界：一次紧张属于常见波动；只有"
                "持续、强烈并影响学习或生活的表现才需要进一步支持或专业评估。"
            ),
        ),
        paper(
            id="theory-school-burnout-salmela-aro-2009",
            title="School Burnout Inventory: Reliability and Validity",
            authors="Katariina Salmela-Aro; Noona Kiuru; Esko Leskinen; Jari-Erik Nurmi",
            year="2009",
            locator="European Journal of Psychological Assessment 25(1), 48–57; https://doi.org/10.1027/1015-5759.25.1.48",
            evidence=(
                "证据卡：学校倦怠在学校情境中包含三个相关但可区分的方面：因学业要求产生的"
                "耗竭、对学校意义的疏离或犬儒态度、作为学生的低效能或不足感。研究样本来自"
                "芬兰综合教育后阶段学生。边界：不能把普通疲劳、短期厌学或成绩下降直接判定为"
                "倦怠；年龄、文化和学校情境限制需要保留，持续功能受损应转介评估。"
            ),
        ),
        paper(
            id="theory-cognitive-load-sweller-1988",
            title="Cognitive Load During Problem Solving: Effects on Learning",
            authors="John Sweller",
            year="1988",
            locator="Cognitive Science 12(2), 257–285; https://doi.org/10.1016/0364-0213(88)90023-7",
            evidence=(
                "证据卡：复杂问题求解中的手段—目的分析会占用有限的认知加工资源，使可用于"
                "形成图式的容量减少；教学设计可以改变不必要的加工负担。教育资料可据此检查"
                "信息是否过多、步骤是否同时交互、表示是否造成额外负担。边界：认知负荷是任务—"
                "学习者—教学设计的交互，不是学生能力低下或注意障碍的诊断。"
            ),
        ),
        paper(
            id="theory-working-memory-baddeley-2000",
            title="The Episodic Buffer: A New Component of Working Memory?",
            authors="Alan Baddeley",
            year="2000",
            locator="Trends in Cognitive Sciences 4(11), 417–423; https://doi.org/10.1016/S1364-6613(00)01538-2",
            evidence=(
                "证据卡：工作记忆模型包括中央执行、语音环路、视空间模板，并加入容量有限的"
                "情景缓冲器，用于整合多来源信息并连接长时记忆。学习场景可观察是否能暂存题目"
                "条件、更新中间结果、协调文字与图形。边界：课堂表现受知识熟悉度、焦虑、睡眠和"
                "任务设计影响，不能据此诊断工作记忆缺陷。"
            ),
        ),
        paper(
            id="theory-attentional-control-eysenck-2007",
            title="Anxiety and Cognitive Performance: Attentional Control Theory",
            authors="Michael W. Eysenck; Nazanin Derakshan; Rita Santos; Manuel G. Calvo",
            year="2007",
            locator="Emotion 7(2), 336–353; https://doi.org/10.1037/1528-3542.7.2.336",
            evidence=(
                "证据卡：注意控制理论区分目标导向与刺激驱动的注意系统，焦虑可能削弱抑制和"
                "转换等执行控制，使效率下降，即使最终正确率有时尚可。学习资料可区分分心、"
                "难以从错误策略切换、被威胁性想法占据等表现。边界：注意波动不能推断 ADHD；"
                "持续跨场景困难或明显功能受损需要由合格专业人员评估。"
            ),
        ),
        paper(
            id="theory-metacognition-flavell-1979",
            title="Metacognition and Cognitive Monitoring: A New Area of Cognitive–Developmental Inquiry",
            authors="John H. Flavell",
            year="1979",
            locator="American Psychologist 34(10), 906–911; https://doi.org/10.1037/0003-066X.34.10.906",
            evidence=(
                "证据卡：元认知框架关注关于认知的知识、认知体验、目标任务与策略行动之间的"
                "互动，以及对认知过程的监控和调节。学习场景可观察能否判断自己是否理解、选择"
                "策略、检查结果并根据反馈调整。边界：不会自我解释可能来自知识不足或表达困难，"
                "不能单凭一次反思任务断定元认知能力缺失。"
            ),
        ),
        paper(
            id="theory-intrinsic-extrinsic-ryan-deci-2000",
            title="Intrinsic and Extrinsic Motivations: Classic Definitions and New Directions",
            authors="Richard M. Ryan; Edward L. Deci",
            year="2000",
            locator="Contemporary Educational Psychology 25(1), 54–67; https://doi.org/10.1006/ceps.1999.1020",
            evidence=(
                "证据卡：内在动机涉及因活动本身的兴趣或满足而行动；外在动机并非单一的‘奖励驱动’，"
                "其自主程度可以从外部控制到较充分内化。教育资料应记录学生行动理由及自主程度，"
                "避免把外在动机一概视为有害。边界：动机随任务、环境和时间变化，不能据一次拒绝"
                "学习判定学生缺乏动机或品格有问题。"
            ),
        ),
        paper(
            id="theory-achievement-goals-elliot-mcgregor-2001",
            title="A 2 × 2 Achievement Goal Framework",
            authors="Andrew J. Elliot; Holly A. McGregor",
            year="2001",
            locator="Journal of Personality and Social Psychology 80(3), 501–519; https://doi.org/10.1037/0022-3514.80.3.501",
            evidence=(
                "证据卡：2×2 成就目标框架以掌握/表现和趋近/回避两个维度区分掌握趋近、"
                "掌握回避、表现趋近、表现回避目标。学习资料可据此描述学生关注理解、避免不熟练、"
                "展示能力或避免显得能力不足的倾向。边界：目标取向是情境化倾向，不是固定人格，"
                "不同目标可能并存，不能简单分成好学生与坏学生。"
            ),
        ),
        paper(
            id="theory-self-determination-ryan-deci-2000",
            title="Self-Determination Theory and the Facilitation of Intrinsic Motivation, Social Development, and Well-Being",
            authors="Richard M. Ryan; Edward L. Deci",
            year="2000",
            locator="American Psychologist 55(1), 68–78; https://doi.org/10.1037/0003-066X.55.1.68",
            evidence=(
                "证据卡：自我决定理论强调自主、胜任和关系三种基本心理需要；支持这些需要的"
                "社会情境有利于更自主的动机与良好发展，持续受阻则与动机和幸福感下降相关。"
                "教育资料可检查选择感、能力反馈和归属支持。边界：需要受阻是环境与体验的描述，"
                "不是精神障碍诊断，也不能据相关研究承诺单一干预必然改善成绩。"
            ),
        ),
        guideline(
            id="guideline-who-adolescent-mental-health-2025",
            title="Mental Health of Adolescents",
            publisher="World Health Organization",
            year="2025",
            locator="https://www.who.int/news-room/fact-sheets/detail/adolescent-mental-health",
            evidence=(
                "安全证据卡：青春期是独特的发展阶段，心理健康受家庭、学校、同伴、逆境和社会环境"
                "等多因素影响。WHO 强调及早识别、避免过度医疗化、尊重儿童权利并保证获得适当"
                "心理健康服务。教育 AI 只能提供低风险学习支持，不能诊断或替代专业照护。出现"
                "自伤、自杀、伤害他人、精神病性体验或显著功能受损时应立即联系当地合格专业服务。"
            ),
        ),
        guideline(
            id="guideline-unicef-teen-support-referral",
            title="When to Help Your Teen Find Mental Health Support",
            publisher="UNICEF Parenting",
            year="accessed 2026-07-02",
            locator="https://www.unicef.org/parenting/mental-health/when-help-your-teen-find-mental-health-support",
            evidence=(
                "安全证据卡：如果情绪或行为变化持续数周并干扰日常功能，应寻求基层医疗或心理"
                "专业支持。明显自伤或自杀言行、对自己或他人构成危险、强烈恐惧妨碍日常活动、"
                "严重情绪变化、物质使用等需要及时求助；有即时危险时无需等待同意，应联系当地"
                "紧急服务、危机热线或训练有素的专业人员。"
            ),
        ),
        guideline(
            id="guideline-nimh-child-adolescent-warning-signs",
            title="Child and Adolescent Mental Health: Warning Signs and Getting Help",
            publisher="U.S. National Institute of Mental Health",
            year="accessed 2026-07-02",
            locator="https://www.nimh.nih.gov/health/topics/child-and-adolescent-mental-health",
            evidence=(
                "安全证据卡：若行为或情绪持续数周或数月，并影响家庭、学校、同伴关系或日常生活，"
                "应联系医疗或心理健康专业人员。自伤、想到自杀、危险破坏行为、明显知觉异常等需"
                "立即求助。该页面的美国热线号码不应直接移植到中国场景；产品必须提示联系用户"
                "所在地的监护人、学校支持、医疗机构、心理援助热线或紧急服务。"
            ),
        ),
    ]
    request = ProductionRequest(
        id="psychology-cognition-k9-2026-v1",
        recipe_id="learning_psychology_cognition_v1",
        evidence_mode=EvidenceMode.SOURCE_GROUNDED,
        source_pack=SourcePack(
            id="source-pack-psychology-cognition-k9-2026-v1",
            title="青少年学习心理与认知发展理论及安全边界来源包",
            scope_note=(
                "覆盖12个规范维度。每个批次由系统确定性绑定对应 theory-* 理论来源，"
                "并同时绑定 WHO、UNICEF、NIMH 三份 guideline-* 安全来源。"
                "所有证据卡均为基于原始论文或权威指南的保守摘要，尚未由人类专家逐条核验。"
            ),
            documents=documents,
        ),
        scope=ProductionScope(
            subject=Subject.CROSS_SUBJECT,
            grade_min=1,
            grade_max=9,
            modules=list(PSYCHOLOGY_DIMENSION_TAXONOMY),
            granularity="module",
        ),
        requested_by="local-production",
        max_reruns=5,
    )
    output_dir = ROOT / "artifacts/psychology/requests"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "psychology-cognition.json"
    target.write_text(request.model_dump_json(indent=2), encoding="utf-8")
    print(target.resolve())


if __name__ == "__main__":
    main()
