# Knowledge 页面设计

## 页面定位

Knowledge 是独立的知识工作台，不是 Library 的子页面，也不显示在普通 Web 页面右侧。
应用主导航中的 Knowledge 选项进入独立顶级路由：

```text
/knowledge -> KnowledgeView.vue
```

Knowledge 页面内部不再设置 Navigation Section，也不再维护内部导航组件、悬停展开层或
Files / Tools 抽屉入口。应用主导航中的 Knowledge 选项与这里取消的页面内部 Navigation
是两个不同边界，主导航入口和 `/knowledge` 路由继续保留。

## 桌面三栏比例

参考图中的三个主体区域约为 `630px / 1210px / 630px`，比例是：

```text
Files : Chat : Tools = 1 : 1.9206 : 1
```

实现取便于维护且视觉误差可忽略的 `1 : 1.92 : 1`。Chat 始终是页面最大区域，宽度约为
任一侧栏的 `1.92` 倍。截图来自完整的 2K 屏幕，因此不再做 DPI 或 `96 / 120` 换算；截图
像素只用于确认比例，页面宽度始终由当前浏览器的 CSS 容器宽度实时计算。

桌面 Grid 规则：

```css
display: grid;
grid-template-columns:
  minmax(0, 1fr)
  minmax(0, 1.92fr)
  minmax(0, 1fr);
gap: 16px;
width: 100%;
padding: 16px;
box-sizing: border-box;
```

页面只有两个容器间距。设页面内容宽度为 `W`，扣除左右各 `16px` 的页面内边距和两个
`16px` 间距后，可分配给三个容器的宽度为：

```text
P = W - 64px
Files = Tools = P / 3.92
Chat = P × 1.92 / 3.92
```

常见宽度下的计算结果：

| 页面内容宽度 | Files | Knowledge Chat | Tools |
| ---: | ---: | ---: | ---: |
| `1200px` | `289.80px` | `556.41px` | `289.80px` |
| `1400px` | `340.82px` | `654.37px` | `340.82px` |
| `1920px` | `473.47px` | `909.06px` | `473.47px` |
| `2040px` | `504.08px` | `967.84px` | `504.08px` |
| `2552px` | `634.69px` | `1218.61px` | `634.69px` |
| `2560px` | `636.73px` | `1222.53px` | `636.73px` |

这些数值不是固定宽度。打开 DevTools 或改变浏览器宽度时，三个容器继续按相同比例共同
缩放；桌面状态不能自动隐藏 Files 或 Tools，也不能让任一侧栏宽于 Chat。

### 两侧容器收纳

Files 和 Tools 各自在 Header 中提供真实的收纳按钮。收纳是用户主动操作，不是桌面宽度
变化自动触发的响应式行为：

| 状态 | Grid 列宽 |
| --- | --- |
| 全部展开 | `minmax(0, 1fr) minmax(0, 1.92fr) minmax(0, 1fr)` |
| Files 收纳 | `56px minmax(0, 1.92fr) minmax(0, 1fr)` |
| Tools 收纳 | `minmax(0, 1fr) minmax(0, 1.92fr) 56px` |
| 两侧都收纳 | `56px minmax(0, 1fr) 56px` |

- 收纳后的容器保留完整高度、边框、白色背景和 `16px` 圆角，不能完全消失；
- 收纳宽度固定为 `56px`，内部保留 Header 分割线；
- Header 中的收纳按钮固定为 `40px × 40px`，图标固定为 `18px × 18px`；
- 收纳后标题和 Body 隐藏，展开图标仍内嵌在窄容器顶部，点击即可恢复；
- 展开和收纳图标使用完全相同的尺寸、按钮盒和垂直中心，只切换图形，不改变轴线；
- 收纳释放的宽度由剩余区域重新分配，Chat 继续占据最大可用区域。

桌面端的收纳和展开必须具有连续的过渡动效：

- `KnowledgeView.vue` 继续以四种收纳状态对应的 Grid 列宽作为最终布局来源，不为动效建立第二套
  布局状态；
- 切换状态时使用项目已有的 GSAP 读取切换前后的实际像素列宽，并对
  `grid-template-columns` 执行 `240ms`、`power2.inOut` 过渡；动画完成后清除内联列宽，让 CSS
  状态重新接管响应式布局；
