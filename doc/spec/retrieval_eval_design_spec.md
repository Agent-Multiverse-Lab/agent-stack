# RAG 检索指标评估工具设计

状态：首期方案已实现。

## 1. 目标

在 `src/knowledge/rag_eval/` 中提供一个确定性、可重复的检索评估工具，
用于回答两个问题：

1. 当前真实知识库检索在不同 K 下能否召回人工标注的相关分块。
2. 在召回率和上下文噪声之间，哪个全局 `top_k` 更适合作为生产默认值。

首期只评估检索层，不评估最终回答质量。核心输出为：

- `Hit@K`：前 K 个结果是否至少命中一个相关分块。
- `Precision@K`：前 K 个结果中相关分块的比例。
- `Recall@K`：前 K 个结果覆盖了多少人工标注的相关分块。
- `F1@K`：`Precision@K` 与 `Recall@K` 的调和平均。
- `recommended_top_k`：基于验证集指标选出的建议 K。

这里的 `F1@K` 是分块级检索 F1，不是答案文本的字符、Token 或语义 F1。
首期不引入 Ragas 或 LLM 裁判，避免评估结果受模型随机性影响。

## 2. 当前生产检索基线

评估必须复用当前真实检索链路，而不是在评估目录内重新实现一套向量检索：

```text
人工标注查询
  -> knowledge_service.search(db, uid, kb_id, query, limit=max_k)
  -> 使用 KnowledgeEmbeddingBinding 指定的 Embedding 模型生成查询向量
  -> MilvusKnowledge.search(...)
  -> COSINE 排序后的分块结果
  -> rag_eval 归一化结果并计算各个 K 的指标
```

当前实现提供了可直接用于评估的稳定字段：

- 索引阶段使用 `file_id:chunk_index` 生成 `chunk_id`。
- Milvus 检索返回 `chunk_id`、`chunk_index`、`file_id`、`chunk` 和相似度。
- 当前默认 `top_k` 为 10，HTTP 请求允许的范围为 1 到 100。
- 当前生产搜索是稠密向量检索，距离指标为 `COSINE`。

每条查询只调用一次生产检索，`limit` 使用候选 K 中的最大值；其他 K 直接取
同一结果列表的前缀。这样既减少 Embedding 和 Milvus 调用，也避免多次查询产生
不可比较的结果。

`src/knowledge/rag_eval/` 不直接导入 `server/service/knowledge_service.py`。
未来由 `scripts/` 下的入口创建数据库会话并调用 `knowledge_service.search(...)`，
再把一个异步检索函数传给评估器，保持现有依赖方向。

## 3. 真实评测集

### 3.1 数据格式

一个数据集只对应一个 `uid + kb_id + corpus_version`，避免在同一份结果中混合
不同知识库或索引快照：

```json
{
  "dataset_id": "product_manual_retrieval",
  "dataset_version": "v1",
  "corpus_version": "2026-08-03",
  "uid": "真实用户业务标识",
  "kb_id": "真实知识库标识",
  "samples": [
    {
      "query_id": "q001",
      "query": "真实用户问题",
      "split": "validation",
      "relevant_chunk_ids": [
        "file-id:3",
        "file-id:8"
      ]
    }
  ]
}
```

字段约束：

- `query_id` 在数据集内唯一。
- `query` 必须来自真实业务问题或经过人工确认的等价改写。
- `split` 只能是 `validation` 或 `test`。
- `relevant_chunk_ids` 必须非空、去重，并使用生产索引中的准确 `chunk_id`。
- `corpus_version` 表示人工标注对应的冻结语料和索引版本。语料、解析结果或
  Chunker 变化后必须更新版本并重新核对标签。

当前系统还没有可自动校验的知识库索引版本号，因此首期的
`corpus_version` 由评估负责人维护。报告必须原样记录它，不能把不同版本的运行
结果直接比较。

### 3.2 标注规则

Ground Truth 以人工核验的相关分块为准，不用 LLM 自动判定相关性：

1. 从真实问题记录中选择查询，覆盖单分块问题和需要多个证据分块的问题。
2. 标注人员在目标知识库的当前索引快照中定位所有能直接支持该问题的分块。
3. 用生产检索跑一次候选结果，对未标注但实际相关的分块进行人工复核并补标。
4. 第二位人员抽查有争议的标签，确认后冻结 `dataset_version` 和
   `corpus_version`。

