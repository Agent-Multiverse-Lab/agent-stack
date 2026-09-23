# Implementation Plan: Knowledge Graph

计划版本：v0.1.0

1. 存储：Neo4j 承载实体节点与关系边；Milvus 实体集合承载实体向量（去重与检索）。
2. 抽取：独立 `extract` 接口，前端在 index 成功后调用；状态机扩展 `extracting -> extracted`，失败回退 `indexed`。
3. 管理：补齐 KB 列表/详情/删除与文件删除/预览接口，删除时级联清理外部存储。
4. 问答：同步 `chat` 接口，复用检索路径，返回答案与引用。

## Mapping

- `server/service/knowledge_service.py`: `extract_file`, `get_graph`, `search_entities`, `chat`, `delete_knowledge_base`, `delete_file`, `list_knowledge_bases`, `list_files`, `get_file_markdown`
- `src/knowledge/graph/extractor.py`: `GraphExtractor`
- `src/knowledge/store/neo4j/neo4j_store.py`: `Neo4jGraphStore`
- `src/knowledge/store/milvus/milvus.py`: `upsert_entities`, `search_entities`, `drop_collection`
- `src/storage/minio.py`: `adelete_objects_by_prefix`
- `server/router/knowledge_router.py`: 图谱与问答端点
