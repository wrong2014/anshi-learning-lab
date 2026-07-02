# 三层物料统一检索层 v1

## 结论

统一检索层不是单一向量库。它把三层物料规范成可追溯检索单元，并组合四种能力：元数据精确过滤、中文字符二元组全文检索、可替换的稠密向量召回、知识关系邻接扩展。

任何命中都保留原始文件、对象 ID、JSON 路径、物料版本、审批范围和安全级别。第一层正式知识图谱没有知识点级可观察卡点信号，因此知识点命中只能说明“可能涉及什么知识内容”，不能直接充当诊断证据。

## 为什么不用纯向量

- 学科、年级、审批范围和心理安全级别必须硬过滤，不能交给相似度猜。
- 知识点名称、公式与符号需要文本精确能力。
- 前置、支撑和承接关系本来就是图边，向量化会损失方向。
- 家长自然语言和同义表达适合语义向量召回。

## 生产索引

先安装可选依赖：

```powershell
python -m pip install -e ".[dev,retrieval]"
```

正式索引推荐使用阿里百炼 `text-embedding-v4`、1024 维。阿里官方将它列为纯文本检索的推荐模型，1024 维是通用场景的性能/成本平衡档；原生 DashScope 调用还可区分 `document` 和 `query`：

```powershell
$env:DASHSCOPE_API_KEY="仅在本机环境中设置，不写入仓库"
python .\scripts\build_material_index.py --embedding aliyun `
  --model text-embedding-v4 --dimension 1024
```

配置样例位于 `.env.example`。本机真实 Key 保存在被 Git 忽略的 `.env` 中；构建、查询和评测脚本会自动加载，但已有进程环境变量优先。Key 不会写进索引、请求材料、评测报告或命令参数。

本地 BGE 保留为断网降级和 A/B 基线：

```powershell
python .\scripts\build_material_index.py --embedding bge
```

默认产物为 `artifacts/retrieval/k9-material-index-v1.sqlite3`。索引内记录供应商、模型名和维度；查询时使用不同模型会直接失败。重建采用临时文件，只有全部 1,068 个向量成功后才原子替换旧索引，空 Key、限流、中断或服务故障不会删除当前可用版本。

阿里官方规格：<https://help.aliyun.com/zh/model-studio/embedding>

## 查询

```powershell
python .\scripts\query_material_index.py "孩子物理例题会做，换个场景就不知道选公式" `
  --subject physics --grade 8 --top-k 8
```

只看专业转介安全通道：

```powershell
python .\scripts\query_material_index.py "持续数周，已经不愿上学，睡眠也受影响" `
  --safety-level referral
```

`--lexical-only` 可以在不加载向量模型时降级运行。该降级是显式的，响应会给出警告。

## 质量验证

```powershell
python .\scripts\evaluate_material_retrieval.py
```

2026-07-02 的真实 A/B 结果：

- 1,068 个检索单元：知识图谱 719、核心思维 100、心理/认知/动机 249；
- 1,486 个关系视图；
- 14 个黄金检索场景全部在预设 top-k 内命中，包括 3 个跨层混淆难例；
- 阿里 `text-embedding-v4@1024`：14/14 通过，平均命中名次 1.071，top-1 为 13/14；
- 本地 `bge-small-zh-v1.5@512`：14/14 通过，平均命中名次 1.214，top-1 为 12/14；
- 阿里版索引：`artifacts/retrieval/k9-material-index-v1-aliyun.sqlite3`；
- 阿里版报告：`artifacts/retrieval/k9-material-index-v1-aliyun-evaluation.json`；
- 自动化测试 40 项全部通过（含本地 `.env` 自动加载、阿里分批、query/document、限流重试、响应维度和失败保留旧索引）。

阿里版在“物理例题会做、换场景不会选公式”的跨层难例中，把科学论证信号排在第 1；本地 BGE 把相关信号排在第 3。阿里版因此成为推荐主索引，本地 BGE 保留为断网降级。即使如此，全库混搜仍只能发现候选，不能直接作为诊断；下游问题编译器必须先解析学科、年级、观察者和场景，再分别查询各层。

## 当前边界

- 这是内部检索基础设施，不是心理测评或诊断器。
- 第二、三层保持 `internal_conditionally_approved`，不能在查询层被改写成公开审批。
- 向量相似度只负责召回候选；第 2 步诊断问题编译器仍需建立证据方向、反证和置信度更新规则。
- 真实 Key 保存在本机 Git 忽略的 `.env`，未被 Git 跟踪，也没有写入索引或报告。已验证清空外部环境变量后，脚本仍能自动加载并完成阿里评测。
