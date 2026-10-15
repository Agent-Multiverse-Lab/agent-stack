# 模型列表与选择

## 目标

用全局 Provider 数据替换静态 Chat 模型列表，同时保持现有 `/api/models` 响应和 ModelContext 消费方式。

## 实施

1. Model Service 查询 `is_enabled=true` 的 Provider，投影公开 `ChatModelItem`，不携带连接参数。
2. 组合 ID 使用 `provider/model`；Provider 稳定排序，模型保留管理员保存顺序。
3. 协议工厂支持的模型标记为 `is_available=true`；默认、Fallback 和 Flash 只引用可执行项。
4. 使用 `model:chat:list:v3` 和一小时 TTL；缓存整体通过 `ChatModelListResponse` 校验。
5. `GET /api/models` 先读 Redis，缺失或无效时读 PostgreSQL 并回填；Redis 故障直接返回数据库投影。
6. Provider 提交后删除旧 key，再从已提交数据重建；启动补齐后预热一次。
7. ModelContext 保持登录后加载、可执行默认项选择和账号切换清理；不增加前端硬编码回退。

## 公开字段边界

Redis 和 HTTP 模型列表只保存展示、选择和角色标记。Base URL、API Key、额外请求头、请求体覆盖、
`has_api_key`、ORM 对象和 ChatModel 对象均不进入该列表。

## 验证

- PostgreSQL 投影顺序、ID、展示字段和默认角色。
- Redis hit、miss、过期、损坏、读写失败与提交后刷新。
- 空列表、无可执行模型、禁用项和 Provider 更新后的 ModelContext 状态。
- 两个登录用户读取相同响应，响应与缓存不含敏感字段。