- 快速连续点击时覆盖尚未结束的同属性 Tween，从当前可见列宽继续到最新目标，不能排队播放或
  闪回旧状态；组件卸载时终止未完成的 Tween；
- Files 和 Tools 的标题与 Body 不再通过 `display: none` 瞬间消失，而是配合列宽变化执行短暂的
  `opacity` 过渡；隐藏后同时设置不可见和不可交互，不能留下可点击的透明内容；
- 收纳按钮的 `40px` 盒子和 `18px` 图标始终保留在 Header 正常布局中，不能因标题淡出发生水平
  跳跃或上下波动；
- 小于等于 `720px` 的纵向布局不执行横向收纳动效；系统启用
  `prefers-reduced-motion: reduce` 时直接切换最终状态，不播放 Tween 或淡入淡出。

## 页面结构

```text
┌────────── 1fr ──────────┐ 16px ┌──────────── 1.92fr ────────────┐ 16px ┌────────── 1fr ──────────┐
│ Files          [收纳]    │      │ Knowledge Chat                  │      │ Tools          [收纳]    │
│ Header 48px              │      │ Header 48px                     │      │ Header 48px              │
│ ──────────────────────── │      │ ─────────────────────────────── │      │ ──────────────────────── │
│ Upload / Search / List   │      │ Messages                        │      │ Tool grid · upper 1fr    │
│                          │      │ Composer                        │      │ ──────────────────────── │
│                          │      │                                 │      │ Empty · lower 1fr        │
└──────────────────────────┘      └─────────────────────────────────┘      └──────────────────────────┘
```

三个区域共享顶部基线和相同外观层级，但各自保留独立的内容滚动边界。

## Files：上传与解析

左侧容器是知识文件入口：

- Header 显示 `Files` 和右侧收纳按钮；
- `KnowledgeFilesComponent` 直接负责选择文件、校验扩展名并发出
  `files-selected`，不为这个单一入口保留独立添加组件；
- 文件搜索保留在 `KnowledgeFilesComponent`，输入框具有正常的文本光标；
- `KnowledgeFileListComponent` 负责列表滚动、空状态和当前选中项；
- `KnowledgeFileListItemComponent` 只显示文件图标、名称、选中状态和操作菜单；
- `KnowledgeFileActionsMenuComponent` 负责文件行的三点菜单和确认交互；
- 文件列表是主内容，上传和搜索区域不能挤压列表的可滚动空间。

### 文件添加入口

- 删除 `KnowledgeFileAddComponent.vue`，把现有 `UploadDragger`、扩展名校验、
  `beforeUpload` 和样式直接并入 `KnowledgeFilesComponent.vue`；
- 添加入口的 `.ant-upload-drag` 高度和最小高度都固定为 `48px`；
- 包裹添加内容的 `.ant-upload-drag` 圆角固定为 `96px`，形成完整的胶囊形边界；
- Files Body 继续提供 `0.9rem` 外层 Padding；本轮不为上传胶囊内部新增上下 Padding；
- 自定义 Upload Slot 不依赖可能缺失的 `.ant-upload-drag-container`；直接把
  `.ant-upload-btn` 设置为 `display: flex`、`align-items: center` 和
  `justify-content: center`，让整组内容相对上传胶囊水平、垂直居中；
- 文件图标和 `Add Sources` 文案继续由 `.knowledge-file-add-content` 的 Flex
  `align-items: center` 彼此对齐；内容组不再贴左侧，图标与文案作为一个整体位于胶囊中心；
- Add Sources 图标只使用 Lucide `Plus` 单加号，不使用带文件外框的 `FilePlus2`，也不使用
  文本字符或手写 SVG 模拟加号；
- 保留多选、格式校验、禁用组件自动上传和 `files-selected` 事件合同，不改变上传行为；
- 不新增替代组件、Composable 或辅助模块。

### 文件搜索容器

`Search files` 不是单行 `InputSearch`，而是一个具有共同边框和背景的上下两层容器：

```text
┌──────────────────────────────────┐
│ Search files                     │  输入区域
│                                  │
│ [Globe]                [Search]  │  功能区
└──────────────────────────────────┘
```

