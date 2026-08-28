# Implementation Plan: Knowledge Ingestion

计划版本：v0.1.0

1. 上传：`upload_file` 只做落库与对象存储。
2. 解析：`parse_file` 在 `uploaded/failed` 下允许执行，写出 `parsed` 与 markdown object。
3. 索引：`index_file` 仅对 `parsed` 执行。
4. 索引失败回退到 `parsed`，并保留错误信息。

## Mapping

- `server/service/knowledge_service.py`: `upload_file`, `parse_file`, `index_file`
- `src/knowledge/flow/pipeline.py`: `parse_document`, `chunk_document`
- `src/database/repositories/knowledge_file_repository.py`: 状态更新
