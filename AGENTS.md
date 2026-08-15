# Repository Agent Guide

This file is the canonical project guide for Claude/Codex-style coding agents.
It contains both repository-wide working rules and the current operational model
of `multi-agent-s2c`. It must remain useful on its own; it is not merely an index
to other documents.

`CLAUDE.md` imports this file directly. Update `AGENTS.md` whenever the current
module boundaries, runtime flows, ownership rules, development commands, or
agent workflow change.

## 1. Working Rules

- Before implementing a new feature or a change that affects code, API, data
  models, architecture, interaction design, cross-module behavior, or public
  contracts, first identify the owning capability under `docs/spec/` and create
  or update its specification artifacts. Present the proposed scope and plan to
  the user, explicitly ask for confirmation, and wait for approval before
  modifying production code. Routine operations that do not require design,
  such as installing an explicitly requested dependency, do not require a new
  specification.
- Organize specifications by capability rather than by source file. One
  capability may span routers, services, workers, repositories, adapters,
  frontend modules, and tests. Do not mirror the source tree under `docs/spec/`
  and do not create one specification per file.
- Use the artifacts as follows:
  - `spec.md` defines intended behavior, goals, non-goals, invariants, contracts,
    edge cases, and acceptance criteria.
  - `plan.md` defines implementation design, concrete file modifications, code
    examples, failure handling, and validation.
  - `tasks.md` defines ordered, independently verifiable work items and the
    requirements each task implements.
- Write specifications and plans as positive, executable scope. Every listed
  behavior, file modification, example, and validation step must correspond to
  work that will actually be performed.
- A non-trivial `plan.md` must include concrete examples for the core contracts
  and control flow. Each example must name its target file and owning function,
  class, method, or document section. Prose-only plans and unplaced snippets are
  incomplete.
- Reference related capabilities by canonical document path and stable
  requirement IDs. Do not duplicate the same contract, invariant, or example in
  multiple specifications.
- When creating or revising a specification or plan, use the `ponytail` skill
  before presenting it when that skill is available. Remove every proposed file,
  abstraction, component, and compatibility path that is not required for the
  smallest confirmed end-to-end implementation.
- Preserve the existing directory structure, module boundaries, and public
  contracts whenever possible. If a task requires moving or deleting existing
  files, changing established ownership, or restructuring existing modules,
  stop first, explain why the structural change is necessary and what it
  affects, then wait for the user's explicit approval before proceeding.
- Do not preserve backward compatibility. Remove obsolete application paths
  instead of adding compatibility layers, legacy fallbacks, duplicate old/new
  implementations, or transitional compatibility migrations. Normal Alembic
  schema migrations are still required for database schema changes.
- Choose the simplest implementation that fully meets the current requirements.
  Avoid speculative abstractions, configuration, extension points, and
  indirection.
- Grow the system in layers. Start from the smallest version that works end to
  end, and add each capability on top of a product that already works. Every
  implementation step should leave the repository coherent and testable. Never
  trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall
  complexity or improve reliability. Lean on existing dependencies before
  writing custom implementations or adding packages. Check library
  documentation and types before assuming a capability is missing.
- Make architectural decisions for the long term. Do not accept a stopgap that
  is explicitly intended to be replaced later.
- Before submitting, ask whether a senior engineer would consider the result
  over-designed, over-defensive, excessively nested, or overly fragmented. If
  so, simplify it first.

## 2. Documentation Ownership

The repository documentation is organized as follows:

```text
docs/
├── constitution.md       repository-wide engineering principles
├── README.md             documentation index
├── architecture/         long-lived boundaries, topology, and ownership
├── spec/                 capability behavior, plans, and tasks
└── adr/                  long-lived technical decisions and trade-offs
```

A capability normally uses:

```text
docs/spec/<domain>/<capability>/
├── spec.md
├── plan.md
└── tasks.md
```

Create only populated artifacts. Small changes may omit `plan.md` or `tasks.md`
when those files add no useful information.

Document responsibilities are complementary:

- `AGENTS.md` records the current project operating model and agent workflow.
- `constitution.md` records stable repository-wide principles.
- Architecture documents explain long-lived boundaries and ownership.
- `spec.md` defines what a capability must do.
- `plan.md` maps that capability to implementation.
- `tasks.md` records the approved work breakdown.
- ADRs explain why a long-lived technical decision was selected.
- Code and tests implement and verify those documents.