- 上半部分是正常的文本输入区域，使用 Ant Design Vue `Input`，保留文本光标和
  `Search files` 占位文字；输入框显式使用 `type="text"` 与 `inputmode="text"`，字母、数字、
  空格和符号都必须能够正常输入；输入框内部不提供 Clear 按钮，输入后右侧不能出现叉号；
- 下半部分是功能区，使用水平布局并与输入区域共同位于搜索容器内部；
- 功能区左侧暂时只放置一个 Lucide `Globe` 图标，用作未来 Web Search 的位置标记；
  本轮不显示 `Web` 文案，不建立按钮、模式开关、Hover 或 Active 状态；
- Globe 图标是无交互的静态元素，使用弱化文字色并设置 `aria-hidden="true"`，不能伪装成
  当前可用的 Web Search 功能，也不能悬挂在搜索容器外侧；
- 功能区右侧提供独立的放大镜形 Search 按钮，使用 Lucide `Search` 图标、圆形按钮语义和
  `aria-label="Search"`；按钮始终位于功能区右端，不能通过 `addonAfter` 拼接到输入框外侧；
- Search 按钮始终保持可点击，不能因查询为空而进入 Disabled 状态；点击 Search 按钮与在
  输入区按 Enter 触发同一提交动作，空白查询由提交函数直接忽略；
- 搜索容器继续使用 `var(--radius-knowledge-container)`，获得焦点时由整个容器通过
  `:focus-within` 显示统一边界状态，内部 Input 和按钮不能各自形成互相冲突的外框；
- 组件保持单一结构，全部放在 `KnowledgeFilesComponent.vue` 内，不新增搜索子组件。

### 搜索行为边界

- 提交查询只按文件名过滤当前文件列表；输入值和已提交查询分离，只有点击 Search 或按
  Enter 才更新列表结果；
- 不建立字符白名单或数字过滤；例如 `123`、`report 2026` 和带符号的文件名片段都必须能够
  留在输入框中并参与文件名匹配；
- 左侧 Globe 图标不接收点击、不发出事件，也不调用 API；真实 Web Search 不属于本轮范围；
- 本轮不修改后端接口、`KnowledgeFileItem` 数据结构或父组件事件合同；将来增加真实 Web
  Search 时必须先补充结果展示和 Source 加入合同，再把静态图标升级为可交互控件。

### 本轮文件级改动与验证

- 修改 `web/src/components/knowledge/KnowledgeFilesComponent.vue`：内联文件添加逻辑，使用
  上层 Input 和下层功能区重建搜索容器，加入静态 Globe 图标和可点击 Search 按钮；
- 上传入口的后续对齐修正仍只修改 `KnowledgeFilesComponent.vue` 中已有的
  `.ant-upload-btn` 样式：覆盖 Ant 的 `display: table`，改为 Flex 水平、垂直居中，不修改
  Padding、图标尺寸或上传行为；
- 删除 `web/src/components/knowledge/KnowledgeFileAddComponent.vue`，不建立替代组件；
- 不修改 `KnowledgeView.vue`、共享类型、后端路由或服务；现有 `files-selected`、`select`、
  `remove`、`close` 和 `toggle-collapse` 事件保持不变；
- Globe 和 Search 图标均为 `18px`；Globe 使用 `32px × 32px` 的静态对齐盒，Search 使用
  `32px × 32px` 的圆形按钮，保证底部功能区处于同一水平轴；
- 清空输入框时立即恢复完整文件列表；非空查询只有点击 Search 或按 Enter 后才应用；
- 删除 `allow-clear`、`#clearIcon`、`canSubmitSearch`、Search Button 的 `disabled` 绑定和仅为
  Disabled 状态服务的样式；按钮保持启用，但空白提交仍不修改过滤结果；
- 实现后运行 `npm run typecheck`、`npm run lint`、`npm run build` 和 `git diff --check`，并检查
  文件选择、格式拦截、数字输入、鼠标提交、Enter 提交、清空恢复、键盘焦点和小屏布局。

## Chat：根据知识库对话

中间容器是主工作区：

