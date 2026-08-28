# Implementation Plan: Knowledge Retrieval

计划版本：v0.1.0

1. 校验 `uid/kb_id/query/limit` 输入。
2. 读取 `KnowledgeEmbeddingBinding`，构建 embedding 并生成 query vector。
3. Milvus 检索候选并（必要时）调用 reranker。
4. 输出命中字段并返回给 caller。

## Mapping

- `server/service/knowledge_service.py: search`
- `src/model/*`: embedding 与 reranker 加载
- `src/knowledge/store/milvus/milvus.py`: 搜索入口
