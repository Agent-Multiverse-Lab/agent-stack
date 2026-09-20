# Settings 模型管理任务

- [x] T01（MODEL-SETTINGS-001～004）：完成现行设计图，并同步规格、执行计划和本清单，清除已被替代的设计要求。
- [x] T02（MODEL-SETTINGS-001～002）：接入 Settings 的 Models 入口及八个供应商选项，实现三栏布局；以留白组织内容，仅保留配置与模型列表之间的细分隔线；厂商采用本地彩色 SVG。
- [x] T03（MODEL-SETTINGS-003）：实现启用开关、API Key 与 Base URL，API Key 标签在输入框上方、加密存储说明在下方，Base URL 名称内嵌；API Key 输入值同排右侧使用 Lucide 显隐和无底色插头图标，检测操作无可见文字；不显示协议、请求头或底部检测按钮。
- [x] T04（MODEL-SETTINGS-003～004）：模型名称居左，单色能力标签在同一行最右侧；默认无背景、无边框，hover 仅加深背景；不展示请求体覆盖、模型卡片、行分隔线或额外说明。
- [x] T05（MODEL-SETTINGS-002～005）：实现真实管理 API、能力元数据解析、启用、保存、获取模型及图标检测；通过确定性测试验证失败保留输入，未展示的后端配置不被清空。
- [x] T06（MODEL-SETTINGS-001～005）：完成浏览器模拟 API 交互、五种宽度、长名称、hover 和键盘验证；执行 typecheck、lint、build、后端 31 项测试与差异检查，结果和已有问题见 plan.md。
- [ ] T07（MODEL-SETTINGS-005）：在具备 Docker、PostgreSQL、Redis 与真实模型密钥的环境中确认迁移、重建 Worker，并验证真实厂商连接。本地缺少 docker 命令，尚未完成环境联调。