- 使用 `1.92fr`，在三栏桌面布局中始终最宽；
- Header 只显示 `Knowledge Chat`；
- 消息区域独立滚动；
- `KnowledgeComposerComponent` 固定在容器底部，真实 `textarea` 保留正常文本光标；
- 没有文件时显示上传引导；存在文件但尚未索引时显示未索引提示；
- 未来的引用信息显示文件名和定位信息，不与普通消息内容混成同一种视觉元素。

## Tools：内容生成工具

右侧容器承载知识内容生成入口：

- Header 显示 `Tools` 和右侧收纳按钮；
- 首批工具为 `Road Map`、`PPT` 和 `Slides`；
- `KnowledgeFileActionsComponent` 只负责 Header、收纳状态、工具数据、三列 Grid、上下分区和点击后的
  上层反馈；每个工具卡由独立的 `KnowledgeToolComponent` 渲染；
- Tools Body 在 Header 下方固定分为上下两个 `1fr` 等高区域，中间使用横贯 Body 的
  `1px solid var(--color-border-subtle)` 分割线；两个区域都使用 `min-height: 0`，不能因内容撑破
  右侧容器；
- 上区承载当前工具列表，固定使用三列 `repeat(3, minmax(0, 1fr))`，Road Map、PPT 和 Slides
  在同一行；不根据容器宽度自动切换列数；
- 下区本轮保持完全空白，只保留等高结构、白色背景和与上区之间的分割线；不增加标题、空状态、
  图标、说明文字或伪造的可用功能；
- `.knowledge-tool` 使用 `border-box`，总高固定为 `74px`，Padding 固定为
  `8px 8px 8px 12px`，即上下和右侧为 `8px`、左侧为 `12px`；Padding 位于
  `.knowledge-tool-details` 外部，Details 自身不设置 Padding；
- 扣除上下 Padding 和边框后，Details 所在内容区的可用高度为 `56px`；内部使用 `18px` 工具图标、
  `2px` 图标文字间距和 `16px` 文字行高，继续保持图标在上、Tool 名称在下；
- 工具卡宽度由上区三列 Grid 等分；上下区各自使用 `16px` 内边距，上区行列间距为 `8px`；
- 工具卡内部明确分成左右两部分：左侧 Details 是纵向信息区，上方是 `18px` 工具图标，下方
  是 Tool 名称；右侧只有一个 `16px` Lucide `ChevronRight`，表示进入该工具；
- 左侧信息区使用 `flex-direction: column`、`align-items: flex-start`，整张卡使用两列内部
  布局将信息区与 Chevron 分开，不能把图标、名称和 Chevron 排成同一条文字基线；
- 每张卡只显示工具图标、工具名称和 Chevron，不增加说明性小字；
- 卡片不使用阴影或悬浮位移，Hover 和键盘 Focus 只加强背景、边框或焦点环；
- `KnowledgeToolComponent` 使用按钮语义并只发出 `activate` 事件，不直接调用消息、路由或生成
  服务；`KnowledgeFileActionsComponent` 接收该事件并保持现有“尚未连接”反馈边界。

工具卡在白色容器内使用低饱和淡色：

| 工具 | 默认背景 | Hover / Focus 背景 |
| --- | --- | --- |
| Road Map | 淡蓝紫 `#EDEFFA` | `#E4E7F7` |
| PPT | 淡米灰 `#F2F2E8` | `#E9E9DA` |
| Slides | 淡薄荷绿 `#E1F1E5` | `#D6EADA` |

颜色必须定义为 `web/src/styles/tokens.css` 中的语义 Token，组件只引用 Token。

### 本轮 Tools 拆分与图标修订

- 新增 `web/src/components/knowledge/KnowledgeToolComponent.vue`，集中承载单张工具卡的
  左侧上下结构、右侧 Chevron、颜色状态和键盘交互；
- 外层 `.knowledge-tool` 总高为 `74px`，使用 `padding: 8px 8px 8px 12px`，Grid 行高同步为
  `74px`；扣除上下 Padding 和边框后的内容区高度为 `56px`；`.knowledge-tool-details` 使用
  `padding: 0`。Padding 只负责 Details 外侧留白，不能
  写到 Details 自身；内部使用 `18px` 工具图标、`2px` 图标文字间距、`16px` 文字行高和
  `16px` Chevron；
