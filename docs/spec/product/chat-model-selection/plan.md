# Plan: Chat Model Selection

计划版本：v0.1.0

## 1. Backend implementation

1. 新增 `src/model/model_cache.py`：集中负责展示字段构建与 Redis read-through cache。
2. 修改 `server/service/model_service.py` 与 Router，异步读取缓存目录。
3. 创建 Run 时校验 `thread_metadata.model`，Worker 合并持久化的 Run metadata，
   `thread_service._build_agent_runtime_context` 将模型写入 `BaseContext.model`。

目标：`src/model/model_cache.py::get_model_catalog`

```python
cached = await redis.get("model:catalog:v1")
if cached is valid:
    return cached
catalog = build_model_catalog()
await redis.set("model:catalog:v1", json.dumps(catalog), ex=3600)
return catalog
```

公开目录只包含选择器所需字段，不复制 Provider 密钥和连接信息；Redis 故障时回退 config。

## 2. Frontend implementation

1. 新增 `web/src/api/model.ts` 与 `web/src/types/model.ts`，读取模型目录。
2. 新增 `web/src/components/chat/models/ChatModelSelectComponent.vue`，实现紧凑 selector。
3. 修改 `ChatMessageInputComponent.vue`，在输入操作区组合 selector。
4. 新增 `web/src/stores/useModelStore.ts`，负责加载目录、选择默认模型和维护当前选择；
   `ChatView.vue` 只消费 Store，并在创建 Run 时传递 model ID。
5. 修改 `web/src/composables/useAgentRun.ts` 和 `web/src/api/agent.ts`，把 model ID 写入
   `thread_metadata.model`。

## 3. Validation

- 模型目录构建、cache hit、cache miss 和 Redis 故障回退单元测试。
- Agent Run model metadata 校验和持久化单元测试。
- 后端相关测试与 Python 编译检查。
- 前端定向 ESLint、`npm.cmd run typecheck`、`npm.cmd run build`。
- `git diff --check`（本次变更路径）。
