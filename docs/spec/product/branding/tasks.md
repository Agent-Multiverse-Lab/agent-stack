# Tasks: AM Product Branding

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| AM-B01 | AM-BRAND-002/005 | `web/src/assets/logo.svg` | 将现有 AU 标识替换为透明彩色像素 M |
| AM-B02 | AM-BRAND-001/003/005 | `web/src/views/NavigationView.vue`, `web/src/views/AuthenticationView.vue` | 替换主导航与认证页品牌名和可访问名称 |
| AM-B03 | AM-BRAND-001/003 | `web/src/views/ChatView.vue`, `web/src/components/LoginComponent.vue`, `web/src/components/SettingsComponent.vue` | 替换活跃界面产品文案 |
| AM-B04 | AM-BRAND-001/003/004 | `web/index.html`, `web/package.json`, `web/package-lock.json`, `web/README.md` | 同步浏览器与前端包 metadata，保留稳定技术标识 |
| AM-B05 | AM-BRAND-002/004 | `web/AGENTS.md` | 记录 AM 产品身份、Logo 归属和不变的仓库/会话标识 |
| AM-B06 | AM-BRAND-001/002/003/005 | `web/` | 搜索残留、定向 lint、构建、diff 与品牌入口视觉核对 |

## Done Conditions

- 活跃 Web 品牌入口统一显示 `AM`。
- `logo.svg` 是透明方形彩色像素 M，favicon、导航和登录页共同复用。
- `Agent Multiverse` 和 `A universe for agents.` 只出现在需要解释品牌的 metadata/
  文档位置，不挤占日常导航。
- 前端包名为 `am-web`；`au.access_token`、仓库名和 GitHub URL 不变。
- 未增加 Logo 组件、主题层、动画、位图副本或第三方依赖。
- 计划中的验证命令已运行，结果如实记录。
