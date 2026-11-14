# 会话 Project 与置顶实施计划

## 当前任务

新增 `project` 表、Alembic 迁移、Project CRUD 接口、会话 `project_id` 归属与 `pinned_at` 置顶排序能力，并在前端侧栏插入专属的 Pinned 与 Projects 组件。

## 任务目标

1. 在 PostgreSQL/SQLAlchemy 层完成 `Project` 模型与 `Conversation.project_id`、`Conversation.pinned_at` 字段定义及迁移。
2. 提供 `/api/projects` 完整管理接口与事务级软删除解绑逻辑，并扩展 `/api/chat/thread` 创建、列表、更新接口。
3. 在前端侧栏新增 `NavPinned` 与 `NavProjectList` 专属组件并接入 `AppSidebar`，补齐前后端测试与静态检查。

## 如何修改

按职责读取当前实施切片：

- [持久化与 HTTP 合同](implementation/persistence-api.md)：CP-01 至 CP-04。
- [侧栏交互与同步](implementation/sidebar.md)：CP-05 至 CP-06。
- CP-07 按两份切片的验收场景执行测试，结果记录在 `tasks.md`。

- **数据模型与迁移**
  - 在 [models.py](../../../../src/database/models.py) 新增 `Project`，为 `Conversation` 添加 `project_id` 与 `pinned_at`，并在 [src/database/__init__.py](../../../../src/database/__init__.py) 导出 `Project`。
  - 新增 `migrate/versions/0030_project_and_pinned.py`（`down_revision = "0029_agent_run_execution"`），完成建表、加列、索引与 `downgrade()`。
- **Repository 层**
  - 新增 `src/database/repositories/project_repository.py` 并在 [src/database/repositories/__init__.py](../../../../src/database/repositories/__init__.py) 导出，提供按用户 CRUD、置顶优先排序及软删除时清空关联会话 `project_id`。
  - 在 [conversation_repository.py](../../../../src/database/repositories/conversation_repository.py) 扩展 `create_conversation`、`update_conversation` 与 `list_top_level_for_user` 的 `project_id` 过滤、`pinned_at` 优先排序及游标条件。
- **Service 与 Router 层**
  - 新增 `server/entities/project.py`、`server/service/project_service.py`、`server/router/project_router.py`，并注册到 [server/router/__init__.py](../../../../server/router/__init__.py)。
  - 扩展 [thread.py](../../../../server/entities/thread.py)、[thread_service.py](../../../../server/service/thread_service.py)、[thread_router.py](../../../../server/router/thread_router.py)，支持 `project_id` 校验绑定/解绑、`pinned` 切换与置顶分页游标。
- **前端 API 与侧栏组件**
  - 新增 `web/src/api/project.ts`，扩展 [web/src/api/thread.ts](../../../../web/src/api/thread.ts) 的字段类型、按项目筛选与 `updateThread` 更新方法。
  - 新增专属组件 `web/src/components/nav-pinned.tsx`（`NavPinned`）与 `web/src/components/nav-project-list.tsx`（`NavProjectList`），扩展 [nav-projects.tsx](../../../../web/src/components/nav-projects.tsx) 的会话菜单（置顶、移入/移出 Project），并在 [app-sidebar.tsx](../../../../web/src/components/app-sidebar.tsx) 中组合挂载并同步三块区域数据。

## 实施步骤

1. 修改 `src/database/models.py` 与 `src/database/__init__.py`，编写迁移 `migrate/versions/0030_project_and_pinned.py`。
2. 新增 `ProjectRepository` 并更新 `ConversationRepository` 的读写与列表排序/游标查询。
3. 新增 `server/entities/project.py`、`server/service/project_service.py`、`server/router/project_router.py` 并挂载到 `api_router`。
4. 更新 `server/entities/thread.py`、`server/service/thread_service.py`、`server/router/thread_router.py`。
5. 新增 `web/src/api/project.ts` 并扩展 `web/src/api/thread.ts`。
6. 新增 `NavPinned`、`NavProjectList` 专属组件，更新 `NavProjects` 菜单与 `AppSidebar` 挂载组合。
7. 编写后端单测与前端组件测试，运行后端 `pytest`、前端 `typecheck` / `lint` / `test` / `build` 与 `git diff --check`。

## 验收标准

- Alembic 迁移 `0030_project_and_pinned` 升降级无误，ORM 模型与数据库 Schema 一致。
- `/api/projects` 与 `/api/chat/thread` 的 CRUD、绑定/解绑、置顶优先排序、游标分页及越权隔离全部通过后端测试。
- 左侧边栏以独立组件展示 Pinned 区域、Projects 区域与 Conversations 区域，新建/重命名/删除 Project、会话加入/移出 Project、置顶与取消置顶操作后三块区域状态保持同步。
- 前端 `npm run typecheck`、`npm run lint`、`npm test`、`npm run build` 全部通过。
