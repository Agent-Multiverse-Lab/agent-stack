# 会话 Project 与置顶实施任务

- [x] CP-01：在 `src/database/models.py` 新增 `Project` 并为 `Conversation` 增加 `project_id` 与 `pinned_at`，完成迁移 `0030_project_and_pinned.py`。
- [x] CP-02：实现 `ProjectRepository`，扩展 `ConversationRepository` 的 `project_id` 过滤、置顶优先排序与游标查询。
- [x] CP-03：新增 `/api/projects` 的 Schema、Service 与 Router，覆盖创建、列表、更新、置顶与软删除解绑。
- [x] CP-04：扩展 `/api/chat/thread` 的 Schema、Service 与 Router，支持 `project_id` 绑定/移出/筛选及会话置顶排序。
- [x] CP-05：新增 `web/src/api/project.ts` 并扩展 `web/src/api/thread.ts` 对接 `project_id` 与 `pinned`。
- [x] CP-06：新增 `NavPinned` 与 `NavProjectList` 专属侧栏组件，更新 `NavProjects` 菜单并插入 `AppSidebar`。
- [ ] CP-07：补齐后端单测与前端组件测试，执行 `pytest`、前端 `typecheck` / `lint` / `test` / `build` 与 `git diff --check`。

## 验证记录

- 后端定向验证：`test_chat_projects.py`、`test_thread_conversation_service.py`、`test_subagent_conversation_relation.py`、`test_thread_message_persistence.py`、`test_agent_run_execution_schema.py`、`test_agent_run_request_dispatch.py`，59 passed、24 subtests passed、32 skipped。执行时隔离未调用的 Agent 注册与其他路由初始化，以避开本机 SSL/Numba/文档解析依赖的加载问题；Project、Thread 路由及其 Service、Repository 使用实际实现。
- SQLite 已验证迁移升级/降级、已有会话保留、外键定义、归组与解绑、软删除事务回滚、用户隔离和置顶分页边界。PostgreSQL 专用用例因未配置独立测试库而跳过；业务数据库尚未执行迁移。
- 前端定向验证：`chat-projects.test.tsx` 与 `nav-projects.test.tsx` 共 8 项通过，覆盖项目管理、归组同步、置顶恢复及操作失败。
- `npm run typecheck`、`npm run build`、变更文件 ESLint、后端变更文件 Ruff、`compileall` 与 `git diff --check` 通过。编译检查使用独立缓存目录，避免已有 `__pycache__` 的权限限制。
- Edge 浏览器验证通过：创建/重命名项目、会话归组、项目与会话置顶、刷新恢复、打开项目、直接取消置顶、删除项目后会话返回列表；无页面错误。验证使用真实前端页面和模拟 API 数据。
- 全量 `npm run lint` 未通过：既有 `ArtifactCard.tsx:199`、`ChunksPanel.tsx:136` 使用原生按钮，被现有规则禁止。
- 全量 `npm test` 未通过：既有 `KnowledgeBaseDetailPage.test.tsx` 的 17 项测试失败，mock 缺少 `listKnowledgeFolders` 与 `listKnowledgeTasks`。本次未修改这些知识库测试及页面。

CP-01 至 CP-06 已完成。CP-07 保留待验收状态，待全量检查的问题处理后归档当前计划。