Do not duplicate full architecture or capability specifications in this file.
However, keep the current project shape, critical boundaries, active runtime
flows, and non-negotiable implementation rules here. When those current facts
change, update both the owning detailed document and this guide.

If the Constitution, this guide, architecture documents, specifications, ADRs,
tests, and implementation disagree, do not silently choose whichever is easiest.
Identify the conflict and resolve the authoritative documents before proceeding.

## 3. Current Project Shape

`multi-agent-s2c` is a general-purpose multi-agent system for technical learning
and engineering practice. The backend is a FastAPI service built around
LangChain/LangGraph agents, SQLAlchemy repositories, PostgreSQL, Redis/ARQ
background execution, MinIO-backed files, Milvus knowledge retrieval, and a
standalone sandbox service.

Current top-level responsibilities:

- `server/`: FastAPI transport and application orchestration.
  - Routers own authentication, HTTP validation, and response shaping.
  - Services own cross-repository and infrastructure use cases.
  - `lifespan.py` and `worker.py` own separate process lifecycles.
  - Router request and response models live in `server/entities/`.
  - Do not put SQL queries, Agent reasoning, or client construction in routers.
- `src/agents/`: Agent contracts, top-level and internal Agents, middleware, MCP
  integration, and Agent-facing backends.
  - Agents are context-driven `BaseAgent` packages.
  - Tools and middleware are assembled at the concrete Agent boundary.
  - Agents must not own HTTP, database, queue, or object-storage workflows.
- `src/configs/`: typed settings, environment parsing, defaults, and validation.
  Configuration modules must not perform business orchestration or hold mutable
  runtime state outside the concrete Agent context.
- `src/model/`: provider-neutral Chat, Embedding, and Reranker construction.
  Rerankers score caller-supplied candidates and must not query databases or
  vector stores.
- `src/database/`: SQLAlchemy models, PostgreSQL lifecycle/session helpers, and
  repositories. All persistence queries belong in responsibility-named
  repositories.
- `src/knowledge/`: document parsing, extraction, chunking, embedding support,
  Milvus access, retrieval, and evaluation. Processing is an explicit pipeline
  with narrow Parser, Extractor, Chunker, PostProcessor, and provider contracts.
- `src/storage/`: thin MinIO and Redis/ARQ infrastructure adapters. Domain
  semantics such as Run lifecycle and cancellation remain in application
  services.
- `src/third_party/`: small compatibility boundaries around external SDKs. Do
  not place application policy or generic utilities here.
- `src/utils/`: small, stateless, domain-neutral helpers shared by multiple
  subsystems. A helper used by one subsystem belongs in that subsystem.
- `sandbox_server/`: independently deployed sandbox management service. It must
  not own application persistence or Agent Run orchestration.
- `web/`: Vue 3 and TypeScript frontend. Keep API consumption and presentation
  concerns here; backend domain rules remain in the backend.
- `test/`: deterministic unit and contract tests plus clearly named manual demos.
  Avoid live network dependencies in the default suite.
- `docker/`: Dockerfiles and Compose topology only. Keep service wiring,
  environment mapping, volumes, and health checks declarative.
- `migrate/`: Alembic environment and ordered schema revisions. Keep application
  startup, business seeding, Worker, Agent, queue, and storage behavior out.
- `scripts/`: repeatable maintenance entry points with explicit inputs,
  observable behavior, and no import-time side effects.
- `docs/`: Constitution, architecture, capability specifications, ADRs, diagrams,
  and supporting assets. Organize specifications by capability, not by source
  path.

Dependency direction is:

```text
routers -> services -> repositories / infrastructure adapters
```

Agent and Knowledge Flow packages receive runtime values through declared
contexts or method contracts and must not import server routers. Cross-layer
use-case coordination belongs in `server/service/`; format-specific processing
belongs in `src/knowledge/flow/`.

## 4. Backend and Agent Runtime Boundaries

- Shared Agent primitives live in `src/agents/base_agent.py` and
  `src/agents/base_context.py`.
