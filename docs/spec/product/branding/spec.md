# Specification: AM Product Branding

## 1. Purpose

将 Web 产品的用户可见身份统一为 `AM`。`AM` 的全称为
`Agent Multiverse`，品牌句为 `A universe for agents.`；首个产品版本继续使用
常规的 `v1` 版本标记，不把数字写入永久品牌名。

本能力只定义产品品牌和前端展示，不重命名仓库、后端服务、数据库对象或公开 API。

## 2. Visual Direction

品牌标识以用户提供的霓虹像素图为母版，提取中央块状 `M` 并重绘为透明 SVG：

- 主体使用深海军蓝，保留青色、洋红和信号黄像素作为唯一高彩度品牌元素；
- 保持硬边像素结构，不把母版的灰色背景和大面积光晕写入 Logo；
- Logo 必须在 favicon、18px 侧栏标识和登录页 24px 标识中保持清晰；
- 产品页面继续使用现有 paper/graphite/slate 中性色，霓虹色只出现在 Logo，
  不扩展为新的全局 UI 主题。

## 3. Requirements

### AM-BRAND-001 Product identity

活跃 Web 界面的产品名统一为 `AM`。需要解释品牌时使用
`Agent Multiverse`；品牌句固定为 `A universe for agents.`。界面不得继续显示
`AU` 或 `Multi-Agent S2C` 作为产品名称。

### AM-BRAND-002 Single logo asset

`web/src/assets/logo.svg` 是前端唯一 Logo 源文件。它使用透明方形画布和矢量像素
结构，不增加平行的旧 Logo、位图副本、运行时滤镜组件或第二套图标依赖。

### AM-BRAND-003 Brand surfaces

以下活跃入口使用同一 `logo.svg` 和 `AM` 文案：

- 浏览器 favicon、document title 和 description；
- `NavigationView.vue` 的展开侧栏品牌入口；
- `AuthenticationView.vue` 的页头、可访问名称和认证区域；
- `ChatView.vue` 的空会话欢迎语；
- `LoginComponent.vue` 和 `SettingsComponent.vue` 的产品文案；
- `web/README.md` 与 npm package metadata。

### AM-BRAND-004 Stable technical identifiers

品牌更新不重命名 Git 仓库、GitHub URL、后端服务、API、数据库字段或现有
`au.access_token` 浏览器存储键。该键是已发布会话数据标识，不是用户可见品牌；
保持它可避免无业务原因的强制登出。

### AM-BRAND-005 Accessibility and responsive use

包含 Logo 的链接必须提供 `AM home` 等可访问名称；纯装饰 `<img>` 保持空 `alt`。
Logo 在桌面展开侧栏、窄屏侧栏、登录页和 favicon 中不得变形或依赖动画；
颜色不是识别 `M` 轮廓的唯一手段。

## 4. Non-goals

- 不修改 API、Worker、Agent、认证协议或 Run 事件链路。
- 不重命名 `multi-agent-s2c` 仓库或现有 GitHub 地址。
- 不把母版整张竖版图片作为页面背景，也不新增启动页或品牌动画。
- 不为深色模式、营销站点、社交媒体或印刷物创建额外 Logo 变体。
- 不重新设计当前页面布局、字体系统或全局色板。

## 5. Acceptance Criteria

- 活跃 Web 源码不再显示 `AU` 或 `Welcome to Multi-Agent S2C`。
- `logo.svg` 呈现透明、清晰的彩色像素 `M`，并被 favicon、导航和登录页复用。
- 浏览器标题为 `AM`，description 包含 `Agent Multiverse` 和品牌句。
- 空会话欢迎语显示 `Welcome to AM`，辅助文案仍说明用户下一步可以做什么。
- npm 前端包名为 `am-web`，锁文件根 package metadata 同步。
- `au.access_token`、仓库名和 GitHub URL 保持不变。
- 定向 ESLint、Vite build 和 `git diff --check -- web docs/spec/product/branding`
  通过；仓库级既有错误单独报告。
