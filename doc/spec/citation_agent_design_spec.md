# CitationAgent 简要设计

状态：首期代码已创建并注册；当前为 Prompt 驱动，尚未形成确定性强制门禁，
SearchAgent 的结构化证据输出也仍需后续收口。

## 1. 目标与位置

`CitationAgent` 是 `LeaderAgent` 管理的内部子 Agent，与 `SearchAgent`、
`OutlineAgent` 平级，放在：

```text
src/agents/subagents/citationagent/
├── __init__.py
├── agent.py
├── prompt.py
├── context.py
└── state.py
```

它用于验证回答中的事实声明是否被检索结果支持，不作为公开会话 Agent，也不取代
`SearchAgent`。

推荐链路：

```text
LeaderAgent
  -> SearchAgent 返回带稳定 source_id 的证据
  -> LeaderAgent 形成带引用的回答草稿
  -> CitationAgent 校验声明、证据和引用的对应关系
  -> LeaderAgent 根据校验报告生成最终回答
```

## 2. 职责边界

`CitationAgent` 负责：

- 检查引用的 `source_id` 是否存在。
- 检查引用片段是否直接或部分支持对应声明。
- 标记缺少引用、引用错位、证据冲突和证据不足。
- 返回结构化校验报告，供 `LeaderAgent` 修订最终回答。

`CitationAgent` 不负责：

- 主动执行知识库或互联网检索。
- 根据常识补全检索结果中不存在的证据。
- 扩写新的事实声明。
- 直接交付最终用户回答。
- 写数据库、队列、Redis Stream 或对象存储。

证据不足时只返回 `needs_retrieval`，由 `LeaderAgent` 决定是否重新调用
`SearchAgent`。

## 3. 输入与输出

首期输入保持最小结构：

```json
{
  "draft": "待验证的回答草稿",
  "claims": [
    {
      "claim_id": "claim_001",
      "text": "待验证声明",
      "citation_ids": ["source_001"]
    }
  ],
  "sources": [
    {
      "source_id": "source_001",
      "title": "来源标题",
      "uri": "来源地址或知识文件标识",
      "excerpt": "实际检索片段"
    }
  ]
}
```

不能只传 URL；语义支持校验必须拿到实际检索片段。首期可通过现有
`SubAgentMiddleware` 的任务描述传递该结构，不新增传输协议。

输出保持为：

```json
{
  "verdict": "pass | revise | needs_retrieval",
  "items": [
    {
      "claim_id": "claim_001",
      "status": "supported | partially_supported | unsupported | citation_missing",
      "citation_ids": ["source_001"],
      "reason": "简短校验理由"
    }
  ]
}
```

`LeaderAgent` 是最终回答的唯一所有者。CitationAgent 只返回报告，不返回改写后的
完整答案。

## 4. 包内文件职责

- `agent.py`
  - 定义并构造 `CitationAgent`。
  - 只负责模型、Prompt、Context、State、工具和中间件装配。
  - 首期不配置检索工具。
- `prompt.py`
  - 保存 CitationAgent 系统提示词和 Prompt 构造逻辑。
  - 明确只依据输入证据判断，不允许补造来源。
- `context.py`
  - 定义 `CitationAgentContext`，继承公共 `BaseContext`。
  - 只保存运行配置，不存放本次待验证草稿和证据。
- `state.py`
  - 定义声明、证据和校验报告等结构化状态。
  - 本次调用的数据放 State，不通过 Context 传递。
- `__init__.py`
  - 仅导出 `CitationAgent`，供 `AgentManager` 发现。

只有出现 CitationAgent 专属且真实使用的确定性工具时才新增 `tools.py`，不预建空模块。

## 5. 当前实现

当前已完成：

1. 已在 `src/agents/subagents/citationagent/` 创建标准五文件包。
2. 已在 `LeaderAgent._create_middlewares(...)` 中注册 `CitationAgent()`。
3. 保持 `AgentManager` 自动发现和 Worker 内部 Agent 注册链路不变。
4. 已在 LeaderAgent 编排规则中约定：使用检索证据且最终回答包含引用时，先调用
   CitationAgent 再交付答案。

尚未完成：

- `SearchAgent` 还没有严格的结构化证据输出契约；当前调用方必须在 CitationAgent
  任务中显式提供 `source_id`、来源信息和实际检索片段。
- CitationAgent 尚未成为最终输出前的确定性强制门禁。

首期是 Prompt 驱动的校验步骤，不声称已经形成强制门禁。如果后续要求任何带引用回答
都必须经过校验，应在 LeaderAgent 最终输出边界增加确定性检查，而不是仅依赖模型自行
决定是否调用子 Agent。

## 6. 首期验收边界

- CitationAgent 被识别为内部 Agent，不出现在公开会话 Agent 列表。
- 输入中的每个 `citation_id` 都能映射到一个来源。
- 支持、部分支持、不支持和缺少引用四类结果可稳定区分。
- 缺少实际检索片段时返回 `needs_retrieval`。
- CitationAgent 不调用检索工具，也不生成最终用户回答。
- LeaderAgent 能取得校验报告并据此修订最终答案。

不在首期范围：

- 自动访问 URL 验证页面实时可用性。
- 学术引用格式转换。
- 引用质量评分模型训练。
- 用 CitationAgent 替代 RAGAS 或离线评测。
