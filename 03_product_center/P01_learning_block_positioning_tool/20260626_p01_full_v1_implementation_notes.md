# P01 完整 V1 实现说明

整理日期：2026-06-26

## 当前已经实现

1. Web 前端入口：聊天流、单选卡、多选卡、孩子补充、结果卡。
2. Python 后端 API：`/api/start`、`/api/answer`、`/api/status`。
3. 规则评分内核：三科分流、10 个原因因子、因子权重、adaptive probe。
4. LLM 可选增强：DeepSeek / 豆包 OpenAI-compatible 文本模型适配位。
5. 无 key 降级：没有 key 时自动使用规则模式。
6. 会话落盘：每个 session 写入 `web_app/data/sessions/*.jsonl`。
7. 配置模板：`agent_engine/.env.example`。

## 本地启动

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
.\run_p01_web.ps1
```

打开：

```text
http://127.0.0.1:8765
```

## LLM 配置

复制：

```text
agent_engine/.env.example -> agent_engine/.env
```

填入：

```text
ENABLE_LLM=true
DEFAULT_TEXT_PROVIDER=deepseek

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TEXT_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled

DOUBAO_API_KEY=
DOUBAO_BASE_URL=
DOUBAO_TEXT_MODEL=
DOUBAO_VISION_MODEL=
```

## LLM 在 V1 中做什么

规则内核仍然负责最终因子评分。LLM 只做三件事：

1. 从家长自由文本中抽取可观察信号。
2. 增强结果页的自然语言解释。
3. 后续可扩展为更自然的追问生成。

这样做的原因是：判断不能完全交给模型，否则结果会漂。

## Provider 说明

DeepSeek：

- 使用 OpenAI-compatible Chat Completions。
- 默认 base URL：`https://api.deepseek.com`
- 当前默认模型：`deepseek-v4-flash`

豆包 / 火山方舟：

- 预留 OpenAI-compatible Chat Completions 适配。
- 需要你提供火山方舟控制台里的 base URL、API key、模型/endpoint ID。
- 多模态和语音暂时只留配置位，V1 文本诊断先跑通。

## 当前还没做

- 题图上传后的真实多模态理解。
- 语音输入和语音播报。
- LangGraph 持久化流程。
- 用户账号体系。
- 正式数据库。
- 商业级权限隔离。

这些不影响 P01 V1 的“自然对话 + 结构化定位 + 结果卡”主流程。

