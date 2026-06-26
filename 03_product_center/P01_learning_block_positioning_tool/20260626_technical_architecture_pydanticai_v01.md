# P01 技术架构：PydanticAI 内核与模型混用策略 v01

整理日期：2026-06-26

## 技术结论

V1 使用：

```text
Pydantic models + 规则评分内核 + PydanticAI 预留接口 + DeepSeek / 豆包 Provider 适配层
```

LangGraph 不作为第一版必选，只预留接入位。

## 为什么这样做

P01 的核心不是让智能体自由聊天，而是让输入、判断、输出都可控：

- 输入要能结构化。
- 因子判断要能复核。
- 追问要围绕不确定点。
- 输出字段要固定。
- 结果能沉淀成案例库。

## 架构分层

```text
Frontend Generative UI
  -> Conversation API
  -> Diagnostic Engine
      -> Pydantic schemas
      -> Rule scorer
      -> Question planner
      -> LLM adapter
      -> Result composer
  -> Case Log / Evaluation Data
```

## 模型混用策略

| 场景 | 首选 |
|---|---|
| 普通文本追问、证据抽取、结果解释 | DeepSeek |
| 多模态图片理解，如题图、作业截图 | 豆包多模态 |
| 语音识别、语音回复 | 豆包语音能力 |
| 本地规则评分、路径判断 | 不调用模型 |

## key 占位

V1 先保留配置项，不写真实 key：

```text
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_TEXT_MODEL=
DOUBAO_API_KEY=
DOUBAO_TEXT_MODEL=
DOUBAO_VISION_MODEL=
DOUBAO_ASR_APP_ID=
DOUBAO_TTS_APP_ID=
```

## V1 不做

- 不做 LangGraph 持久化流程。
- 不做多 Agent 专家团。
- 不做完整账号体系。
- 不做长期学习数据平台。
- 不把 LLM 作为唯一判断来源。

## V2 预留

未来需要以下能力时，再接 LangGraph：

- 家长补材料。
- 人工审核。
- 暂停和恢复。
- 一户一案服务流转。
- 多轮报告生成。
- 长期案例状态。

## 接口设计

内部核心函数建议：

```python
start_session(subject: Subject) -> DiagnosticSession
record_answer(session, answer) -> DiagnosticSession
score_session(session) -> FactorScoringResult
plan_next_question(session, scores) -> UIBlock
compose_result(session, scores) -> DiagnosisResult
```

LLM 只接入这些位置：

1. 从长文本中抽取证据。
2. 根据分数接近的因子生成追问。
3. 把结构化结果翻译成家长能懂的文字。

## 数据沉淀

每次完成后保存：

- 匿名 session id。
- 学科。
- 问答事件。
- 因子分数。
- 结果。
- 用户是否认可。
- 是否进入 P02/P03。
- 后续验证反馈。

这些数据后续用于校准规则，而不是直接训练公开模型。

