# 工程决策记录

决策记录保存非平凡工程变更的背景、决定、真实替代方案、后果与验证入口。它补充代码与 `ARCHITECTURE.md`，不替代源码或测试作为运行时事实来源。

## 生命周期目录

按需在 `docs/develop-guides/decisions/` 下创建对应子目录（仅在存在记录时创建空目录以外的文件）：

- `proposed/`：尚未实施的提案，用于较大或跨模块改动前对齐方向与验收场景。
- `implemented/`：已合入生效的当前决定，使用现在时表述。
- `rejected/`：明确放弃且值得保留原因的提案，不构成实现约束。
- `archived/`：已冻结或被后续决定完全取代的历史记录。

提案实施稳定后，将文件移入 `implemented/` 并改写为现在时，删除提案阶段的进度列表与“应当”式描述；若影响系统边界或长期不变量，将精炼结论同步至根 [ARCHITECTURE.md](../../../ARCHITECTURE.md)。被部分取代时交叉链接；完全失去当前价值时移入 `archived/`。

`docs/vibe/` 已加入 `.gitignore`，仅用于本地临时计划与草稿，不进入 Git 也不作为决策或历史依据。

## 何时需要

满足任一条件时编写决策记录：

- 改变持久状态模型、事务发布点、Run/Worker 生命周期或权限隔离边界；
- 改变跨模块或对外公开契约；
- 引入新的核心抽象、基础设施依赖或需要长期维护的取舍。

普通 bug 修复、单点调整、局部文案或机械重构直接实施，无需创建决策文档。

## 文件命名与模板

文件名使用 `YYYY-MM-DD-topic.md`。

### `proposed` 模板

```markdown
# 决策标题

状态：proposed
类型：feature | architecture | simplification | bug-fix
Owner：相关代码或文档边界

## 问题与目标
## 方案与取舍
## 替代方案
## 核心验收场景
```

### `implemented` 模板

```markdown
# 决策标题

状态：implemented
类型：feature | architecture | simplification | bug-fix
Owner：相关代码或文档边界

## 问题
## 决策
## 替代方案
## 后果
## 验证
```

记录应保持精炼（建议 30~80 行），聚焦边界、取舍与验收重点，不保存逐函数清单、施工流水账或推断过程。
