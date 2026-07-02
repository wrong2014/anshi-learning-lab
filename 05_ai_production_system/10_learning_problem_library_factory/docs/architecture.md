# 学习问题库资料生产系统：技术架构 v0.1

## 系统边界

本系统是独立的离线资料生产系统，不依赖、导入或适配任何现有测评产品。

它负责：

- 在默认 `model_distillation` 模式下，让模型自举产出学习卡点和诊断追问候选；课程范围和正式知识网络必须走课标流水线。
- 在可选 `source_grounded` 模式下，将经过核验的来源资料组织为 Source Pack。
- 让 Planner 依据目标模块拆分批次。
- 并行调用至少两个 Executor 生成独立候选。
- 先执行确定性硬校验，再交给 Supervisor 做语义质量审查。
- 对不合格批次进行有限次数的定向重跑。
- 将通过审核的学习卡点编译成结构化诊断追问。
- 形成带摘要校验值的不可变发布包。

它暂不负责：

- 面向家长或学生的测评对话。
- 将问题条目映射到旧产品的因子编号或分值。
- 自动抓取和判定互联网资料的权威性。
- 绕过人工审核发布心理、认知或干预边界内容。

## 课标驱动知识图谱流水线

```text
Official Curriculum PDFs
  -> Hash Verification + Page OCR
  -> Immutable Curriculum Seed
  -> Parallel Outline Candidates + Supervisor
  -> Parallel Knowledge Point Candidates + Supervisor (one leaf at a time)
  -> Coverage Ledger
  -> Parallel Graph Candidates + Supervisor
  -> Citation + Coverage + Graph Validators
  -> SQLite Audit + Checkpoints
  -> CurriculumKnowledgeNetwork
  -> Immutable Curriculum Release
```

课程范围禁止使用 `model_distillation`。来源目录、OCR 证据、确定性种子和模型产物分层保存。

## 学习卡点资料流水线

```text
Production Request
  -> Planner / ExecutionPlan
  -> Executor A + Executor B + ...
  -> Pydantic Schema Validation
  -> Deterministic Validators
  -> Supervisor Rubric Review
  -> Retry (max N) / Human Review
  -> Accepted KnowledgeArtifact
  -> Diagnostic Probe Compiler
  -> Immutable ReleaseBundle
```

## 两种证据模式

### model_distillation

默认模式。不需要来源包，目标是尽量榨出大语言模型内部已有的学科知识、教学经验、常见误解和学习卡点。

约束：

- `source_pack` 可以为空。
- `batch.source_ids`、`artifact.source_ids` 和所有 `citations` 必须为空，防止模型伪造引用。
- Supervisor 不因为缺少来源而扣分，重点审查覆盖面、内部一致性、教学洞察密度和可观察性。
- 产物会带有模型蒸馏标记，适合作为内部候选问题库。

### source_grounded

审计模式。用于把候选问题库和课程标准、教材、论文、专家资料进行校准。

约束：

- 必须提供 Source Pack。
- 每个知识点、关系和学习卡点必须有精确引用。
- 发布时涉及的每个来源必须已经人工核验。

核心思维和心理认知资料只允许使用该模式，并由 `SpecializedMaterialFactory` 生产。心理认知发布还必须记录明确的人工审批人。

## 为什么先硬校验再让模型审查

结构错误不需要大模型判断。以下问题由代码直接拦截：

- 重复或不稳定的 ID。
- 在蒸馏模式下伪造来源引用。
- 在来源审计模式下引用了来源包之外的来源。
- 在来源审计模式下缺少来源引用的知识点、关系或卡点。
- 卡点指向不存在的知识点。
- 前置依赖形成环。
- 一个知识点没有对应学习卡点。
- 追问选项 ID 重复。
- 出现“粗心”“不努力”等主观标签。
- 年级或学科超出生产请求范围。

Supervisor 只处理代码无法可靠判断的准确性、深度、可观察性和术语一致性。

## 质量决策

```text
90-100  pass
70-89   partial_rerun
0-69    full_rerun
高风险、重试超限或来源争议  human_review
```

分数与决策的一致性由 Schema 强制校验，Supervisor 不能输出“80 分但通过”。

## 发布约束

- 只有状态为 `completed` 的生产运行可以发布。
- `model_distillation` 发布包会标记为模型蒸馏产物，不要求来源包。
- `source_grounded` 发布涉及的每个来源必须已经人工核验。
- 心理与认知配方必须填写人工审批人。
- 版本号在同一个 SQLite 仓库内唯一，已发布版本不可覆盖。
- 发布包同时保存资料摘要和追问摘要，方便检测内容漂移。

## 下一阶段

1. 完成四份课标的全量 OCR 并人工抽检低质量页。
2. 用三个真实模型跑完 65 个叶子任务，建立首版覆盖基线。
3. 建立小学科学到初中物理、化学的五组黄金承接边。
4. 建立人工审核表和黄金样本集，校准 Supervisor 量表。
5. 将通过审核的知识网络输入学习卡点资料生产流程。
