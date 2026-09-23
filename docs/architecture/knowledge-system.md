# Knowledge System Architecture

## 1. Responsibility

管理知识库文件生命周期：上传 -> 解析 -> 切块 -> 向量化 -> 索引 -> 检索/重排。

行为规格入口：

- [Knowledge Ingestion Spec](../spec/knowledge/ingestion/spec.md)
- [Knowledge Retrieval Spec](../spec/knowledge/retrieval/spec.md)
- [Knowledge Evaluation Spec](../spec/knowledge/evaluation/spec.md)

## 2. Pipeline Components

- `server/service/knowledge_service.py`：服务编排（上传、解析、索引、检索、图谱抽取、问答）。
- `src/knowledge/flow/pipeline.py`：解析与切块流水线。
- `src/knowledge/graph/extractor.py`：实体关系结构化抽取。
- `src/knowledge/store/milvus/milvus.py`：Milvus 分块与实体向量存取。
- `src/knowledge/store/neo4j/neo4j_store.py`：Neo4j 图谱结构存取。
- `src/knowledge/embedding_service.py`：Embedding 查询服务。

## 3. Binding Rules

- 每个 `uid+kb_id` 有固定 `KnowledgeEmbeddingBinding`，记录模型规格与向量维度。
- 绑定发生变化时，检索必须与已有向量维度一致。
- 实体向量复用同一绑定的维度，实体集合与分块集合共用摘要命名。

## 4. State Model

文件状态链：`uploaded -> parsing -> parsed -> indexing -> indexed`，失败回退到 `failed` 或 `parsed`。
`indexed` 后追加图谱抽取：`indexed -> extracting -> extracted`，`extracting` 失败回退 `indexed`（可重试）。

## 5. Search Flow

1. 读取检索向量
2. 从 Milvus 取候选
3. 可选重排（Reranker）
4. 返回 `knowledge_record` + `metadata`
5. 问答在命中之上组装引用并由 LLM 生成答案；实体检索走独立实体集合

## 6. Boundaries

- 索引阶段必须持久化绑定，禁止隐式重建绑定。
- 搜索服务只读 Milvus，不在搜索路径中直接写入向量数据。

## 7. Capability Ownership

| 能力 | 承载位置 | 责任边界 |
| --- | --- | --- |
| 上传、解析、索引和检索编排 | `server/service/knowledge_service.py` | 协调数据库、对象存储、Embedding 和向量库 |
| Parser/Extractor/Chunker 流程 | `src/knowledge/flow/` | 只交换规范化 block/chunk 结构，不写业务记录 |
| 实体抽取 | `src/knowledge/graph/extractor.py` | 结构化输出与 JSON 回退，不接触存储 |
| Embedding 批处理和校验 | `src/knowledge/embedding_service.py` | 使用注入的 Embeddings，不选择 Agent 或 Provider 业务配置 |
| 向量存取 | `src/knowledge/store/milvus/milvus.py` | 接收已嵌入记录并负责 Milvus CRUD，不读取对象存储 |
| 图谱结构存取 | `src/knowledge/store/neo4j/neo4j_store.py` | 实体节点与关系边 CRUD，不参与抽取与去重 |
| 文件状态和绑定 | `src/database/`、`KnowledgeEmbeddingBinding` | PostgreSQL 保存权威状态和模型/维度绑定 |

上传原始 `Attachment` 与知识库 `KnowledgeFile` 是两条不同边界；Worker 不把聊天附件
隐式转换成解析、切块或 Milvus 记录。
