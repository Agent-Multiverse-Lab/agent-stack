# Implementation Plan: 影像 OGC 发布控制面

计划版本：v0.1.0

## 1. Scope

实现 DP-OGC-001 至 DP-OGC-006 的最小端到端控制面：复用现有卫星影像目录，新增五张发布表，由 Go Gateway
提供受控读写接口，并由现有 SatelliteAgent 调用。DP-OGC-007 的 renderer 只保留边界，本版本不实现 WMTS/WMS
像素服务。

## 2. Implementation order

1. 按 [control-plane-data.md](implementation/control-plane-data.md) 新增 Alembic 迁移和关系约束，并准备最小 fixture。
2. 按 [gateway-runtime.md](implementation/gateway-runtime.md) 增加 service/layer/theme 查询与状态迁移；先完成读取，再完成写入。
3. 按 [agent-runtime.md](implementation/agent-runtime.md) 将工具接入 SatelliteAgent，并把修改工具加入 HIL 审批集合。
4. 完成静态、数据库、Go、Python 和 Agent 合同测试；真实 OGC renderer 留给后续独立计划。

## 3. Shared constraints

- Alembic 是唯一 schema owner；不修改历史迁移，Gateway 启动不执行 DDL。
- `project_id`、`user_id`、`run_id` 来自受信运行时，不进入模型可填写 schema。
- catalog 是影像事实来源，发布表只存引用与渲染/发布配置。
- 发布与取消发布使用版本条件更新；引用冲突或跨项目关系在事务提交前失败。
- 第一版只支持结构化样式字段，不执行用户脚本，也不接受任意 SQL/正则/JMESPath。
- 控制面可在 renderer 缺席时独立验收，但 API 和 Agent 输出必须明确实际服务可用性。

## 4. End-to-end example

`src/agents/subagents/satellite_agent.py`（或当前 SatelliteAgent 构造入口）收到“把某范围内最新低云量影像发布为图层”后：

1. 调用 `search_scenes` 获取有界候选集并向用户解释选择依据。
2. 调用 `create_layer` 和 `attach_scene_to_layer` 前触发 HIL；Gateway 验证候选 asset 与项目归属。
3. 调用 `publish_layer(expected_version=...)`；Gateway 原子更新状态和审计字段。
4. 若 renderer 未部署，Agent 返回“发布配置已生成，OGC 服务尚不可访问”，不得返回虚构的瓦片地址。

## 5. Failure handling

- catalog asset 不存在、质量不可处理、跨项目或跨 service 引用时，事务整体失败。
- 乐观并发版本不匹配时返回冲突，不自动覆盖当前配置。
- HIL 拒绝或 Run 取消时不执行修改调用。
- renderer 或缓存服务不可用不回滚已经明确完成的控制面变更，但结果必须分别报告控制面与数据面状态。

## 6. Validation

- Alembic upgrade/downgrade 在临时 PostgreSQL/PostGIS 数据库执行。
- `go test ./...` 验证 Gateway store/service/gRPC 合同。
- Python focused tests 验证工具参数、受信上下文注入、HIL 和 Agent 提示词。
- `ruff check`、`python -m py_compile`、`git diff --check`。
- 真实 RustFS/PostGIS/Gateway 集成测试单独记录；本版本不以 WMTS/WMS 图像响应作为完成条件。
