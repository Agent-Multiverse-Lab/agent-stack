# Knowledge Ingestion Spec

## 1. Scope

定义知识文件从上传到向量索引的状态边界。

## 2. 状态链

`uploaded -> parsing -> parsed -> indexing -> indexed`

`parsed` 失败退回：`failed`（文件可重试）；`indexing` 失败退回 `parsed`。

## 3. Requirements

### K-ING-001
解析必须持久化 Markdown 到 MinIO，并更新 `status`。

### K-ING-002
索引必须先读取 `parsed` Markdown，不能直接对未解析原文件重建索引。

### K-ING-003
索引流程绑定 embedding 规格，避免维度漂移。

### K-ING-004
每一步失败必须回写失败原因 (`error_message`)。

## 4. 示例

```python
await parse_file(db, uid=uid, kb_id=kb_id, file_id=file_id)
await index_file(db, uid=uid, kb_id=kb_id, file_id=file_id)
```

## 5. Acceptance

- 未解析文件不能进入 `indexing`
- 重试时不会重复污染旧分片元数据
- 每次状态变更可追溯到数据库记录
