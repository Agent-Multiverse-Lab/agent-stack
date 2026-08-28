# docs/spec 索引

`docs/spec/` 按能力而不是源码文件组织，并通过索引逐层披露上下文。

| Domain | 职责 | 入口 |
| --- | --- | --- |
| Run | 生命周期、取消、事件流、消息持久化、打断恢复 | [run/README.md](run/README.md) |
| Agent | 上下文管理、子代理委派 | [agent/README.md](agent/README.md) |
| Knowledge | 输入处理、检索、评估 | [knowledge/README.md](knowledge/README.md) |
| Persistence | 状态和存储所有权 | [persistence/README.md](persistence/README.md) |
| Product | 产品身份和跨页面体验 | [product/README.md](product/README.md) |

## Capability 结构

```text
<domain>/<capability>/
├── README.md                 # 可选的能力入口，只做路由
├── spec.md                   # 单一现行能力契约
├── plan.md                   # 当前变更总览和阅读路由；没有当前变更时可不存在
├── tasks.md                  # 当前一次变更的任务；与 plan 同生命周期
├── implementation/          # 可选；大型变更按真实职责拆分的当前实施细节
│   └── <responsibility>.md
└── history/
    └── <version>/
        ├── plan.md           # 已完成计划快照
        └── tasks.md          # 有任务快照时保留
```

`spec.md` 是当前目标行为，不记录版本演进。根目录 `plan.md` / `tasks.md` 只描述一次当前变更。
简单变更不创建 `implementation/`；大型跨系统变更由根计划路由到按职责命名的实施切片。完成后
先把实施切片合并回完整计划，再只将 `plan.md` / `tasks.md` 移入 `history/<version>/`；历史目录

如果一个 spec 同时承载多个可独立验收的职责，应按能力边界拆成具名的 sub-capability，并由
上级 README 路由；不要按版本、日期或文件长度机械分片。

## 加载顺序

1. 从本页选择一个 domain，不扫描全部 capability。
2. 读取该 domain 的 README，定位一个 capability。
3. 读取该 capability 的 `spec.md`，确认当前契约。
4. 只有需要设计或实施时，才读取根目录当前的 `plan.md` 和 `tasks.md`。
5. 如果根计划存在实施切片，只读取当前 Task 明确指向的 `implementation/<responsibility>.md`。
6. 只有追溯、回归或比较旧设计时，才读取明确指定的 `history/<version>/`。

架构归属先从 [`docs/architecture/README.md`](../architecture/README.md) 判断。具体维护规则以
[`docs/working-rules.md`](../working-rules.md) 为准。
