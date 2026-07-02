# 青少年数理化学习问题库资料生产系统

这是一个与现有测评产品完全隔离的离线生产系统。数学、物理、化学知识图谱领域智能体采用“教育部课标定边界 + 大纲/知识点/关系三阶段 Executor + 多模型候选 + Supervisor + 硬校验”的来源优先链路。

知识图谱不能由一个提示词一次性生成。官方课程标准先确定完整任务树，模型只能在任务树叶子内提取原子知识点，随后进入关系建网阶段。模型知识可以补充教学解释和学习卡点，但不能扩张官方课程范围。

当前版本：`0.2.0`。

## 已实现

- 教育部 2022 版数学、科学、物理、化学课程标准来源目录、官方 URL、页数和 SHA-256。
- 扫描版 PDF 的下载、哈希核验、逐页渲染和 Windows 中文 OCR。
- 96 个大纲节点、65 个学段叶子任务，覆盖 1-9 年级并保留 13 个小学科学核心概念。
- 大纲、知识点、关系三个内部生产阶段，每阶段至少两个独立模型候选。
- 每个叶子任务逐页注入对应课标 OCR 证据，禁止 Executor 越界。
- Supervisor 按 90/70 阈值择优、局部重跑或整体重跑。
- 候选、硬校验和审查写入 SQLite，最终网络可生成不可变发布包。
- 覆盖账本、精确页码/摘录校验、悬空边、自环、重复边、前置环检测。
- 小学科学到初中物理/化学缺少 `bridges_to` 时强制失败。

- 严格 Pydantic 数据模型。
- 七类资料生产配方注册表。
- OpenAI-compatible Provider 配置，密钥只从环境变量读取。
- 至少两个 Executor 并行生成独立候选。
- Planner、Executor、Supervisor 三层提示和编排。
- 通用学习卡点资料支持 `model_distillation`；该模式不再用于确定课程大纲。
- 可选 `source_grounded` 模式：使用人工核验来源包做审计型生产。
- 确定性硬校验、90/70 分级决策和最多 N 次重跑。
- SQLite 运行、候选、校验、审查和发布留痕。
- 从学习卡点到结构化诊断追问的编译器。
- 来源审计发布闸门和心理资料人工审批闸门。
- 三类核心思维使用学科专用画像与专科 Supervisor 量表。
- 心理认知资料强制真实理论来源、三科场景、严重程度、AI 边界与专业转介字段。
- 三层正式物料统一规范化、阿里 text-embedding-v4 / 本地 BGE 可替换向量后端、关键词检索、元数据过滤和图关系扩展。
- 端到端自动化测试。

## 课标驱动知识图谱

四份教育部 PDF 是扫描件，没有原生文本层。先生成带页码的 OCR 证据包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ocr_curriculum_pdfs.ps1 `
  -Catalog .\data\official_curriculum_sources.json `
  -PdfDirectory .\artifacts\sources `
  -Output .\artifacts\ocr\official-curriculum-2022.json `
  -PopplerBin "C:\path\to\poppler\bin"
```

然后生成模型不可删改的课标种子并运行三阶段生产流程：

```powershell
problem-library-factory build-curriculum-seed `
  --request .\examples\curriculum_pipeline_request.example.json `
  --catalog .\data\official_curriculum_sources.json `
  --output .\artifacts\curriculum-seed.json

problem-library-factory run-curriculum `
  --request .\examples\curriculum_pipeline_request.example.json `
  --catalog .\data\official_curriculum_sources.json `
  --seed .\artifacts\curriculum-seed.json `
  --evidence .\artifacts\ocr\official-curriculum-2022.json `
  --providers .\examples\curriculum_providers.example.json `
  --database .\artifacts\factory.db `
  --output .\artifacts\curriculum-network.json
```

流水线按 65 个叶子任务逐一生产，并在 `artifacts/checkpoints/<request-id>/` 保存每个阶段；中断后用同一命令即可续跑。任何叶子覆盖不足、引用页不存在、摘录不在 OCR 证据中，或小学科学与物理/化学之间没有承接边，最终网络都不能通过。

在调用真实模型前，可以先生成本地任务树预览：

```powershell
problem-library-factory preview-curriculum `
  --outline .\artifacts\curriculum\k9-stem-seed.json `
  --catalog .\data\official_curriculum_sources.json `
  --evidence .\artifacts\ocr\official-curriculum-2022.json `
  --output .\artifacts\preview\k9-stem-task-tree.html
```

验证后发布不可变网络版本：

```powershell
problem-library-factory publish-curriculum `
  --request .\examples\curriculum_pipeline_request.example.json `
  --catalog .\data\official_curriculum_sources.json `
  --evidence .\artifacts\ocr\official-curriculum-2022.json `
  --network .\artifacts\curriculum-network.json `
  --version k9-stem-v1.0.0 `
  --database .\artifacts\factory.db
```

## 本地准备

```powershell
cd D:\wbh\social-media\anshi-learning-lab\05_ai_production_system\10_learning_problem_library_factory
python -m pip install -e ".[dev]"
python -m pytest
problem-library-factory list-recipes
```

## 配置

1. 复制 `.env.example` 的变量到本机环境，并填写模型密钥。
2. 复制 `examples/providers.example.json`，填写模型名和 OpenAI-compatible endpoint。
3. 复制 `examples/math_linear_equation_request.example.json`。这个默认就是 AI 知识蒸馏请求，不需要来源包。

如果要进入来源审计模式，再复制 `examples/math_linear_equation_source_grounded_request.example.json` 并替换为经过授权、可定位、人工核验的真实来源。

密钥不会写入请求、数据库或发布包。`api_key_env` 只记录环境变量名。

## 运行生产

```powershell
problem-library-factory run `
  --request .\examples\math_linear_equation_request.json `
  --providers .\examples\providers.json `
  --database .\artifacts\factory.db
```

命令会输出运行结果 JSON 的绝对路径。如果批次重试超限或进入人工审核，进程返回码为 `2`。

核心思维和心理认知必须使用来源扎根请求与专用流水线：

```powershell
problem-library-factory run-specialized `
  --request .\examples\math_core_thinking_request.example.json `
  --providers .\examples\providers.json `
  --database .\artifacts\factory.db

problem-library-factory publish-specialized `
  --outcome .\artifacts\runs\RUN_ID.json `
  --version math-thinking-v1.0.0 `
  --database .\artifacts\factory.db
```

心理认知版本发布时还必须传入 `--approved-by`，且所有使用来源必须已经人工核验。

## 发布问题库版本

```powershell
problem-library-factory publish `
  --outcome .\artifacts\runs\RUN_ID.json `
  --version math-g7-linear-equation-v0.1.0 `
  --database .\artifacts\factory.db
```

心理与认知资料必须额外传入 `--approved-by`。

`model_distillation` 产物可以作为内部学习卡点或思维资料候选版本发布；知识图谱禁止走该入口，必须先运行课标驱动流水线。要变成对外可背书版本，再跑 `source_grounded` 审计链路。

## 目录

```text
src/learning_problem_factory/
  models.py         核心数据契约
  recipes.py        七类生产配方
  providers.py      模型适配层
  prompts.py        三层生产提示
  validators.py     确定性质量闸门
  orchestrator.py   并行、审查与重跑流程
  compiler.py       学习卡点 -> 诊断追问
  curriculum_*.py  课标知识网络生产、校验与发布
  specialized_*.py 核心思维/心理认知生产、校验与发布
  repository.py     SQLite 留痕和版本存储
  cli.py            命令行入口
```

更完整的设计见 [docs/architecture.md](docs/architecture.md)。
