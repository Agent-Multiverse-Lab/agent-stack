# 通用 Reranker 与 DashScope 适配器设计

状态：首期代码已实现，真实 DashScope 请求尚未执行。

## 1. 目标与结论

在 `src/model/` 下实现一个面向检索结果的通用 Reranker 模型层，首个 Provider
接入 DashScope `qwen3-rerank`，并允许以后增加其他云端或本地重排模型。

首期结论：

- Embedding 和 Reranker 是两个独立模型能力，不能共用 `Embeddings` 接口。
- DashScope Embedding 继续负责查询向量生成和 Milvus 初召回。
- DashScope `qwen3-rerank` 接收“查询 + 候选分块文本”，返回新的相关性分数和排序。
- Reranker 的通用契约、DashScope 适配器和构造入口放在 `src/model/`。
- 候选检索、业务字段映射和最终结果组装仍由
  `server/service/knowledge_service.py` 协调。
- 首期通过现有 `httpx` 直接调用 DashScope HTTP 接口，不增加 DashScope SDK、
  LlamaIndex 或其他 Rerank 依赖。
- Rerank 地址完整配置在 `.env`，代码不根据 Embedding 地址拼接或转换 URL。

## 2. Embedding 与 Reranker 的边界

两阶段职责如下：

| 能力 | 输入 | 输出 | 所处阶段 |
|---|---|---|---|
| Embedding | 查询文本或知识分块 | 向量 | 建库和初召回 |
| Reranker | 查询文本和候选分块文本 | 每个候选的相关性分数与新排名 | 初召回之后 |

目标链路：

```text
query
  -> DashScope Embedding
  -> Milvus 向量检索 candidate_limit 条
  -> 通用 BaseReranker
  -> DashScopeReranker
  -> final top_k 条
  -> knowledge_service.search(...) 返回结果
```

Reranker 不生成向量，也不参与知识库索引。即使 Embedding Provider 以后切换为
OpenAI，本项目仍可独立使用 DashScope Reranker；反过来也一样。

## 3. 当前实现基础

当前代码已经具备：

- `src/configs/config.py` 中已有 `rerank_model`，对应环境变量
  `RERANK_MODEL`，但尚未被使用。
- `src/model/model_tool.py` 已按 `provider/model` 解析和构造聊天模型及
  Embedding 模型。
- `src/configs/model.py` 已有独立的 `EmbeddingModelProvider` 配置。
- `knowledge_service.search(db, ...)` 会使用知识库绑定的 Embedding 模型生成查询
  向量，再调用 `MilvusKnowledge.search(...)`。
- Milvus 命中包含 `chunk_id`、`chunk`、`file_id`、`chunk_index` 和向量
  `distance`，能够无损转换为 Rerank 候选。
- 项目已经显式依赖 `httpx`。

当前尚不存在：

- Reranker 的输入、输出和异常契约。
- Rerank Provider 配置与构造函数。
- DashScope Rerank HTTP 适配器。
- 初召回数量与最终 `top_k` 的区分。
- Rerank 分数和原始向量分数的并存输出。

## 4. 模型层通用契约

### 4.1 RerankDocument

`RerankDocument` 表示一个与 Provider 无关的候选文档：

```python
@dataclass(frozen=True, slots=True)
class RerankDocument:
    id: str
    text: str
    original_rank: int
    retrieval_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

字段含义：

- `id`：稳定业务标识；知识库场景使用 `chunk_id`。
- `text`：真正发送给 Rerank Provider 的分块文本。
- `original_rank`：初召回中的排名，从 1 开始。
- `retrieval_score`：Milvus 原始向量分数，仅用于诊断，不参与通用 Rerank
  排序逻辑。
- `metadata`：保留 `file_id`、`chunk_index` 等业务字段。

### 4.2 RerankResult

```python
@dataclass(frozen=True, slots=True)
class RerankResult:
    document: RerankDocument
    relevance_score: float
    rerank_rank: int
