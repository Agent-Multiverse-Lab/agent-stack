# Navigation 图标按钮 Tooltip 规格

## 目标行为

`NavigationView.vue` 中所有仅以图标表达含义的可见按钮使用 Ant Design Vue
`ATooltip` 显示操作名称。现有侧栏图标按钮保持当前 Tooltip；右上角
`More options` 按钮补充同样的 Tooltip，悬停或键盘聚焦时显示
`More options`。

Tooltip 文案与按钮现有 `aria-label` 保持一致。右上角 Tooltip 使用
`placement="bottom"`，其内部 `ADropdown` 继续使用 `bottomRight` 和点击触发。

## 边界与公开契约

- 保留 More options 按钮的尺寸、图标、颜色、hover 样式和无障碍名称。
- 保留 Dropdown 的 New chat、Settings 菜单内容与点击行为。
- 不修改路由、状态管理、后端接口或其他页面组件。

## 文件级修改计划

1. 修改 `web/src/views/NavigationView.vue`：
   - 使用现有 `ATooltip` 包装右上角 `ADropdown`；
   - Tooltip 标题设为 `More options`，位置设为 `bottom`。

## 验证方式

```bash
cd web
npm run typecheck
npx eslint src/views/NavigationView.vue
npm run build
cd ..
git diff --check -- web/src/views/NavigationView.vue doc/spec/web/src/views/NavigationView.md
```

浏览器确认右上角三点按钮在悬停和键盘聚焦时显示 Tooltip，点击后 Dropdown
仍向右下方展开，New chat 与 Settings 行为保持不变。