如果所有样本都只有一个相关分块，则 `Recall@K` 基本等价于 `Hit@K`，无法真实
衡量多证据召回。因此评测集需要包含一部分确实要求多个分块才能完整回答的问题。

首期不接受 `relevant_chunk_ids=[]` 的无答案样本。无答案检索需要相似度阈值和
单独的误召回率指标，不能混入正样本的 Recall/F1。

## 4. 指标口径

对查询 `q`：

- `G(q)`：人工标注的相关 `chunk_id` 集合。
- `R(q, K)`：检索结果按原始排名去重后，前 K 个 `chunk_id` 的集合。
- `M(q, K) = G(q) ∩ R(q, K)`：命中的相关分块集合。

结果去重时保留同一 `chunk_id` 第一次出现的位置，重复结果不能重复计分。

### 4.1 Hit@K

```text
Hit@K(q) = 1，当 |M(q, K)| > 0
Hit@K(q) = 0，其他情况
```

数据集的 `Hit Rate@K` 是所有查询 `Hit@K` 的算术平均。它回答“用户问题在前 K
条中至少拿到一条可用证据的概率”，但不能替代 Recall。

### 4.2 Precision@K

```text
Precision@K(q) = |M(q, K)| / |R(q, K)|
```

当没有返回结果时，`Precision@K(q)=0`。分母使用实际返回的去重结果数，而不是
名义上的 K；这样可以准确衡量真正进入上下文的噪声比例。

虽然首要需求是 Top-K、Recall 和 F1，但 F1 必须依赖 Precision，因此
`Precision@K` 是不可省略的中间指标，也应出现在报告中。

### 4.3 Recall@K

```text
Recall@K(q) = |M(q, K)| / |G(q)|
```

它回答“该问题所需的已标注证据，在前 K 条中被找回了多少”。由于首期拒绝空
Ground Truth，分母始终大于零。

### 4.4 F1@K

```text
F1@K(q) = 2 * Precision@K(q) * Recall@K(q)
          / (Precision@K(q) + Recall@K(q))
```

当 Precision 和 Recall 同时为 0 时，`F1@K(q)=0`。

### 4.5 聚合方式

每个 K 先逐查询计算，再对查询做宏平均：

```text
Macro Metric@K = sum(Metric@K(q)) / query_count
```

宏平均作为主指标，避免相关分块较多的少数问题支配总体结果。报告同时保留每条
查询的命中、漏召回和原始排名，方便定位问题；首期不增加加权评分体系。

## 5. 选择合适的 Top-K

`top_k` 是需要通过评测选择的截断参数，本身不是一个分数。首期建议从
`[1, 3, 5, 10]` 开始评估，允许调用方显式调整，但必须满足：

- K 为互不重复的正整数。
- K 不超过当前搜索接口上限 100。
- 一次检索使用 `max(K)`，所有指标共享同一排序结果。

选择规则：

1. 只使用 `validation` 样本选择 K，避免在测试集上调参。
2. 如果调用方给出业务最低召回率 `min_recall`，先筛选
   `Macro Recall@K >= min_recall` 的候选。
3. 在剩余候选中选择 `Macro F1@K` 最高的 K。
4. F1 相同时选择更小的 K，减少传给生成模型的上下文和 Token 开销。
5. 如果没有候选达到 `min_recall`，仍返回最高 F1 的 K，但在报告中标记
   `recall_target_met=false`。
6. 使用选出的 K 只在 `test` 样本上报告最终指标，不再根据测试结果改 K。

如果数据量不足以拆分 validation/test，可以输出各 K 的描述性指标，但报告不得
把最高分 K 表述为已经验证的生产最优值。

## 6. 评估流程

```text
读取并校验数据集
  -> 校验 K 列表和 validation/test 划分
  -> 对每条 query 调用一次真实检索，limit=max_k
  -> 从 hit.entity.chunk_id 读取业务 ID，缺失时使用 hit.id
  -> 按首次出现位置去重并保留 rank、distance、file_id
  -> 对每个 K 计算逐查询指标
  -> 按 split 和 K 做宏平均
  -> 在 validation 上选择 recommended_top_k
  -> 在 test 上报告选定 K 的最终结果
  -> 输出 JSON 报告
```

