# AskUser 组件重设计与 Composer 对齐

计划版本：v0.7.0

## 当前任务

重新设计 `web/src/pages/chat/components/AskUser.tsx`，去除开发性描述文案，使其在 `ChatPage` 底部输入区内与 `AgentMessageComposer` 100% 等宽对齐。

## 任务目标

1. 移除 `AskUser` 的 `max-w-[36rem]` 宽度限制，占满 `ChatPage` 底部 `max-w-[800px]` 容器，并与 `AgentMessageComposer` 对齐圆角（`rounded-[1.4rem]`）、边框（`border-border`）、背景（`bg-card`）与轻量阴影。
2. 删除开发性描述文案（顶部 `Input required`、`Agent needs your choice` 标题栏、题干下方 `Choose an option, then continue. You can go back to change it.` 说明及必填场景下的 `Skip` 按钮）。
3. 题干与进度（`Question {{current}} of {{total}}`）同处顶部行，内容区改为自适应高度（`max-h-[min(18rem,40dvh)]`）。

## 如何修改

- `web/src/pages/chat/components/AskUser.tsx`：移除 `<header>`、`QuestionnaireDescription`、`QuestionnaireSkip` 及 `max-w-[36rem]`、`h-[min(22rem,45dvh)]`；调整卡片样式与 `AgentMessageComposer` 一致。
- `web/src/i18n.ts`：清理已移除的开发性描述翻译键。
- `web/src/pages/chat/components/AskUser.test.tsx`：验证等宽样式、无开发性描述文案以及分页答题与切换保留行为。
- `docs/spec/run/interrupt-resume/spec.md`：同步 `RUN-HIL-010` 前端容器与对齐契约。

## 实施步骤（计划）

1. 更新 `docs/spec/run/interrupt-resume/spec.md` 中 `RUN-HIL-010` 契约。
2. 修改 `AskUser.tsx` 与 `i18n.ts`。
3. 更新 `AskUser.test.tsx` 并执行单测与前端静态检查。

## 验收标准

- `npx vitest run src/pages/chat/components/AskUser.test.tsx --environment jsdom` 通过。
- `npm run typecheck`、`npm run lint`、`npm run build` 通过。
- `git diff --check` 无格式错误。