- 修改 `KnowledgeFileActionsComponent.vue`，保留工具配置数组并渲染
  `KnowledgeToolComponent`，删除父组件中的单卡模板和单卡样式，Grid 固定为三列；
- 修复当前 `PPT` 配置中的空白 Label，使三张卡分别显示 `Road Map`、`PPT` 和 `Slides`；
- 继续复用已有三个工具颜色 Token，不新增颜色、全局样式或工具业务合同；
- 修改 `KnowledgeFilesComponent.vue`，让 Add Sources 内容组居中并使用 Lucide `Plus`；搜索
  输入不启用 Clear 控件，因此不渲染任何输入后叉号；
- Knowledge 页面内由业务组件呈现的图标以及 Ant Design Vue 可覆盖的可见图标 Slot 均使用
  `@lucide/vue`；文件格式警告、工具未接通提示和删除确认中的状态图标也改用 Lucide；
- 修改 `KnowledgeFileActionsMenuComponent.vue` 的删除确认图标；其余 Knowledge 组件已使用
  Lucide，只做审计，不做无关重写；
- 实现后运行 `npm run typecheck`、`npm run lint`、`npm run build` 和 `git diff --check`，并在
  桌面与小屏检查 Add Sources 双轴居中、Tool 固定三列、上下区域等高、分割线、键盘焦点和
  图标来源。

### 本轮 Tools 分区与收纳动效

- 修改 `KnowledgeFileActionsComponent.vue`：把 Body 重构为上下两个等高区域，上区渲染三列
  Tool Grid，下区保留空白；新增的水平分割线属于上下区域边界，不替代现有 Header 分割线；
- 修改 `KnowledgeView.vue`：把 Files 和 Tools 的直接布尔取反改为统一的收纳切换函数，通过页面
  根节点 Ref 读取切换前后 Grid 的实际像素列宽，并使用 GSAP 完成过渡；不改变子组件 Props、事件
  名称或收纳状态所有权；
- 修改 `KnowledgeFilesComponent.vue` 和 `KnowledgeFileActionsComponent.vue`：将收纳状态下标题和
  Body 的 `display: none` 改为可过渡的 `opacity`、`visibility` 和 `pointer-events` 状态，并保持
  收纳按钮轴线稳定；
- 动效只使用直接元素 Ref 和组件内状态，不建立通用动画 Composable，不引入 GSAP Plugin；卸载时
  清理 Tween，动画完成后清除内联 `grid-template-columns`；
- 实现后除静态检查和生产构建外，必须在浏览器中测量上下区高度比例、三列 Tool 排列，以及 Files、
  Tools 单独/同时收纳、快速反向点击、小屏和减少动态效果状态。

## 圆角与图标内嵌

Knowledge 页面所有可见的矩形容器统一使用
`var(--radius-knowledge-container)`，其值固定为 `16px`：

- Files、Knowledge Chat、Tools 三个主容器；
- 文件上传区、文件搜索框、文件行和文件类型图标底座；
- Chat 与 Files 的空状态图标底座；
- Tools 工具卡；
- Composer 输入容器。

圆形发送按钮、文件三点按钮和两侧收纳按钮继续保持圆形，因为圆形本身是这些操作控件的
明确语义，不强制改成矩形。

图标采用内嵌式结构：

- Knowledge 页面统一从 `@lucide/vue` 引入图标；不能使用文本字符模拟图标、手写 SVG 或
  `@ant-design/icons-vue`；Ant Design Vue 只负责控件行为，存在可覆盖的可见图标 Slot 时也
  必须传入 Lucide 图标；
- 图标必须是所属卡片、按钮、输入框、文件行或空状态容器的内部子元素；
- 不允许在容器外侧建立独立图标列，也不允许使用负 margin 或绝对定位把图标悬挂在边框外；
- 图标和文字共同参与所属容器的正常布局，容器自身承担 Hover、Focus、选中和点击状态；
- 工具图标放在淡色工具按钮内部，上传图标放在上传容器内部，文件图标放在文件行内部；
- 搜索图标放在文件搜索容器下层功能区右侧的 Search 按钮内部，不能使用外接 Search
  addon，也不能悬挂在容器外侧；