任何查询发生 Embedding、数据库或 Milvus 异常时，本次运行应标记为失败，不能把
系统错误伪装成 `Recall=0` 后继续生成“有效”总分。

## 7. 最小模块

```text
src/knowledge/rag_eval/
├── __init__.py
├── types.py
├── metrics.py
├── evaluator.py
└── retrieval_eval_design_spec.md

scripts/
└── evaluate_rag_retrieval.py
```

职责如下：

- `types.py`：数据集、逐查询结果、K 汇总和最终报告的数据结构。
- `metrics.py`：无 I/O 的 `RetrievalMetrics` 指标类，计算 `Hit/Precision/Recall/F1@K`。
- `evaluator.py`：`RetrievalEvaluator` 负责校验输入、调用异步检索函数、聚合指标并选择 K。
- `scripts/evaluate_rag_retrieval.py`：创建数据库会话，调用
  `knowledge_service.search(...)`，读取真实数据集并把 JSON 报告写到显式指定路径。

首期不拆分额外的工厂、注册表、指标插件或报告渲染层。

核心接口保持简单：

```python
evaluator = RetrievalEvaluator(
    retrieve=retrieve,
    ks=[1, 3, 5, 10],
    min_recall=0.8,
)
report = await evaluator.evaluate(dataset)
```

其中 `retrieve(query, limit)` 由脚本闭包绑定当前数据集的 `db`、`uid` 和
`kb_id`，并调用 `knowledge_service.search(...)`。评估器只消费排序后的检索命中，
不读取数据库配置。

## 8. 报告格式

JSON 报告至少包含：

```json
{
  "run": {
    "dataset_id": "product_manual_retrieval",
    "dataset_version": "v1",
    "corpus_version": "2026-08-03",
    "kb_id": "真实知识库标识",
    "embedding_model_spec": "provider/model",
    "embedding_dimension": 1024,
    "ks": [1, 3, 5, 10]
  },
  "summary_by_k": [
    {
      "split": "validation",
      "k": 3,
      "query_count": 40,
      "hit_rate": 0.9,
      "precision": 0.7,
      "recall": 0.82,
      "f1": 0.75
    }
  ],
  "selection": {
    "recommended_top_k": 3,
    "min_recall": 0.8,
    "recall_target_met": true,
    "selected_on": "validation"
  },
  "test_result": {
    "k": 3,
    "query_count": 20,
    "hit_rate": 0.85,
    "precision": 0.68,
    "recall": 0.8,
    "f1": 0.73
  },
  "queries": []
}
```

上面的数值只展示字段结构，不是项目当前检索质量。实际报告中的每条查询还应包含：

- `query_id`、`split` 和查询文本。
- `relevant_chunk_ids`、`retrieved_chunk_ids`、`matched_chunk_ids`。
- 各命中的 `rank`、`distance` 和 `file_id`。
- 每个 K 的 Hit、Precision、Recall 和 F1。

## 9. 验证要求

实现阶段至少需要：

- 用手算样例覆盖全命中、部分命中、零命中、重复返回和少于 K 个返回结果。
- 验证同一排序结果在多个 K 下只做前缀切片，每条查询只检索一次。
- 验证宏平均和 Top-K 选择规则，包括 F1 并列时选择较小 K。
- 验证空 Ground Truth、重复 `query_id`、非法 K 和缺失 `chunk_id` 会明确失败。
- 用假的异步检索函数完成默认自动化测试；真实 PostgreSQL、Embedding 和 Milvus
  运行作为显式集成评估，不混入默认单元测试。

## 10. 首期不做

- 不评估回答忠实度、答案正确性或 CitationAgent 的引用质量。
- 不用 Ragas、LLM 或字符串相似度替代人工 Ground Truth。
- 不自动生成或伪造测试问题和相关分块。
- 不在评估器内修改 Embedding、Chunker、Milvus 索引或生产配置。
- 不把延迟、Token 成本等运行指标混入 Recall/F1；如需记录，可作为独立诊断字段。
- 不做按查询动态选择 K；首期只给出一个可解释、可复现的全局生产候选值。