- Public top-level Agents live under `src/agents/<agentname>/`; internal Agents
  live under `src/agents/subagents/<agentname>/`. Each package exposes its
  concrete Agent class from `__init__.py`.
- A standard internal Agent package uses:

  ```text
  __init__.py   exports the concrete Agent
  agent.py      assembles model, Prompt, Context, State, tools, middleware
  prompt.py     owns system Prompt and Prompt construction
  context.py    owns runtime configuration extending BaseContext
  state.py      owns graph State and structured input/output contracts
  ```

  Add `tools.py`, `middleware.py`, or other modules only for real package-local
  behavior. Do not create package-shaped placeholders for future ideas.
- `SearchAgent` and `OutlineAgent` predate the standard package structure. Move
  them only in an explicitly approved structural refactor; do not opportunistically
  add empty modules.
- `AgentManager` discovers public and internal `BaseAgent` subclasses and keeps
  internal Agents out of the public conversation Agent list.
- `BaseAgent.stream_messages(...)` uses LangGraph `astream(...)`.
  `BaseAgent.stream_messages_with_event(...)` consumes
  `astream_events(version="v3")` and forwards the `messages` channel's
  `params.data` payload.
- `LeaderAgent` is the public general-purpose orchestrator. Keep its base Prompt
  domain-neutral. Specialized behavior belongs in tools, internal Agents, or
  runtime context.
- `SubAgentMiddleware` exposes Run-backed delegation tools for registered
  internal Agents. It does not execute an embedded child runnable inside the
  parent graph. Persistence, queueing, and storage stay outside Agents.
- `SearchAgent` owns bounded query planning, retrieval, source comparison, and
  evidence synthesis. Search remains opt-in through `LeaderAgent`; it does not
  produce the parent's final response.
- `CitationAgent` validates only supplied claims, source mappings, and excerpts.
  It remains tool-free, does not retrieve or invent sources, and returns
  `pass`, `revise`, or `needs_retrieval`. The current integration is Prompt-driven,
  not a deterministic final-output gate.
- `OutlineAgent` produces a bounded outline artifact for its parent. It remains
  tool-light and must not become another top-level orchestrator.

Agent runtime configuration has exactly three sources:

1. The concrete Agent or SubAgent context class, including schema and defaults.
2. Values supplied for the current Run.
3. Values loaded by the backend for the current Agent or Run.

Merge Run-supplied and backend-loaded values into the concrete context before
execution. The resulting context is the only runtime configuration source for
Agents, SubAgents, middleware, tools, and backends. Do not add parallel module
globals, middleware-local defaults, ad hoc keyword arguments, or direct runtime
configuration reads. Per-invocation messages and similar payloads are State, not
runtime configuration.

## 5. API, Worker, and Agent Run Flow

- FastAPI construction lives in `server/main.py`; API startup and shutdown live
  in `server/lifespan.py`.
- Lifespan startup verifies JWT configuration and initializes API PostgreSQL
  resources. It does not create tables or seed records. Shutdown closes shared
  Redis before disposing PostgreSQL.
- HTTP routes live under `server/router/`. Thread-level execution and attachment
  orchestration live in `server/service/thread_service.py`; do not create a
  parallel `conversation_service.py`.
- Agent Run creation, cancellation, and SSE exposure live in
  `server/router/agent_router.py` and `server/service/agent_run_service.py`.
- `server/service/arq_queue_servcie.py` owns ARQ pool access, raw Redis Stream
  operations, cancellation keys, and cancellation Pub/Sub operations. Keep the
  existing filename spelling unless a dedicated rename is approved.
- `src/storage/redis/redis_manger.py` owns only Redis/ARQ client construction,
  shared-client lifecycle, and close behavior. It must not own Agent Run
  semantics.
- `server/worker.py` is the independent ARQ Worker entry point and startup owner
  for Worker-side database bootstrap. It may create missing tables and missing
  Agent registration rows, but must not drop tables, seed users/conversations,
  or overwrite existing Agent rows. Worker shutdown disposes only Worker-owned
  PostgreSQL resources.

The current queued flow is:

```text
POST /api/chat/thread
    -> create Conversation
POST /api/agent/runs
    -> persist triggering Message and AgentRun
    -> enqueue run_id through ARQ
Worker process_agent_run(...)
    -> reload Run, Message, and User
    -> set running
    -> stream Agent execution
    -> persist completed / failed / cancelled
GET /api/agent/runs/{run_id}/events
    -> read Redis Stream
    -> format SSE frames
```

ARQ receives only `run_id`, uses job ID `run:{run_id}`, and writes to the
configured queue. The Worker produces events; enqueueing does not invoke the SSE
endpoint. Consumers independently open the SSE endpoint.

SubAgent Runs reuse the same durable flow. `AgentRun.run_type` selects `chat` or
`subagent`; `parent_run_id` records relationships and must not be used as a type
flag. Child Run operations must verify ownership by the current parent Run.

Current event and cancellation rules:

- `process_agent_run(...)` publishes `messages`, `values`, and
  `agent_execute_event` entries to `run:events:{run_id}`.
- Running lifecycle events use `type: "status"`, `status: "running"`.
- Terminal events use `type: "end"` and one of `completed`, `failed`, or
  `cancelled`.
- Cancellation first persists `cancel_requested` for the target Run and active
  direct child Runs in one transaction. After commit, it writes
  `run:cancel:{run_id}` and publishes the Run ID to channel `run:cancel`.
- The Worker checks the cancellation key and listens to Pub/Sub. A matching
  signal sets a Run-local `asyncio.Event`, stops the active Agent stream,
  persists `cancelled`, publishes one terminal event, and clears the key.
- Cancellation scope does not branch on `run_type`.
- Rebuild the Compose Worker after backend source changes because the Worker
  image does not bind-mount the checkout.

## 6. Persistence and Identifier Boundaries

- PostgreSQL is the source of truth for users, Agents, conversations, messages,
  attachments, knowledge records, and Agent Run lifecycle state.
- Redis/ARQ queue state and Redis Stream events are runtime coordination data,
  not authoritative business state.
- `Conversation.id` is the database primary key;
  `Conversation.thread_id` is the external conversation/runtime identifier.
- `Message.id` identifies the persisted triggering input.
  `AgentRun.trigger_message_id` lets the Worker reconstruct input from `run_id`.
- `AgentRun.run_type` is the execution-kind flag. `AgentRun.parent_run_id` is a
  relationship field.
- `AgentRun.agent_status` is the only lifecycle field.
- Current coarse states are `pending`, `running`, `cancel_requested`,
  `completed`, `failed`, and `cancelled`.
- ARQ jobs use `run:{run_id}`.
- Event Streams use `run:events:{run_id}`.
- Cancellation keys use `run:cancel:{run_id}` and Pub/Sub uses `run:cancel`.
- Redis Stream IDs are event cursors, not Run IDs or durable business status.
- Do not duplicate authoritative state across PostgreSQL, Redis, memory, MinIO,
  or Milvus without explicitly documented ownership, lifetime, consistency, and
  cleanup behavior.

## 7. Knowledge and Attachment Flow

Knowledge-file processing is intentionally split:

```text
upload -> parse -> parsed Markdown review -> explicit index confirmation
       -> chunk -> embed -> Milvus -> indexed
```

- Uploading or parsing must never trigger indexing implicitly.
- Only a file in `parsed` state may enter `indexing`.
- Indexing reloads persisted Markdown, applies the configured Chunker and
  Embedding binding, writes stable `file_id + chunk_index` records, and marks the
  file `indexed`.
- Indexing failure returns the file to `parsed` so the same artifact can be
  retried.
- Current file states are `uploaded`, `parsing`, `parsed`, `indexing`, `indexed`,
  and `failed`.
- `src/knowledge/flow/pipeline.py` exposes parsing and chunking as separate
  stages. Do not restore an all-in-one `run(...)` path.
- `src/knowledge/flow/parser/parser.py` is the only public Parser. It routes by
  normalized file suffix and must not infer formats from content or send one
  input through multiple parsers.
- OCR Extractors are called only by PDF or image parsing paths. They do not
  select file types, chunk content, or write knowledge records.
- Chunking belongs under `src/knowledge/flow/chunker/`. `TokenChunker` uses a
  fixed token step. `TitleChunker` explicitly selects `group` or `hierarchy`;
  do not restore content-inferred document profiles.