- 工具卡右侧方向指示使用 Lucide `ChevronRight`，不能直接渲染 `>` 文本；
- 收纳图标放在 `56px` 窄容器顶部的 `40px` 按钮内部，不能漂浮在窄容器旁边。

## 字号层级

- `KnowledgeView.vue` 根容器的基础字号固定为 `14px`，只影响 `/knowledge` 页面，不修改
  全局 `body` 的 `15px`，也不新增全局 Typography Token；
- 文件名、Add Sources、搜索输入、列表空状态、Chat 空状态、Composer 输入和 Tools 按钮文案
  统一继承 Knowledge 页面的 `14px`，删除组件中现有的 `0.8125rem`、`0.85rem`、`0.86rem`、
  `0.88rem`、`0.9rem` 和 `0.96rem` 混合字号；
- Files、Knowledge Chat 和 Tools 三个 Header 标题继续使用 `16px`，保留标题与正文的必要层级；
- 桌面与普通响应式状态的正文均为 `14px`；小屏文本输入继续使用 `16px`，避免移动浏览器因
  输入字号小于 `16px` 自动缩放页面；
- 按钮尺寸、图标尺寸、Line Height、间距和容器高度不随字号调整，本轮只统一文字大小。

本轮字号改动文件范围：

- `web/src/views/KnowledgeView.vue`：声明 Knowledge 页面基础字号 `14px`；
- `web/src/components/knowledge/KnowledgeFilesComponent.vue`：让 Add Sources 和桌面搜索输入
  继承基础字号，保留 Header `16px` 与小屏输入 `16px`；
- `KnowledgeFileListComponent.vue`、`KnowledgeFileListItemComponent.vue`、
  `KnowledgeChatComponent.vue`、`KnowledgeComposerComponent.vue` 和
  `KnowledgeFileActionsComponent.vue`：移除正文与控件文案的零散 rem 字号并继承 `14px`，
  各区域 Header 仍为 `16px`；
- 不修改共享样式、其他页面、后端接口、组件 Props 或事件合同；实现后运行
  `npm run typecheck`、`npm run lint`、`npm run build` 和 `git diff --check`，并用浏览器确认
  Knowledge 正文计算字号为 `14px`、Header 为 `16px`。

## Header 与分割线

Files、Knowledge Chat 和 Tools 使用完全一致的 Header 规则：

- Header 的 `height`、`min-height` 和 `max-height` 都是 `48px`；
- Header 使用 `box-sizing: border-box`，分割线包含在这 `48px` 内；
- 标题垂直居中，不通过额外 margin 改变 Header 高度；
- Header 底部使用横贯容器宽度的 `1px solid var(--color-border-subtle)`；
- 三个 Header 的顶部和分割线必须分别处于同一水平线；
- Header 标题是静态文本，使用 `user-select: none` 和 `caret-color: transparent`；
- Knowledge 页面的非输入内容默认隐藏文本 Caret；文件搜索框、Composer `textarea` 和未来的
  `[contenteditable="true"]` 显式恢复 `user-select: text` 与 `caret-color: auto`；
- 键盘 `:focus-visible` 外框继续保留，不能通过移除可聚焦语义解决闪动 Caret；
- Body 从 Header 分割线下方开始，使用 `min-height: 0` 并独立滚动。
- Files 和 Tools 展开时，收纳按钮位于各自 Header 内部；收纳后仍保持同一个 Header 高度和
  图标中心轴。

## 组件和职责

```text
web/src/views/KnowledgeView.vue
  └── web/src/components/knowledge/
        ├── KnowledgeFilesComponent.vue                # 1fr
        │     └── KnowledgeFileListComponent.vue
        │           └── KnowledgeFileListItemComponent.vue
        │                 └── KnowledgeFileActionsMenuComponent.vue
        ├── KnowledgeChatComponent.vue                 # 1.92fr，页面最大区域
        │     └── KnowledgeComposerComponent.vue
        └── KnowledgeFileActionsComponent.vue          # 1fr，Tools 编排
              └── KnowledgeToolComponent.vue           # 单个 Tool 卡片
```

