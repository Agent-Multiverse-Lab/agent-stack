# Library 页面前端设计与实现规格 (Revision 13)

## 目标行为与组件化 Dropdown 重构

根据用户指令，彻底替换第二行 Filter 工具栏中的原生 HTML `<select>` 标签，改用组件库 (`ant-design-vue`) 的 `ADropdown` / `AMenu` 组件重构类型 (Type) 与来源 (Source) 筛选框。

### 1. 彻底摒弃原生 `<select>` 标签
- 原生 `<select>` 的操作系统渲染样式与现代设计风格严重割裂。
- 全面改用 `ant-design-vue` 的 `ADropdown` + `AMenu` + `AMenuItem` 结合自定义按钮触发器。

### 2. 第二行工具栏重构美化 (Polished Component-Based Filter Toolbar)
- **统一几何高度与图标比例**：
  - 控件高度：全员统一 `h-8` (32px)。
  - Icon Metrics：所有图标（Tabs 图标、Filter 图标、ChevronDown 图标、View Switcher 图标）统一为 **14px (`:size="14"`)** 和 **1.75 线条粗细 (`:stroke-width="1.75"`)**。
- **自定义组装 Dropdown 按钮**：
  - Type Filter Dropdown：`<ADropdown>` 配合 `<button class="inline-flex h-8 items-center gap-1.5 rounded-[10px] bg-mist/70 hover:bg-mist px-2.5 text-xs text-[#0F172A]">`，内置 ChevronDown 图标。
  - Source Filter Dropdown：`<ADropdown>` 配合同风格按钮，内置 ChevronDown 图标。
- **Category Tabs & View Switcher**：
  - 保持统一分段控制 (`bg-mist/80 rounded-[12px] p-0.5`)，Active 项获得 `bg-paper text-[#0F172A] shadow-2xs font-medium`。

---

## 字符布局设计图 (ASCII Layout Diagram - Revision 13)

```text
+-----------------------------------------------------------------------------------+
|  [Header 顶栏]                             [··· 三点菜单 (NavigationView)]       |
+-----------------------------------------------------------------------------------+
|  [左侧窄条留白]                     [中间区域: max-w 920px]         [右侧窄条留白] |
|                                                                                   |
|  (1) 头部栏:                                                                      |
|  [📚 18px] Library                       [ 🔍 Search... (16px) ]  [+ New ˅]        |
|                                                                                   |
|  (2) 第二行重构工具栏 (使用 ant-design-vue ADropdown 组件, 所有 Icon 统一 14px):  |
|  [ [≡ All] [🖼️ Images] [📄 Documents] ]   [⚙ Type: All ˅]  [Source: All ˅]  [ [≡] [::] ]
|  ^ 分段 Tab (32px h)                    ^ antd ADropdown 组件按钮         ^ Switcher
|                                                                                   |
|  (3) 列表展示 (表头 12px #94A3B8, 主文本 14px #0F172A, SIZE 左对齐, Hover 显示 3点)： |
|                                                                                   |
|  NAME                     MODIFIED            SIZE                ACTIONS         |
|                                                                                   |
|  [Hover] 🖼️ Banner.png    2026-08-11 11:20    3.4 MB               [···] LibraryActionComponent
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 文件修改计划

1. `web/src/components/library/LibraryFilterComponent.vue`
   - 彻底移除 `<select>` 与 `<option>` 标签。
   - 使用 `ant-design-vue` 的 `ADropdown`、`AMenu`、`AMenuItem` 搭配自定义 trigger 按钮重构类型与来源筛选框。
   - 所有图标统一 `:size="14"` 和 `:stroke-width="1.75"`。

---

## 验证方式

1. 运行 `npm run typecheck` 确认 TypeScript 类型无误。
2. 运行 `npm run build` 确认打包通过。
3. 检查页面：第二行没有原生 `<select>` 标签，下拉筛选使用优雅的 antd 组件 Dropdown 弹窗；所有图标尺寸高度与样式几何统一。
