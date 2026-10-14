# Settings 全局模型供应商管理任务

- [ ] S01（MODEL-SETTINGS-005～006）：接入 Auth Domain 管理员授权；仅管理员显示 Models 管理入口，普通用户调用任一 Provider 管理接口均返回 403。
- [ ] S02（MODEL-SETTINGS-002）：让供应商选项完全来自全局 `listModelProviders()`，移除组件内 DeepSeek/Qwen 数组和默认选中常量。
- [ ] S03（MODEL-SETTINGS-002）：放宽 provider ID 类型，实现已知 SVG 资源映射和未知供应商的中性图标 fallback。
- [ ] S04（MODEL-SETTINGS-005～006）：在 `SettingsModels` 本地状态中实现动态首选、空状态、当前项消失时回退，以及身份/权限与 provider 双重迟到响应校验。
- [ ] S05（MODEL-SETTINGS-003～006）：保留现有启用、密钥、Base URL、模型发现、连接检测和保存交互，保存后同步当前详情与摘要。
- [ ] S06（验收）：补齐管理员/普通用户授权、组件状态与交互测试，执行 typecheck、lint、test、build 和差异检查。
