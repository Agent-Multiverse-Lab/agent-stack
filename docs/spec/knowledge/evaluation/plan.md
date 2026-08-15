# Implementation Plan: Knowledge Evaluation

1. 将评估逻辑作为可选脚本与独立任务，不影响主请求路径。
2. 统一评估输入 schema（query/ground truth/response）。
3. 记录模型版本与重现参数（seed、rerank/model）。

## Mapping

- `src/knowledge/rag_eval/*`（如启用）
- 独立的评估脚本/任务入口（仓库中可新增）
