# Knowledge System Architecture

## 1. Responsibility

管理知识库文件生命周期：上传 -> 解析 -> 切块 -> 向量化 -> 索引 -> 检索/重排。

## 2. Pipeline Components

- `server/service/knowledge_service.py`：服务编排（上传、解析、索引、检索）。
- `src/knowledge/flow/pipeline.py`：解析与切块流水线。
- `src/knowledge/store/milvus/milvus.py`：Milvus 索引存取。
- `src/knowledge/embedding_service.py`：Embedding 查询服务。

## 3. Binding Rules

- 每个 `uid+kb_id` 有固定 `KnowledgeEmbeddingBinding`，记录模型规格与向量维度。
- 绑定发生变化时，检索必须与已有向量维度一致。

## 4. State Model

文件状态链：`uploaded -> parsing -> parsed -> indexing -> indexed`，失败回退到 `failed` 或 `parsed`。

## 5. Search Flow

1. 读取检索向量
2. 从 Milvus 取候选
3. 可选重排（Reranker）
4. 返回 `knowledge_record` + `metadata`

## 6. Boundaries

- 索引阶段必须持久化绑定，禁止隐式重建绑定。
- 搜索服务只读 Milvus，不在搜索路径中直接写入向量数据。