```

`relevance_score` 只保证是有限浮点数，不承诺不同 Provider、不同模型之间具有
相同量纲。不能用一个未经评估的全局阈值横跨多个模型。

结果必须按 `relevance_score` 降序排列；分数相同时使用 `original_rank` 保持
确定性顺序。

### 4.3 BaseReranker

```python
class BaseReranker(ABC):
    @abstractmethod
    async def arerank(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> list[RerankResult]:
        ...
```

统一约束：

- `query` 必须是非空文本。
- `documents` 必须非空，`id` 必须唯一，`text` 必须非空。
- `top_n` 必须大于 0；超过候选数量时按候选数量处理。
- 返回结果中的文档只能来自输入候选，不能由 Provider 新建或改写。
- 返回文档不得重复，`rerank_rank` 必须连续并从 1 开始。
- Provider 返回的索引、分数或数量不合法时立即失败。

通用接口首期不暴露 `instruct`、`return_documents` 等 Provider 参数。Provider
差异由适配器内部处理，避免业务层依赖 DashScope 请求格式。

## 5. 模型解析与构造

沿用当前 `provider/model` 规则：

```text
dashscope/qwen3-rerank
```

计划在 `src/configs/model.py` 增加独立的 `RerankModelProvider`，不要扩展
`EmbeddingModelProvider`：

```python
class RerankModelProvider(BaseModel):
    name: str
    api_key_field: str
    endpoint_field: str
```

`src/model/model_tool.py` 增加：

```python
def resolve_rerank_model(
    model: str | None = None,
) -> tuple[str, str, RerankModelProvider]:
    ...


def load_reranker(model: str | None = None) -> BaseReranker:
    ...
```

行为约束：

- `resolve_rerank_model` 从显式参数或 `config.rerank_model` 读取模型规格。
- 模型为空、格式错误、Provider 未注册、API Key 或 URL 缺失时明确报错。
- `load_reranker` 只负责模型构造，不查询数据库、不调用 Milvus。
- 是否启用 Rerank 由 `knowledge_service.search(...)` 根据 `RERANK_MODEL` 是否为空显式判断；
  不创建 `NoOpReranker`。
- 首期使用简单的 Provider 映射和显式分支，不建立插件系统或动态注册框架。

以后新增 Provider 时，只需要增加 Provider 配置、一个适配器和一个构造分支，
`knowledge_service.py` 的检索函数与 Rerank 数据结构保持不变。

## 6. DashScopeReranker

### 6.1 首期模型选择

首期只支持文本模型 `qwen3-rerank`。DashScope 官方文档已经将它作为当前文本
Rerank 模型，并说明旧 `gte-rerank` 于 2026 年 5 月 30 日停止服务，因此不把
旧模型作为兼容目标。

多模态 `qwen3-vl-rerank` 的输入、接口和资源限制不同，不混入首期文本契约。

### 6.2 HTTP 请求

使用配置中的完整 `DASHSCOPE_RERANK_URL` 发起请求：

```http
POST https://<workspace-id>.cn-beijing.maas.aliyuncs.com/compatible-api/v1/reranks
Authorization: Bearer <DASHSCOPE_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "qwen3-rerank",
  "query": "用户查询",
  "documents": [
    "候选分块一",
    "候选分块二"
  ],
  "top_n": 2
}
```

首期不传 `instruct`，使用官方默认的问答检索排序策略。以后确有 FAQ 相似度或
专用排序需求时，再为通用契约设计稳定的任务模式，不能直接把任意 DashScope
参数透传到业务层。

### 6.3 响应归一化

`qwen3-rerank` 返回的核心结构为：

```json
{
  "results": [
    {
      "index": 0,
      "relevance_score": 0.93
    }
  ],
  "model": "qwen3-rerank",
  "id": "provider-request-id",
  "usage": {
    "total_tokens": 79
  }
}
```

`DashScopeReranker` 按 `index` 找回原始 `RerankDocument`。它不能依赖 Provider
回传文档正文，因为业务标识、Metadata 和原始向量分数只存在于本地候选对象。

归一化时校验：

- `results` 必须是列表。
- `index` 必须是未重复且位于候选范围内的整数。
- `relevance_score` 必须是有限数值。
- 返回数量必须等于 `top_n` 与候选数量中的较小值。
- 最终结果按分数降序、原始排名升序稳定排序。

### 6.4 官方限制的处理

当前官方文档给出的 `qwen3-rerank` 限制包括：

- 单次最多 500 个候选文档。
- 查询和单个文档最多 4,000 Token。
- 单次请求最多 120,000 Token。

首期只在本地严格校验候选数量。项目没有与该模型完全一致的本地 Tokenizer，
因此不使用字符数假装精确 Token 数，也不静默截断文本。

候选超限时直接报错，不自动拆成多批。不同批次的分数未必可以安全地进行全局
比较，自动分批会改变“对同一候选集统一排序”的语义。

### 6.5 HTTP 客户端

- 使用现有 `httpx.AsyncClient`，不增加 SDK 依赖。
- 允许测试注入 Mock Client。
- 默认客户端生命周期限定在一次 `arerank(...)` 调用内，确保连接被关闭；只有
  在真实性能数据证明需要时，再提升为进程级共享客户端。
- 使用明确的请求超时，不做无限等待。
- 首期不自动重试请求，避免隐藏限流、重复计费和延迟问题。

## 7. 环境配置

计划在 `.env` 和 `.env.template` 中配置：

```dotenv
RERANK_MODEL=dashscope/qwen3-rerank
DASHSCOPE_RERANK_URL=https://<workspace-id>.cn-beijing.maas.aliyuncs.com/compatible-api/v1/reranks
RERANK_REQUEST_TIMEOUT_SECONDS=30
RERANK_CANDIDATE_LIMIT=50
DASHSCOPE_API_KEY=
```

配置边界：

- `DASHSCOPE_API_KEY` 可与 DashScope Embedding 共用。
- `DASHSCOPE_RERANK_URL` 必须是部署环境可访问的完整 Rerank 地址。
- 不复用 `EmbeddingModelProvider.base_url`，也不在代码中从 Embedding URL
  生成 Rerank URL；DashScope 不同接口的路径形式并不相同。
- `RERANK_CANDIDATE_LIMIT` 是初召回数量，`KnowledgeSearchRequest.limit`
  继续表示最终返回数量。
- 50 只是首轮评测起点，不是未经验证的永久默认值；应结合检索评估集调整。
- 首期不配置 `RERANK_SCORE_THRESHOLD`。不同模型的分数需要先用真实评测数据
  校准，不能直接假设 0.5 或其他值有效。

`Config` 只负责读取和校验这些值，不构造 Reranker 或执行请求。

## 8. knowledge_service 接入

核心 Reranker 实现位于 `src/model/`，实际检索协调仍在
`knowledge_service.search(db, ...)`：

```text
RERANK_MODEL 为空
  -> Milvus 按 limit 检索
  -> 原样返回当前结果

