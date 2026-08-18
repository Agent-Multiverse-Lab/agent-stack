# Login 单页认证设计

## 1. 目标

认证只保留 `/login` 一个页面。登录与邮箱注册在同一张分屏卡片中切换，不再提供独立的
Register 页面。

本轮只设计并实现：

- 邮箱和密码登录；
- 邮箱、密码和确认密码注册；
- 注册成功后原地恢复为 Login 状态；
- 用户随后点击 Login，登录成功后进入 Chat。

不提供用户名、手机号、第三方登录、记住密码、忘记密码或密码找回。

## 2. 页面设计

参考：

- [分屏布局](./assets/layout.png)
- [左侧插画](./assets/auth-illustrate.png)

桌面端使用居中的内联分屏卡片，而不是铺满两块独立页面：

```text
┌────────────────────────────────────────────────────────────┐
│                                                            │
│   ┌──────────────────────────┬──────────────────────────┐   │
│   │                          │  AU                      │   │
│   │                          │                          │   │
│   │         插画             │  Welcome back            │   │
│   │                          │  [Email]                 │   │
│   │                          │  [Password]              │   │
│   │                          │  [Login]                 │   │
│   │                          │  [Create Account]        │   │
│   └──────────────────────────┴──────────────────────────┘   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

具体规则：

- 桌面端卡片使用 `900 × 560` 的横向矩形，圆角 `16px`；
- 卡片按 `7:5` 分栏：左侧插画区约占 `58.3%`，尺寸约为 `525 × 560`；
  右侧表单区约占 `41.7%`，尺寸约为 `375 × 560`；
- 新插画是 `1254 × 1254` 的正方形，左侧使用 `object-fit: cover` 和居中定位，
  只进行少量横向裁切，不按照插画原比例拉伸卡片；
- 卡片宽度随视口等比缩小；小于 `1000px` 时改为上下布局，不继续压窄表单区；
- 卡片右侧使用稍深于页面的浅灰绿表单区，内部表单容器最大宽度为 `280px` 并居中；
- 右侧表单直接属于外层卡片，不再嵌套第二张带边框或阴影的小卡片；
- 卡片只保留一处轻阴影，插画本身就是主要视觉元素，不增加渐变、装饰线或额外插图；
- 小屏改为上下布局，插画在上、表单在下，页面允许纵向滚动。
- 卡片外增加轻量页头：左上角显示现有 Logo 和 `AU`，右上角只显示 GitHub 图标；
- GitHub 图标链接到 `https://github.com/leeejuju/multi-agent-s2c`，在新标签页打开；
- GitHub 图标复用项目现有 `@ant-design/icons-vue` 的 `GithubOutlined`；
- 页头不增加底色、边框或独立组件；桌面端距离页面边缘 `32px`，小屏为 `16px`；
- 表单内部删除重复的 Logo 和 `AU`。

颜色沿用新插画中的森林和萤火光：

| 用途 | 颜色 |
| --- | --- |
| 页面背景 | `#FFFFFF` |
| 卡片表单侧 | `#F2F4F3` |
| 输入框 | `#FFFFFF` |
| 正文 | `#10272B` |
| 次要文字 | `#66777A` |
| 主按钮 | `#15545A` |

字体继续使用项目已有的 `Noto Sans SC Variable` 字体栈，不增加字体依赖。

## 3. 组件边界

```text
AuthenticationView.vue
├── 页面标识
│   ├── 左侧 Logo + AU
│   └── 右侧 GitHub 图标链接
└── 分屏卡片
    ├── 左侧插画
    └── LoginComponent.vue
        └── login / register 两种表单状态
```

- `AuthenticationView.vue` 负责页面布局、插画和认证成功后的路由跳转；
- `LoginComponent.vue` 使用 Ant Design Vue Form，负责表单字段、登录/注册状态、校验、提交状态和错误提示；
- `LoginComponent.vue` 调用 `useAuthStore`，只有登录成功后才向 View 发出
  `authenticated` 事件；
- 不创建 `RegisterView.vue`、`RegisterComponent.vue`、认证 Composable 或表单字段子组件。

右侧表单是一个真实的认证功能组件，不是纯样式包装，因此只拆这一层。

## 4. 表单交互

### 4.1 Login 状态

初始状态只显示：

1. `Email`；
2. `Password`；
3. 主按钮 `Login`；
4. 次按钮 `Create Account`。

点击 `Login` 调用现有登录 Store action。

### 4.2 Register 状态

点击 `Create Account` 时不立即请求接口，而是在同一表单内：

- 保留已经输入的 Email 和 Password；
- 在 Password 输入框正下方展开 `Confirm password` 输入框；
- 标题变为 `Create your account`；
- 主按钮变为 `Create Account`；
- 次按钮变为 `Back to Login`。

字段顺序固定为：

```text
[Email]
[Password]
└─ [Confirm password]  # 点击 Create Account 后原位向下展开
```

Password 与 Confirm password 之间不插入标题、说明、分割线或其他按钮。

注册提交改为：

```text
register
→ POST /api/auth/register
→ 保持当前 /login 页面
→ 收起 Confirm password
→ 恢复 Login 状态
```

点击 `Back to Login` 收起确认密码区域并清空确认密码，不清空 Email 和 Password。

### 4.3 注册成功

注册成功后不刷新页面、不切换路由，也不自动调用登录接口：

- Email 和 Password 保持原值；
- Confirm password 的值和校验状态被清空；
- Confirm password 使用同一个过渡反向收起；
- 标题恢复为 `Welcome back`；
- 主按钮恢复为 `Login`，次按钮恢复为 `Create Account`；
- 使用 `a-alert` 显示 `Account created. Log in to continue.`；
- 动画结束后焦点进入 `Login` 按钮。

