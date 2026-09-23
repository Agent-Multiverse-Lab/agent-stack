# Tasks: Knowledge Graph

## Task Map

| Task ID | 需求 | 文件 | 说明 |
| --- | --- | --- | --- |
| KGR-001 | K-GRA-001/002 | `src/knowledge/graph/extractor.py` | flash 模型结构化输出与 JSON 回退 |
| KGR-002 | K-GRA-003 | `src/knowledge/store/neo4j/neo4j_store.py` | 实体/关系写入、全图查询、按文件/知识库删除 |
| KGR-003 | K-GRA-004/005 | `server/service/knowledge_service.py` | 实体向量写入、0.92 去重合并与重抽取清理 |
| KGR-004 | K-GRA-004/007 | `src/knowledge/store/milvus/milvus.py` | 实体集合懒创建、向量检索与集合删除 |
| KGR-005 | K-GRA-008/009 | `server/service/knowledge_service.py` | 文件与知识库删除的级联清理 |
| KGR-006 | K-GRA-010 | `server/service/knowledge_service.py` | 同步问答与引用组装 |
