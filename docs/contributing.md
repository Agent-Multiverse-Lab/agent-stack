# 贡献与提交指南

## 贡献规则

- 遵循 `CONTRIBUTING.md` 中的仓库贡献流程。
- 除非任务明确要求其他语言，Pull Request 应包含简洁的中文摘要和动机说明。
- 有 issue 或任务 ID 时应附上链接。
- 写明执行过的验证命令及其结果。

## Git 提交规则

- 使用 Conventional Commits：`<type>(<scope>): <subject>`。
- `type` 必须是 `feat`、`fix`、`refactor`、`doc`、`test`、`chore`、`build` 或 `ci` 之一。
- 使用简洁的小写英文 scope，例如 `agent`、`thread`、`worker`、`auth` 或 `deps`。
- subject 及可选的 body 使用中文。subject 应简洁，最好不超过 72 个字符，且不要以标点结尾。
- 示例：
  - `feat(worker): 发布 Agent Run 流式事件`
  - `fix(auth): 修复令牌校验失败`
  - `doc(agent): 更新仓库代理指南`
- 不要使用 `@` 字符包裹 commit message、subject 或 scope。
- 推送前，尤其是在 PowerShell 中提交后，检查所有待推送的 subject 和 body，确认没有误加 `@` 包裹，
  如有则修正。
- 一个 commit 只聚焦一个完整一致的变更。
