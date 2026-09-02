# 贡献与提交指南

## Commit Message 规范

本仓库使用 Conventional Commits，格式：

```text
<type>(<scope>): <subject>
```

示例：

```text
feat(agent): 接入流式响应接口
fix(thread): 处理空消息请求
refactor(config): 拆分模型配置
doc(readme): 补充后端启动步骤
chore(deps): 更新项目依赖
```

规则：

- `type` 必须是 `feat`、`fix`、`refactor`、`doc`、`test`、`chore`、`build`、`ci` 之一。
- `scope` 建议使用简洁的小写英文模块名，例如 `agent`、`thread`、`worker`、`auth`、`deps`。
- subject 及可选的 body 使用中文。subject 应简洁（建议不超过 72 个字符），且不要以标点结尾。
- 不要使用 `@` 字符包裹 commit message、subject 或 scope。
- 一个 commit 只聚焦一个完整一致的变更。
- 推送前，尤其是在 PowerShell 中提交后，检查所有待推送的 subject 和 body，确认没有误加
  `@` 包裹，如有则修正。

## Pull Request 规范

- 包含简洁的中文摘要和动机说明（除非任务明确要求其他语言）。
- 有 issue 或任务 ID 时附上链接。
- `web/` 的 UI 变更附上截图或视频。
- 写明执行过的验证命令及其结果。

## GitHub Release

版本发布由维护者显式创建并推送语义版本 Tag 触发。Tag 去掉 `v` 前缀后必须与
`pyproject.toml` 中的项目版本一致。

首个版本的发布命令为：

```bash
git tag v0.1.0
git push origin v0.1.0
```

发布工作流会重新执行后端和前端构建检查；全部通过后创建正式的
GitHub Release，并由 GitHub 自动生成 Release Notes 和源码归档。该流程不部署应用，
也不发布容器镜像或语言包。
