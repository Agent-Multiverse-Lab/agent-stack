# RAG

RAG 负责把知识文件转换为可检索的知识，并为 Agent 提供检索结果。

## 主链路

```text
上传知识文件
  -> Parser 解析为 Markdown
  -> 显式确认索引
  -> Chunker 分块
  -> Embedding 向量化
  -> Milvus 建立索引
  -> Agent 检索知识
```

解析、分块、向量化、索引和检索连续但独立；上传文件先完成解析，显式确认后才进入索引，检索结果作为 Agent 的外部证据输入。

## 主要设施示例

| 文件 / 类 | 角色 | 主要参数 |
| --- | --- | --- |
| `server/service/knowledge_service.py::KnowledgeService` | 协调上传、解析、索引和检索 | `upload_file(uid, kb_id, file_name, content)`、`parse_file(uid, kb_id, file_id)`、`index_file(uid, kb_id, file_id)`、`search(uid, kb_id, query, limit)` |
| `src/knowledge/flow/pipeline.py::Pipeline` | 连接 Parser 和 Chunker | `parse_document(file_source, file_name)`、`chunk_document(document, chunker, title_method, target_level, chunk_token_size)` |
| `src/knowledge/flow/parser/parser.py::Parser` | 按 `file_name` 后缀选择格式解析器 | `parser_method="plain"` 或 `"ocr"`，`parse(file_source, file_name)` |
| `src/knowledge/embedding_service.py::EmbeddingService` | 批量向量化并校验维度 | `embedding_model`、`model_spec`、`batch_size`、`expected_dimension` |
| `src/knowledge/store/milvus/milvus.py::MilvusKnowledge` | 保存已向量化分块并执行向量检索 | `build_file_index(collection_name, file_id, dimension, records)`、`search(collection_name, vector, limit)` |
