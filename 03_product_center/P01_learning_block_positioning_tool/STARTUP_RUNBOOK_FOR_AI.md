# P01 Startup Runbook for AI

本文档给 AI/开发者使用，目标是把 P01 理科学习卡点定位工具在本地跑起来。

当前工具是前后端分离：

- 前端入口：React + Vite，端口 `5173`
- 后端 API：Python `http.server`，端口 `8765`
- 浏览器打开：`http://localhost:5173/`
- 不要把 `8765` 当成用户入口。`8765` 只给 API 使用。

## 0. 项目位置

仓库根目录：

```powershell
D:\wbh\social-media\anshi-learning-lab
```

P01 工具目录：

```powershell
D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
```

后续命令默认从仓库根目录或 P01 工具目录执行。路径不确定时，先执行：

```powershell
pwd
git status --short --branch
```

## 1. 不要提交这些东西

启动前先记住：

- 不要提交 `agent_engine/.env`
- 不要提交 `web_app/data/sessions/*.jsonl`
- 不要提交 `node_modules/`
- 不要提交 `web_app/frontend/dist/`

这些已经在 `.gitignore` 中忽略。AI 在提交前必须执行：

```powershell
git status --short --branch
```

如果看到 `.env`、`.jsonl`、`node_modules`、`dist` 出现在待提交列表，先停下来处理。

## 2. 依赖检查

检查 Node/npm：

```powershell
node -v
npm -v
```

检查 Python：

```powershell
python --version
```

本机 Codex runtime 常用 Python 路径：

```powershell
C:\Users\10707\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

如果系统 `python` 不可用，后端命令优先使用上面这个 Python。

## 3. LLM 配置

LLM key 不是启动必需项。没有 key 时，系统会进入规则模式；有 key 时，系统进入 LLM 增强模式。

配置文件位置：

```text
03_product_center/P01_learning_block_positioning_tool/agent_engine/.env
```

如果没有 `.env`，从模板复制：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
Copy-Item .\agent_engine\.env.example .\agent_engine\.env
```

DeepSeek 文本模型最小配置：

```text
ENABLE_LLM=true
DEFAULT_TEXT_PROVIDER=deepseek
DEEPSEEK_API_KEY=填入真实 key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TEXT_MODEL=deepseek-chat
DEEPSEEK_THINKING=disabled
LLM_TIMEOUT_SECONDS=45
```

豆包/火山方舟暂时是预留配置。没有豆包 key 不影响文本诊断启动。

```text
DOUBAO_API_KEY=
DOUBAO_BASE_URL=
DOUBAO_TEXT_MODEL=
DOUBAO_VISION_MODEL=
DOUBAO_ASR_APP_ID=
DOUBAO_TTS_APP_ID=
```

## 4. 安装前端依赖

第一次启动或 `package-lock.json` 更新后执行：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\web_app\frontend
npm install
```

如果已经装过依赖，可以跳过。

## 5. 启动后端

打开第一个 PowerShell，执行：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
python .\web_app\server.py
```

如果 `python` 不可用，执行：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
& "C:\Users\10707\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\web_app\server.py
```

成功时终端应出现类似输出：

```text
P01 Conversational Agent running at http://127.0.0.1:8765
  LLM mode: llm
  DeepSeek ready: True
```

如果没有 key，也可能是：

```text
  LLM mode: rules
  DeepSeek ready: False
```

这仍然可以启动，只是不用 LLM。

## 6. 启动前端

打开第二个 PowerShell，执行：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\web_app\frontend
npm run dev
```

成功时应看到类似：

```text
Local:   http://localhost:5173/
```

浏览器打开：

```text
http://localhost:5173/
```

## 7. 启动后验收

后端状态检查：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/status | ConvertTo-Json -Depth 5
```

期望字段：

```json
{
  "enable_llm": true,
  "default_text_provider": "deepseek",
  "deepseek_ready": true,
  "mode": "llm"
}
```

如果没有 key，`mode` 可以是 `rules`。

前端验收：

1. 打开 `http://localhost:5173/`
2. 页面标题应为“理科学习卡点定位”
3. 输入框应能输入家长描述
4. 点击“历史记录”应显示历史列表
5. 点击“设置”应显示运行状态
6. 新开空白对话不应进入历史列表；发出第一句话后才进入历史列表

## 8. 常见问题处理

### 8.1 端口被占用

检查后端端口：

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
```

检查前端端口：

```powershell
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
```

如果确认占用端口的是旧的本项目进程，可以停止：

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### 8.2 前端能打开但一直转圈

先检查后端是否启动：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/status
```

如果失败，先启动后端。

### 8.3 后端提示 provider 未配置

检查：

```powershell
Get-Content .\agent_engine\.env
```

至少要有：

```text
ENABLE_LLM=true
DEEPSEEK_API_KEY=真实 key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TEXT_MODEL=deepseek-chat
```

如果没有 key，把 `ENABLE_LLM=false`，使用规则模式。

### 8.4 DeepSeek 模型报错

如果接口返回模型不存在或不可用，优先改成：

```text
DEEPSEEK_TEXT_MODEL=deepseek-chat
```

修改 `.env` 后必须重启后端。

### 8.5 历史记录为空

这是正常的。只有用户发出第一句话后，会话才进入历史列表。

历史数据落盘位置：

```text
web_app/data/sessions/*.jsonl
```

这些是本地运行数据，不提交到 GitHub。

## 9. 开发验证命令

前端构建：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\web_app\frontend
npm run build
```

前端 lint：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\web_app\frontend
npm run lint
```

后端语法检查：

```powershell
cd D:\wbh\social-media\anshi-learning-lab
python -m py_compile .\03_product_center\P01_learning_block_positioning_tool\web_app\server.py
```

如果 `python` 不可用：

```powershell
cd D:\wbh\social-media\anshi-learning-lab
& "C:\Users\10707\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m py_compile .\03_product_center\P01_learning_block_positioning_tool\web_app\server.py
```

诊断行为回归测试：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\agent_engine
python -m unittest discover -s tests -v
```

这组测试必须覆盖数学、物理、化学不串科，用户答案真实改变判断，以及放大因素不抢主卡点。

## 10. 当前架构速记

```text
浏览器 http://localhost:5173
  ↓
React/Vite frontend
  ↓ proxy /api
Python backend http://127.0.0.1:8765
  ↓
ConversationAgent
  ↓
隐藏因子证据层 → 家长可读分类层 → 三科学科验证动作
  ↓
可选 DeepSeek 自由文本抽取与结果润色（不控制流程）
  ↓
JSONL 会话日志 web_app/data/sessions
```

核心文件：

```text
web_app/server.py
web_app/frontend/src/App.tsx
web_app/frontend/src/components/ChatContainer.tsx
web_app/frontend/src/api.ts
agent_engine/science_diagnostic_agent/conversation_agent.py
agent_engine/science_diagnostic_agent/factor_rules.py
agent_engine/science_diagnostic_agent/question_bank.py
agent_engine/science_diagnostic_agent/llm_providers.py
```

## 11. AI 接手时的最短执行序列

如果只想启动，不改代码，按这个顺序执行：

```powershell
cd D:\wbh\social-media\anshi-learning-lab
git status --short --branch
```

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool
& "C:\Users\10707\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\web_app\server.py
```

另开一个 PowerShell：

```powershell
cd D:\wbh\social-media\anshi-learning-lab\03_product_center\P01_learning_block_positioning_tool\web_app\frontend
npm install
npm run dev
```

打开：

```text
http://localhost:5173/
```
