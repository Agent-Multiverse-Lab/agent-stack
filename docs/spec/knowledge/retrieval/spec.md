# Knowledge Retrieval Spec

## 1. Scope

定义检索时的执行顺序、排序语义和输入校验。

## 2. Requirements

### K-RET-001
检索必须先通过绑定模型获取候选，再做 rerank（存在 reranker 时）。

### K-RET-002
`limit` 必须为正整数，否则失败返回。

### K-RET-003
检索返回要包含用于显示的 metadata（文件名、chunk id、kb_id、uid）。

### K-RET-004
命中重排失败时可回退为未重排候选，但必须保持可观测错误。

## 3. Contract

`search(..., query, kb_id, limit)` -> `hits + optional rerank block`.

## 4. Acceptance

- 无有效 binding 时阻断搜索
- 命中必须有可追溯来源（collection + metadata）