- Parser, Extractor, Chunker, and PostProcessor exchange only the canonical
  block and chunk structures from `src/knowledge/flow/types.py`.
- `src/knowledge/embedding_service.py` owns batching and vector validation for
  an injected Embeddings instance. It must not select Provider configuration or
  import Agent packages.
- `KnowledgeEmbeddingBinding` binds each `uid + kb_id` to one model specification,
  observed dimension, batch size, and Milvus collection. Later indexing and
  query paths must load it and reject model or dimension drift.
- `MilvusKnowledge` is a thin vector-store adapter. It receives already embedded
  records and owns collection creation plus CRUD; it must not read object
  storage, choose Chunkers, load models, generate vectors, or update PostgreSQL
  file state.
- `knowledge_service.search(...)` owns two-stage retrieval: retrieve Milvus
  candidates, rerank their text, and return the final limit. Keep Milvus
  `distance` separate from `rerank_score`.
- Post-processing remains isolated in `src/knowledge/flow/post_processor.py` and
  is not wired into the active parse/index chain without a dedicated approved
  requirement.
- `Attachment` is a user-owned uploaded file and does not belong directly to a
  Conversation. `MessageAttachment` records usage by a Message. Deleting a
  Conversation removes message references, not the Attachment.
- Attachments use the private `attachment` MinIO bucket and remain uploaded
  originals. The Worker must not parse, move, clean, or turn them into
  `KnowledgeFile`, Chunk, Embedding, or Milvus records.

## 8. Authentication Boundary

- Authentication is email-and-password based.
- `User.email` is the unique login account; `User.uid` is the stable business
  identifier used by conversations and Agent Runs.
- Current endpoints are `POST /api/auth/register`, `POST /api/auth/login`, and
  `GET /api/auth/me`.
- JWT payloads carry the numeric database user ID in `sub`, plus `uid`, `email`,
  and `is_active`.
- `AuthMiddleware` decodes an optional Bearer token into
  `request.state.auth_payload`; protected routes resolve the database user
  through `AuthenticatedUser`.
- Password hashing, JWT creation/validation, and user lookup remain in
  `server/utils/auth.py`, the auth router, and `UserRepository`. Do not duplicate
  authentication logic in feature routes.

## 9. Development Commands

Backend API:

```bash
uv sync
python server/main.py
```

ARQ Worker:

```bash
uv run --no-sync arq server.worker.WorkerSettings
```

Database migrations:

```bash
uv run --no-sync alembic upgrade head
uv run --no-sync alembic downgrade -1
```

Local infrastructure and Worker:

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis minio sandbox worker
```

Targeted backend validation:

```bash
uv run --no-sync python -m compileall server/router server/service server/worker.py src/agents src/database/repositories src/storage
git diff --check
```

`pytest` is not currently declared as a project dependency. Do not report pytest
validation unless it is installed and the tests were actually run. If `uv run`
is blocked by local cache permissions, use the repository virtual environment,
for example `.venv/bin/python -m compileall -q <paths>`.

## 10. Contribution Rules

- Follow `CONTRIBUTING.md` for repository contribution workflow.
- Pull requests should include a concise Chinese summary and motivation unless
  the task explicitly requires another language.
- Link the issue or task ID when available.
- Include verification notes with the commands run and outcomes.

## 11. Git Commit Rules

- Use Conventional Commits: `<type>(<scope>): <subject>`.
- `type` must be one of `feat`, `fix`, `refactor`, `doc`, `test`, `chore`,
  `build`, or `ci`.
- Use a concise lowercase English scope such as `agent`, `thread`, `worker`,
  `auth`, or `deps`.
- Write the subject and optional body in Chinese. Keep the subject concise,
  preferably no more than 72 characters, and do not end it with punctuation.
- Examples:
  - `feat(worker): 发布 Agent Run 流式事件`
  - `fix(auth): 修复令牌校验失败`
  - `doc(agent): 更新仓库代理指南`
- Do not wrap commit messages, subjects, or scopes with `@` characters.
- Before pushing, especially after committing from PowerShell, inspect all
  outgoing subjects and bodies for accidental `@` wrappers and correct them.
- Keep one commit focused on one coherent change.