RERANK_MODEL 已配置
  -> candidate_limit = max(limit, RERANK_CANDIDATE_LIMIT)
  -> Milvus 初召回 candidate_limit 条
  -> 转换为 RerankDocument
  -> reranker.arerank(query, documents, top_n=limit)
  -> 映射回知识库命中结构
  -> 返回最终 limit 条
```

这保持当前 HTTP 请求中的 `limit` 语义不变，无需让路由感知 Provider。

重排后每个命中应同时保留：

```json
{
  "chunk_id": "file-id:3",
  "chunk": "分块正文",
  "file_id": "file-id",
  "chunk_index": 3,
  "distance": 0.81,
  "retrieval_rank": 7,
  "rerank_score": 0.94,
  "rerank_rank": 1
}
```

不能用 `rerank_score` 覆盖 Milvus `distance`。两种分数含义不同，保留它们才能
进行诊断和 RAG 指标对比。

响应顶层还应增加：

```json
{
  "rerank": {
    "applied": true,
    "model_spec": "dashscope/qwen3-rerank",
    "candidate_count": 50,
    "result_count": 10
  }
}
```

Reranker 不写数据库，不修改 Milvus 数据，也不持久绑定到
`KnowledgeEmbeddingBinding`。Embedding 变化会使索引失效，而 Reranker 只影响
查询时排序，可以在不重建索引的情况下独立评估和切换。

Agent 和工具不得直接构造 `DashScopeReranker`；后续接入知识检索时应调用服务
获取已经重排的结果。

## 9. 失败与可观测性

增加统一的 `RerankError`，包装以下错误：

- 配置缺失或模型规格非法。
- DashScope 网络、超时、鉴权、限流和非成功 HTTP 状态。
- Provider 响应字段缺失或索引、分数非法。

首期不做静默降级。配置了 Reranker 但调用失败时，检索请求应失败，并由服务层使用
现有 `logger.exception(...)` 记录 `uid`、`kb_id`、模型规格、候选数量和 Provider
请求 ID 后重新抛出。不能返回向量结果却声称已经完成 Rerank。

日志和错误中不得记录：

- API Key 或 Authorization Header。
- 完整查询文本和候选文档正文。
- Provider 返回的可能包含敏感内容的完整响应体。

可记录的诊断字段包括模型规格、候选数量、输出数量、耗时、HTTP 状态码和 Provider
请求 ID。

## 10. 与 RAG 评估工具联动

[RAG 检索评估规格](../../knowledge/rag_eval/retrieval-evaluation.md) 中的检索评估应分别运行：

1. 仅向量检索的 Baseline。
2. 相同初召回候选上的 Rerank 结果。

报告额外记录：

- `rerank_model_spec`。
- `candidate_limit`。
- `final_top_k`。
- `rerank_applied`。

候选召回决定 Reranker 能看到哪些相关分块；Reranker 无法找回初召回中不存在的
证据。因此应先保证 `Recall@candidate_limit`，再比较重排后的 `Hit@K`、
`Precision@K`、`Recall@K` 和 `F1@K`。

`candidate_limit` 和最终 `top_k` 是两个不同参数：

- 用候选集 Recall 选择足够大的 `candidate_limit`。
- 用重排后 F1 和业务最低 Recall 选择最终 `top_k`。

不得只展示个别查询的排序改善后就宣称 Reranker 有效。

## 11. 实现文件

```text
doc/spec/src/model/reranker/
└── reranker.md

