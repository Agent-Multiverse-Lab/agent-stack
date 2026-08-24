# Implementation Plan: AM Product Branding

计划版本：`v0.1.0`

## 1. Implementation Steps

1. 重绘 `web/src/assets/logo.svg`：用透明方形 `viewBox` 和少量整数坐标 path/rect
   表达母版中的像素 `M`，保留深海军蓝、青色、洋红和黄色，不保留灰底与光晕。
2. 修改 `web/src/views/NavigationView.vue` 和
   `web/src/views/AuthenticationView.vue`，将可见 `AU` 与对应 aria label 改为
   `AM`，继续复用同一个 Logo asset。
3. 修改 `web/src/views/ChatView.vue`、`web/src/components/LoginComponent.vue`、
   `web/src/components/SettingsComponent.vue`，统一空会话、登录和设置中的产品名。
4. 修改 `web/index.html` 的 favicon metadata、title 和 description；修改
   `web/package.json`、`web/package-lock.json` 与 `web/README.md` 的前端包/产品名称。
5. 更新 `web/AGENTS.md` 的当前产品身份和 Logo 所有权；使用 `rg` 确认活跃 Web
   不再残留用户可见 `AU` 或 `Multi-Agent S2C`。
6. 运行定向 ESLint、Vite build 和 diff check；不启动前端、API 或 Worker。

## 2. Ownership

- `web/src/assets/logo.svg`：唯一前端 Logo 源文件。
- View/Component：各自拥有所在界面的品牌文案和 aria label。
- `web/index.html`：浏览器 favicon、title 和 description。
- `web/package*.json`：前端 package metadata，不承载展示逻辑。
- `au.access_token`：既有认证会话数据标识，本次保持稳定。

## 3. Core Examples

### 3.1 Pixel M asset

目标：`web/src/assets/logo.svg`

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" role="img" aria-label="AM logo">
  <path fill="#10244a" d="..." />
  <path fill="#00d9e8" d="..." />
  <path fill="#ff087f" d="..." />
  <rect fill="#ffd900" ... />
</svg>
```

坐标使用整数像素，不增加 SVG filter、渐变或外部资源。小尺寸仍由完整 `M`
轮廓承担识别，彩色块只做品牌签名。

### 3.2 Navigation brand

目标：`web/src/views/NavigationView.vue`

```vue
<RouterLink :to="{ name: 'chat' }" aria-label="AM home">
  <img :src="logoUrl" alt="">
  <span>AM</span>
</RouterLink>
```

### 3.3 Browser metadata

目标：`web/index.html`

```html
<meta
  name="description"
  content="AM — Agent Multiverse. A universe for agents."
>
<title>AM</title>
```

### 3.4 Empty chat copy

目标：`web/src/views/ChatView.vue`

```vue
<h1>Welcome to AM</h1>
<p>What would you like to explore or build today?</p>
```

## 4. Failure Handling

- SVG 必须是浏览器原生可解析的独立资源；构建失败时不引入组件包装或位图 fallback。
- GitHub 链接保持当前真实仓库地址；品牌名更新不推断仓库已重命名。
- 全量检查若被本次范围外的既有错误阻断，继续运行改动文件的定向检查和直接
  Vite build，并在交付时明确区分。

## 5. Validation

```bash
cd web
npx eslint \
  src/views/NavigationView.vue \
  src/views/AuthenticationView.vue \
  src/views/ChatView.vue \
  src/components/LoginComponent.vue \
  src/components/SettingsComponent.vue
npx vite build
cd ..
rg -n "AU|Multi-Agent S2C" web/src web/index.html web/README.md
git diff --check -- web docs/spec/product/branding
```

视觉核对 favicon、展开侧栏、窄屏侧栏、登录页和空 Chat；不启动后端进程。
