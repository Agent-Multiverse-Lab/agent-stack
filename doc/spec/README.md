# 设计规格目录

`doc/spec/` 按主要代码所有者镜像当前仓库结构。每份规格只保存一份；跨层改动仍在
该规格内列出受影响文件，不复制到多个目录。

## 归档规则

1. 以 `doc/spec/` 为根，最多使用四层子目录。
2. 目录名使用仓库中的真实路径，例如 `server/router/`、`src/agents/`、
   `web/src/views/`；不增加 `frontend/`、`backend/` 等虚拟分层。
3. 规格放在主要实现所有者下。跨层规格不重复保存，其他边界通过文档内的文件计划表达。
4. 只创建已有规格需要的目录，不为未来功能预建空目录。
5. 页面规格放在 `web/src/views/`；仅涉及组件的规格才放在
   `web/src/components/<area>/`。
6. 图片等规格资产放在所属区域最近的 `assets/`，不得散落回 `doc/spec/` 根目录。
7. 移动或重命名后直接更新引用并删除旧路径，不保留兼容副本。

## 当前结构

```text
doc/spec/
├── README.md
├── server/
│   ├── router/
│   │   ├── library-attachment.md
│   │   └── thread-conversation.md
│   └── service/
│       └── queue.md
├── src/
│   ├── agents/
│   │   ├── agent.md
│   │   ├── backends/
│   │   │   └── sandbox.md
│   │   └── subagents/
│   │       └── citation-agent.md
│   ├── database/
│   │   └── async-postgres-store.md
│   ├── knowledge/
│   │   ├── rag.md
│   │   └── rag_eval/
│   │       └── retrieval-evaluation.md
│   └── model/
│       └── reranker/
│           └── reranker.md
└── web/
    └── src/
        └── views/
            ├── ChatView.md
            ├── FeatureViews.md
            ├── KnowledgeView.md
            └── assets/
                ├── chat-agent-execution-states.png
                ├── chat-agent-tool-chain.png
                └── chat-attachment-capsule.png
```

## 规格索引

| 主要代码区域 | 规格 |
| --- | --- |
| `server/router/` | [Thread API](server/router/thread-conversation.md)、[Library Attachment API](server/router/library-attachment.md) |
| `server/service/` | [Agent Run Queue](server/service/queue.md) |
| `src/agents/` | [Agent 总体结构](src/agents/agent.md)、[Sandbox Backend](src/agents/backends/sandbox.md)、[CitationAgent](src/agents/subagents/citation-agent.md) |
| `src/database/` | [AsyncPostgresStore 与 Saver](src/database/async-postgres-store.md) |
| `src/knowledge/` | [RAG 主链路](src/knowledge/rag.md)、[检索评估](src/knowledge/rag_eval/retrieval-evaluation.md) |
| `src/model/` | [Reranker](src/model/reranker/reranker.md) |
| `web/src/views/` | [ChatView](web/src/views/ChatView.md)、[功能 View 拆分](web/src/views/FeatureViews.md)、[KnowledgeView](web/src/views/KnowledgeView.md) |