src/model/
├── __init__.py
├── model_tool.py
└── reranker/
    ├── __init__.py
    ├── base.py
    └── dashscope.py

src/configs/
├── config.py
└── model.py

server/service/
└── knowledge_service.py

test/
└── test_reranker.py
```

文件职责：

- `src/model/reranker/base.py`：`RerankDocument`、`RerankResult`、
  `BaseReranker` 和 `RerankError`。
- `src/model/reranker/dashscope.py`：DashScope HTTP 请求和响应归一化。
- `src/model/reranker/__init__.py`：统一导出契约和 Provider 适配器。
- `src/model/model_tool.py`：解析 `provider/model` 并构造适配器。
- `src/configs/model.py`：Provider 元数据。
- `src/configs/config.py`：读取环境配置。
- `server/service/knowledge_service.py`：初召回、Rerank 调用和业务结果组装。
- `test/test_reranker.py`：使用 Mock HTTP Transport 的确定性测试。

核心抽象和 Provider 代码全部位于 `src/model/`；服务文件只增加现有用例所需的
调用编排。

## 12. 验证要求

实现阶段至少验证：

- 空查询、空候选、重复 ID 和非法 `top_n`。
- DashScope 请求中的模型、查询、文档顺序和 `top_n` 正确。
- Provider 返回乱序结果时按分数稳定排序。
- 非法、重复或越界 `index` 被拒绝。
- 非有限 `relevance_score` 被拒绝。
- 业务 `chunk_id`、Metadata、原始 `distance` 和排名在重排后不丢失。
- `RERANK_MODEL` 为空时保持当前检索行为。
- Rerank 启用时，Milvus 使用 `candidate_limit`，最终只返回 `limit` 条。
- 超时、401、429、5xx 和畸形 JSON 不会被静默吞掉。
- `git diff --check` 和相关模块编译检查通过。

所有新函数和类按仓库规则添加简洁中文 Docstring。

## 13. 首期不做

- 不实现多模态 `qwen3-vl-rerank`。
- 不兼容已停止服务的旧 `gte-rerank`。
- 不实现批次拆分后跨批分数归并。
- 不增加插件发现、入口点或运行时动态注册系统。
- 不把 Reranker 绑定写入知识库数据库表。
- 不自动截断文档、不设置未经评估的分数阈值。
- 不修改 Agent、队列、Redis Stream 或 SSE 协议。

## 14. 官方参考

- [DashScope Rerank 使用说明](https://help.aliyun.com/en/model-studio/rerank)
- [DashScope 文本 Rerank API](https://help.aliyun.com/zh/model-studio/text-rerank-api)
- [Model Studio 知识库中的 Embedding 与 Rerank 边界](https://www.alibabacloud.com/help/en/model-studio/rag-knowledge-base)
