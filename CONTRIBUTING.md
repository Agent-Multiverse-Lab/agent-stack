# Contributing Guide

## Commit Message Convention

This repository uses Conventional Commits.

Format:

```text
<type>(<scope>): <subject>
```

Examples:

```text
feat(agent): 接入流式响应接口
fix(thread): 处理空消息请求
refactor(config): 拆分模型配置
doc(readme): 补充后端启动步骤
chore(deps): 更新项目依赖
```

Rules:

- `type` should be one of: `feat`, `fix`, `refactor`, `doc`, `test`, `chore`, `build`, `ci`.
- `scope` is recommended and should describe the changed module, such as `agent`, `thread`, `worker`, `web`, or `deps`.
- Keep `type` and `scope` as lowercase English Conventional Commit tokens.
- Write the `subject` and optional commit body in Chinese. Keep the subject concise (recommended <= 72 characters) and do not end it with punctuation.
- Do not wrap commit messages, subjects, or scopes with `@` characters.
- Keep one commit focused on one change.

## Pull Request Checklist

- Include a short summary and motivation.
- Link the issue/task ID when available.
- For UI changes in `web/`, include screenshot(s) or video.
- Add verification notes (commands run and outcomes).