- `KnowledgeView.vue` 持有本地文件集合、`selectedFileId`、两侧收纳状态和三栏页面编排；
- `KnowledgeFilesComponent.vue` 直接负责文件选择、搜索和列表组合；
- `KnowledgeChatComponent.vue` 负责对话容器和空状态；
- `KnowledgeFileActionsComponent.vue` 负责右侧工具列表编排，`KnowledgeToolComponent.vue`
  负责单张工具卡的显示与激活事件；
- `web/src/types/knowledge.ts` 定义页面组件共享的 TypeScript 合同；
- 不建立通用 `Panel`、`Container` 或 `Layout` 抽象，也不为一次性页面状态创建 Composable。

### 源码目录边界

- 仅由 Knowledge 页面使用的 8 个 `Knowledge*.vue` 组件统一放在
  `web/src/components/knowledge/`；
- `KnowledgeView.vue` 继续留在 `web/src/views/`，只把三个页面入口组件的 import
  更新为 `@/components/knowledge/...`；
- Knowledge 组件之间继续使用同目录相对 import，不增加 `index.ts` 聚合导出；
- 组件 scoped CSS 的全局样式引用随目录层级更新为
  `@reference "../../styles/index.css"`，不修改任何样式规则；
- `ConversationComponent.vue`、`MessageInputComponent.vue` 等通用组件继续留在
  `web/src/components/` 根目录，不因名称或页面邻近关系一起移动；
- 本次目录重组只改变文件路径和 import，不改变组件名称、Props、事件、页面行为或样式；
- 已删除的 `KnowledgeNavigationComponent.vue` 不移动、不恢复。

`KnowledgeNavigationComponent.vue` 已取消。不能再从 `KnowledgeView.vue` 引入它，也不能以另一
个名称重新建立同职责的页面内部导航栏。

## Ant Design Vue 使用边界

Ant Design Vue 只提供成熟控件行为，不负责主布局：

- 文件添加由 `KnowledgeFilesComponent.vue` 直接使用 `Upload` / `Upload.Dragger`；
- 文件搜索使用搜索容器内部的无独立边框 `Input`、静态 Globe 图标和 Search 提交按钮，
  不使用 `InputSearch`；
- 操作按钮、Tooltip、Dropdown 和确认交互使用对应的 Ant Design Vue 控件；
- Ant Design Vue 不提供 Knowledge 页面的视觉图标；Input Clear、消息状态和确认状态等可见
  图标通过组件 Prop 或 Slot 显式替换为 Lucide；
- 文件列表和空状态使用 `List`、`Empty`；
- 页面根部和三个圆角容器使用原生 CSS Grid，不用 `Layout` 或 `Card` 替代；
- Knowledge 页面始终把 Files 和 Tools 作为普通 Panel 使用，不再由页面内部 Navigation
  触发 Drawer；
- 组件颜色和交互状态通过现有语义 Token 统一管理。

## 响应式规则

- 页面宽度大于 `720px` 时保留 Files / Chat / Tools 三栏，比例为 `1 : 1.92 : 1`；
- 桌面 DevTools 导致的普通视口缩窄只会让三栏按比例收缩，不自动收纳两侧容器；
- 桌面端允许用户分别收纳 Files 和 Tools，收纳后各自保留 `56px` 图标容器；
- 页面宽度小于等于 `720px` 时不增加移动端 Navigation，也不使用页面级抽屉；
- 小屏按 `Chat → Files → Tools` 纵向排列，页面负责纵向滚动；
- 小屏强制完整显示 Files 和 Tools，隐藏横向收纳按钮；桌面收纳状态可以保留，返回桌面后恢复；
- 每个小屏区域高度为 `calc(100dvh - 32px)`，继续保留 `16px` 页面内边距、`16px` 间距、
  圆角和边框；
- Tools 在桌面和小屏都保持三列，每行最多三个 Tool；上下区域在两种布局下都保持 `1:1` 等高；
- 所有按钮和文件行都需要清晰的键盘焦点状态。

## 视觉方向

页面采用安静的知识工作台语言：浅灰工作区、白色容器、细边界、稳定圆角和克制的淡色工具
卡。页面重点来自 Chat 的最大宽度与清晰的三栏层级，不再依靠额外 Navigation、装饰性渐变、
统计卡片或无功能说明制造视觉重心。