用户点击 `Login` 后才调用 `/api/auth/login`。只有登录成功才写入 Token、发出
`authenticated` 事件并进入 Chat。

### 4.4 过渡

确认密码的 `a-form-item` 使用约 `220ms` 的高度、透明度和轻微位移过渡，从 Password
输入框下方原位展开。动画由 Vue `<Transition>` 控制挂载，字段本身仍使用 Ant Design Vue
的 `a-input-password`，不使用 GSAP。

开启 `prefers-reduced-motion` 时取消动画。展开后焦点进入确认密码输入框；手动返回时焦点
回到 `Create Account`，注册成功时焦点进入 `Login`。

## 5. Ant Design Vue 表单

使用项目已经安装的 Ant Design Vue：

| 功能 | 组件 |
| --- | --- |
| 表单与提交 | `a-form` |
| 字段与错误提示 | `a-form-item` |
| Email | `a-input` |
| Password / Confirm password | `a-input-password` |
| Login / Create Account | `a-button` |
| 注册成功提示 | `a-alert` |
| 表单主题 | `a-config-provider` |

`a-form` 的 rules 负责必填、Email 格式、密码最小长度和两次密码一致性校验。`a-button`
直接使用 `html-type="submit"`、`loading` 和 `block`，不自己重写提交态。

`a-config-provider` 只在登录组件范围内设置主色、控件高度和圆角，避免为 Ant Design
内部结构编写一组全局覆盖样式。外层分屏卡片继续使用内联 Tailwind 布局。

主操作按钮使用内联 Tailwind
`shadow-[0_6px_16px_rgba(21,84,90,0.20)]`；次按钮不增加阴影。
Login、Create Account 和 Back to Login 按钮统一为 `240 × 42px`、`14px` 字号，
在表单容器内居中。

页面标识的 Logo 为 `24px`、品牌文字为 `14px`。表单标题为 `30px`，说明文字为
`13px`，输入文字为 `14px`；输入框高度从 `52px` 调整为 `44px`。

Ant Design Vue 没有对外提供专门的“表单字段出现”组件；`a-collapse` 带有面板语义和标题结构，
不适合放在 Password 与 Confirm password 之间。因此只用 Vue `<Transition>` 处理字段的出现，
不直接依赖 Ant Design 的内部 Motion 实现。

## 6. Placeholder 与可访问性

- 输入框只显示 placeholder，不显示额外的可见 Label；
- placeholder 分别为 `Email`、`Password` 和 `Confirm password`；
- 因为 placeholder 会在输入后消失，每个输入仍保留对应 `aria-label`、`name`、`type` 和
  `autocomplete`；
- 错误信息显示在输入区下方，不使用 Toast；
- Enter 提交当前状态的主操作；
- 提交期间禁用输入和按钮，防止重复请求。

## 7. 路由与公开合同

- 保留 `/login`，直接挂载 `AuthenticationView.vue`；
- 删除 `/register` 路由和所有指向它的链接；
- 不增加 `/register` 的兼容重定向；
- Navigation 删除单独的 Sign up 入口，只保留 Log in；
- 后端 `/api/auth/login`、`/api/auth/register` 和认证类型不变；
- `useAuthStore.register()` 改为只调用注册接口，不再内部调用 `login()`；
- `accessToken` 和当前用户仍然只由 `useAuthStore.login()` 写入。

## 8. 文件级修改计划

用户确认后：

1. 修改 `web/src/views/AuthenticationView.vue`，使用 `900 × 560` 卡片和 `7:5`
   分栏，将页面背景改为纯白、卡片表单侧改为浅灰绿，并增加页面标识和 GitHub 链接；
2. 修改 `web/src/components/LoginComponent.vue`，删除重复品牌标识、缩小表单和按钮，
   并给主操作按钮增加轻阴影；
3. 保留现有插画、主题、登录、注册、Store、API 和路由行为，不增加组件或依赖。

不修改后端、不增加依赖，也不新增认证状态层。

## 9. 验证

```bash
cd web
npm run typecheck
npm run lint
npm run build

cd ..
git diff --check -- web doc/spec/web/src/views/login-register
rg -n 'path: "/register"|name: "register"|to="/register"' web/src web/AGENTS.md
```

人工验证：

1. `/login` 桌面端显示 `900 × 560` 横向卡片，左侧插画和右侧表单比例为
   `7:5`；
2. 移动端变为上下布局且可以完整滚动；
3. `Create Account` 平滑展开确认密码，`Back to Login` 正确收起并恢复焦点；
4. Confirm password 始终紧贴在 Password 下方，中间没有其他节点；
5. Ant Design Form 正确显示 Email、密码长度和确认密码错误；
6. 注册成功后 URL 不变、页面不刷新、Confirm password 丝滑收起；
7. 注册成功后只产生注册请求，不自动产生登录请求或写入 Token；
8. Email 和 Password 保留，点击 Login 后才登录并进入 Chat；
9. 页面没有可见 Label、记住密码、忘记密码或独立 Register 入口；
10. 键盘、错误提示、提交禁用和 reduced-motion 行为正常。
11. 新插画在桌面端不被拉伸，主要画面完整；小屏裁切后仍保留中央萤火光区域。
12. 页面底色为纯白，卡片表单侧略深，主操作按钮有轻阴影且次按钮无阴影。
13. 两个按钮均为 `240 × 42px`、`14px` 字号，并在 `280px` 表单容器内居中。
14. 页面左上角显示 Logo + AU，右上角只显示可访问的 GitHub 图标链接。
15. 表单内部不重复显示 Logo 和 AU；标题、说明和输入文字使用紧凑字号，输入框高度为
    `44px`。
