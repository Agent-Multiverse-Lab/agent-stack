# Knowledge Graph Spec

## 1. Scope

定义知识文件实体关系抽取、图谱持久化、图谱查询与实体检索的能力边界。
图谱结构（实体 + 关系）存 Neo4j；实体向量存 Milvus 实体集合，仅用于抽取去重与实体检索。

## 2. 状态链

文件在 `indexed` 后可进入抽取：`indexed -> extracting -> extracted`。
`extracting` 失败退回 `indexed`（保留 `error_message`，可重试）；`extracted` 允许重抽取（先清理旧数据再全量重写）。

## 3. Requirements

### K-GRA-001
抽取必须使用快速模型结构化输出（`flash_model` + `with_structured_output`），失败回退 JSON 文本解析；单文件一次调用，Markdown 超过 60 000 字符时截断。

### K-GRA-002
抽取结果实体字段为 `name/type/description`，关系字段为 `source/target/type`（端点引用实体名称）；仅允许 `indexed/extracted` 状态的文件执行抽取。

### K-GRA-003
图谱结构必须持久化到 Neo4j：实体为 `Entity` 节点（`entity_id/kb_id/file_id/name/type/description`），关系统一用 `RELATED_TO` 类型、关系语义存 `type` 属性。

### K-GRA-004
实体向量必须写入按 `(uid, kb_id)` 隔离的 Milvus 实体集合（`kge_` 前缀 + 与分块集合相同的摘要），维度复用 `KnowledgeEmbeddingBinding.embedding_dimension`。

### K-GRA-005
抽取去重：实体名向量与库内已有实体 cosine 相似度 ≥ 0.92 时合并到已有实体，不新建节点；名称（casefold 去空格）在单次抽取结果内去重。

### K-GRA-006
图谱查询返回全量 `{nodes, edges, entity_count, relation_count}`，只读 Neo4j。

### K-GRA-007
实体检索通过 Milvus 实体集合向量搜索，返回 `entity_id/name/type/description/file_id/similarity`；集合不存在时返回空命中。

### K-GRA-008
删除文件必须清理：Neo4j 该文件实体及关系、Milvus 分块与实体集合中该 `file_id` 的记录、RustFS 对象前缀；处理中（`parsing/indexing/extracting`）禁止删除。

### K-GRA-009
删除知识库必须清理：两个 Milvus 集合 drop、Neo4j 全部节点边、RustFS 对象前缀（外部清理尽力而为），PostgreSQL 行为权威删除。

### K-GRA-010
知识库问答为同步接口：检索命中 → 组装引用（`file_id/file_name/chunk_id/excerpt`）→ LLM 生成答案，答案只依据片段、句末标注 [n]；无命中时不调用 LLM，返回固定答语。

## 4. 示例

```python
await extract_file(db, uid=uid, kb_id=kb_id, file_id=file_id)
await get_graph(db, uid=uid, kb_id=kb_id)
await search_entities(db, uid=uid, kb_id=kb_id, query=query, limit=20)
await chat(db, uid=uid, kb_id=kb_id, query=query, limit=8)
```

## 5. Acceptance

- 未 `indexed` 的文件不能进入 `extracting`
- 抽取失败后文件回到 `indexed` 且可重试，重抽取不残留旧实体
- 相似实体合并后关系指向同一 `entity_id`
- 图谱/实体检索/问答均按用户隔离，跨用户不可见
