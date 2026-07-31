# Repository Agent Guide

This file is the single source of repository guidance for Claude/Codex-style coding agents. `CLAUDE.md` imports this file directly, so update `AGENTS.md` whenever architecture or workflow guidance changes.

## Current Project Shape

`multi-agent-s2c` is a general-purpose multi-agent system for technical learning
and engineering practice. The backend is a FastAPI service built around
LangChain/LangGraph agents, SQLAlchemy repositories, PostgreSQL, Redis/ARQ
background work, and MinIO-backed uploads.

Current top-level responsibilities and construction rules:

- `server/`: FastAPI transport and application orchestration. Build it from thin
  routers, responsibility-named services, explicit middleware, and separate API
  and worker lifecycle entrypoints. Routers own HTTP validation and response
  shaping; services own use-case coordination; lifespan and worker hooks own
  process resources. Do not put SQL queries, agent reasoning, or storage-client
  construction in routers.
- `src/agents/`: shared agent contracts, concrete top-level and internal agents,
  middleware, model helpers, MCP integration, and sandbox backends. Construct
  agents as context-driven `BaseAgent` packages, expose each concrete class from
  its package, and assemble tools and middleware at the concrete agent boundary.
  Agents must not own HTTP, database, queue, or object-storage workflows.
- `src/configs/`: typed Pydantic settings loaded from environment variables and
  `.env`. Keep parsing, defaults, and validation centralized here. Configuration
  modules must not perform business orchestration or introduce mutable runtime
  state outside the concrete agent context.
- `src/model/`: shared LangChain chat and Embedding model construction. Resolve
  `provider/model` specifications from `src/configs/model.py` here so Agents,
  Knowledge services, and other callers do not depend on each other.
- `src/database/`: SQLAlchemy models, PostgreSQL lifecycle/session helpers, and
  repositories. Define schema and relationships in models, centralize engine and
  session lifecycle, and place all persistence queries in responsibility-named
  repositories. Do not add HTTP, agent, queue, or storage orchestration here.
- `src/knowledge/`: document parsing and chunking, knowledge-provider adapters,
  and Milvus-backed knowledge access. Construct processing as explicit pipelines
  with narrow Parser, Extractor, Chunker, PostProcessor, and provider contracts.
  Keep database records, object storage, queues, and request handling outside
  the Flow.
- `src/storage/`: infrastructure adapters for MinIO and Redis/ARQ connections.
  Keep adapters thin and limited to client creation, connection lifecycle, and
  raw transport operations. Domain semantics such as Agent Run state and
  cancellation belong in application services.
- `src/third_party/`: compatibility boundaries for external libraries and SDKs.
  Expose a small local interface and isolate vendor-specific behavior; do not
  place application policy or general utilities here.
- `src/utils/`: small, stateless utilities shared across multiple packages.
  Utilities must remain domain-neutral and dependency-light. A helper used by
  one subsystem belongs in that subsystem instead.
- `test/`: deterministic backend unit and contract tests plus explicitly named
  manual demos. Mirror production boundaries, avoid live network dependencies in
  the default suite, and keep manual scripts distinguishable with `demo_` names
  or dedicated fixture directories.
- `sandbox_server/`: the standalone sandbox support service. Keep its API and
  container contract independent from the main FastAPI process; it must not own
  application persistence or Agent Run orchestration.
- `docker/`: Dockerfiles and Compose topology only. Keep service wiring,
  environment mapping, volumes, and health checks declarative; application
  behavior remains in production modules.
- `migrate/`: Alembic environment, revision template, and ordered database
  Schema versions. Keep only Schema changes and tightly coupled data backfills
  here; do not add application startup, connection lifecycle, business seeding,
  Worker, Agent, queue, or storage behavior.
- `scripts/`: repeatable maintenance entrypoints. Require explicit inputs, keep
  operations observable, and avoid import-time side effects.
- `doc/`: architecture diagrams and supporting project documentation. Keep
  diagrams aligned with the boundaries defined in this guide.

Dependencies should follow this ownership direction: routers call services, and
services call repositories or infrastructure adapters. Agent and Knowledge Flow
packages receive runtime values through their declared contexts or method
contracts and must not import server routers. Cross-layer use-case coordination
belongs in `server/service/`; format-specific processing belongs in
`src/knowledge/flow/`.

The public top-level agent is `LeaderAgent` in `src/agents/leaderagent/`. Current
internal subagents are `SearchAgent` and `OutlineAgent` under
`src/agents/subagents/`.

## Backend Architecture

- Shared agent primitives live in `src/agents/base_agent.py` and `src/agents/base_context.py`.
- Top-level agents live in `src/agents/<agentname>/`; internal agents live in `src/agents/subagents/<agentname>/`. Each package should expose its agent class from `__init__.py`.
- `AgentManager` in `src/agents/manager.py` discovers both groups, instantiates `BaseAgent` subclasses, and separately records top-level IDs so internal subagents are not exposed as public conversation agents.
- `LeaderAgent` replaced the former `DesignAgent`. Worker startup registration migrates the old database slug and its `Conversation.agent_id` / `AgentRun.agent_id` references; `AgentManager` keeps `DesignAgent` only as a non-public runtime compatibility alias for already-loaded work.
- `BaseAgent.stream_messages(...)` uses LangGraph `astream(...)`. `BaseAgent.stream_messages_with_event(...)` consumes `astream_events(version="v3")` and currently forwards the `messages` channel's `params.data` payload.
- `LeaderAgent` delegates search through the local `SubAgentMiddleware`. The middleware exposes Run-backed tools for `SearchAgent`; it does not execute an embedded runnable in the parent graph. Keep orchestration in `LeaderAgent`; do not move database, queue, or storage behavior into an agent.
- FastAPI application setup lives in `server/main.py`. Startup and shutdown live in `server/lifespan.py`.
- Lifespan startup verifies JWT configuration and initializes the API process's PostgreSQL resources. It does not create tables or seed records. Shutdown closes the shared async Redis client before disposing PostgreSQL.
- HTTP routes live under `server/router/`: `auth_router.py`, `thread_router.py`, `agent_router.py`, `knowledge_router.py`, `library_router.py`, and `model_router.py`.
- Thread creation, public agent listing, and temporary attachment upload live in `server/router/thread_router.py`. Thread-level agent execution helpers live in `server/service/thread_service.py`.
- Agent Run creation, cancellation, and SSE exposure live in `server/router/agent_router.py`. The cancellation endpoint calls `cancel_run_service(...)`, while the shared `request_cancel_agent_run(...)` path handles top-level and child Runs in `server/service/agent_run_service.py`.
- `server/service/arq_queue_servcie.py` owns ARQ pool access, direct Redis Stream `XADD`/`XREAD` operations, Agent Run cancellation-key `SET`/`EXISTS`/`DELETE` operations, and cancellation Pub/Sub `PUBLISH`/blocking `get_message` operations. Keep the existing filename spelling unless a dedicated rename is requested.
- `server/service/subagent_service.py` owns child conversation/message/Run persistence, parent-child ownership checks, and enqueue handoff. It does not own generic Agent Run cancellation; `SubAgentMiddleware` verifies parent-child scope there before calling `request_cancel_agent_run(...)`.
- `src/storage/redis/redis_manger.py` owns only Redis/ARQ connection creation, lazy shared-client initialization, and close behavior. It must not own Agent Run semantics.
- `server/worker.py` is the independent ARQ worker entrypoint and the single startup owner for database bootstrap. Worker startup initializes PostgreSQL, creates missing model tables with `checkfirst=True`, applies the non-destructive `AgentRun.run_type` column/index patch for existing databases, and inserts only missing public/internal Agent registration rows before accepting jobs. It must not drop tables, seed users or conversations, or overwrite existing Agent rows. Worker shutdown only disposes its own PostgreSQL resources; it does not reuse the FastAPI lifespan.
- Database access belongs in `src/database/repositories/`. Do not put persistence queries inside agents.

## Knowledge Flow

- Knowledge-file indexing is an explicit confirmation step. Only a file in
  `parsed` state may enter `indexing`; the service reloads its persisted
  Markdown, applies the configured Chunker and Embedding binding, writes stable
  `file_id + chunk_index` records to Milvus, and then marks it `indexed`.
  Indexing failures return the file to `parsed` so the same artifact can be
  retried. Uploading or parsing a file must never trigger this step implicitly.
- `MilvusKnowledge` is a thin database adapter. Its `build_file_index(...)`
  accepts only already embedded file records and owns Collection creation plus
  Milvus CRUD. It must not read object storage, select Chunkers, load Embedding
  models, generate vectors, or update PostgreSQL file state.
- `src/knowledge/flow/pipeline.py` exposes parsing and chunking as separate
  stages. `parse_document(...)` returns a `ParsedDocument` whose Markdown may be
  persisted for user review; `chunk_document(...)` runs only after the caller
  explicitly resumes indexing. Do not restore an all-in-one `run(...)` path.
- `src/knowledge/flow/parser/parser.py` is the only public document Parser. It
  routes by normalized file suffix; it must not infer formats from document
  content or send one input through multiple format parsers.
- OCR implementations live under `src/knowledge/flow/extractor/` and are called
  only by PDF or image parsing paths. Extractors do not select file types,
  chunk content, or write knowledge records.
- Chunking lives under `src/knowledge/flow/chunker/`. `TokenChunker` uses a
  fixed token step. `TitleChunker` explicitly selects `group` or `hierarchy`;
  both strategies reuse `BaseTitleChunker.invoke()` and the same
  outline-first, regex-frequency-fallback level resolver. Do not restore
  content-based `general` / `book` / `laws` / `paper` profile inference.
- `src/knowledge/embedding_service.py` accepts an injected LangChain
  `Embeddings` instance and owns batching plus vector result validation. It must
  not import Agent packages or choose Provider configuration.
- `KnowledgeEmbeddingBinding` durably binds each `uid + kb_id` to one model
  spec, observed dimension, batch size, and Milvus collection. Initial indexing
  creates this binding; every later indexing and query path must load it and
  reject model or dimension drift.
- `KnowledgeBase` owns logical knowledge-base metadata. `KnowledgeFile` belongs
  to exactly one KnowledgeBase and tracks `uploaded`, `parsing`, `parsed`,
  `indexing`, `indexed`, or `failed`. Conversation `Attachment` rows must never
  be reused for knowledge files.
- `server/service/knowledge_service.py` assembles the configured model and
  owns the parsing boundary: original files and parsed Markdown use
  `knowledge-files/{uid}/{kb_id}/{file_id}/...` MinIO paths, and parsing stops
  at `KnowledgeFile.status="parsed"`. Chunking, Embedding, and Milvus writes
  must not run before explicit user confirmation.
- Post-processing remains isolated in
  `src/knowledge/flow/post_processor.py` and is not wired into the current
  parse/index chain. `RaptorPostProcessor` uses an injected Embedding Provider
  and the RAGFlow UMAP + scikit-learn GaussianMixture/BIC algorithm; do not add
  it to `Pipeline` until a dedicated indexing requirement enables it.
- Parser, Extractor, Chunker, and PostProcessor exchange only the document block
  and chunk structures from `src/knowledge/flow/types.py`. Embedding Provider
  construction, persistence, object storage, and queue behavior remain outside
  the Flow.

## Agent Runtime Context

Agent runtime configuration has exactly three sources:

1. The context class defined by the concrete top-level agent or subagent, including its schema and defaults.
2. Values supplied for the current run.
3. Values loaded by the backend from the database for the current agent or run.

Run-supplied and database-loaded values must be merged into the concrete agent context before execution. The resulting context is the only source of runtime configuration for agents, subagents, middleware, tools, and backends. Do not introduce parallel runtime configuration through module globals, middleware-local defaults, ad hoc keyword arguments, or direct database/config reads; resolve those values first and bind them to the context.

Invocation data such as input messages and similar per-call payloads is not runtime configuration and may remain outside the context.

## Current Chat Flow

- Authentication is email-and-password based. `User.email` is the unique login account; `User.uid` is the stable business identifier used by conversations and Agent Runs.
- `POST /api/auth/register`, `POST /api/auth/login`, and `GET /api/auth/me` are the current auth endpoints.
- JWT payloads carry the numeric database user ID in `sub`, plus `uid`, `email`, and `is_active`.
- `AuthMiddleware` decodes an optional Bearer token into `request.state.auth_payload`; protected routes resolve the database user through `AuthenticatedUser`.
- Keep password hashing, JWT creation/validation, and user lookup in `server/utils/auth.py`, the auth router, and `UserRepository`; do not duplicate auth logic in feature routes.

## Current Thread and Agent Run Flow

The current queued flow is:

1. `POST /api/chat/thread` validates the authenticated user and a public top-level agent, then creates a `Conversation` with a generated `thread_id`.
2. `POST /api/agent/runs` requires `ENABLE_RUN_QUEUE=true`, validates ownership of the conversation, persists the triggering user `Message`, creates an `AgentRun` linked through `trigger_message_id`, and commits both records.
3. The router calls `enqueue_agent_run(run_id)`. ARQ receives only the `run_id`, uses job ID `run:{run_id}`, and writes to the configured `ARQ_QUEUE_NAME`.
4. The independent worker runs `process_agent_run(ctx, run_id)`, reloads `AgentRun`, the triggering `Message`, and `User` from PostgreSQL, changes the run to `running`, and calls `stream_thread_response(...)`.
5. `stream_thread_response(...)` resolves the database `Agent` by slug and role, builds runtime context, validates conversation ownership, and consumes `BaseAgent.stream_messages_with_event(...)`.
6. The worker changes the durable run state to `completed`, `failed`, or `cancelled` after execution.
7. `GET /api/agent/runs/{run_id}/events` now returns a `StreamingResponse` over `stream_agent_run_events(...)`, which reads `run:events:{run_id}` and formats SSE frames.

Subagent runs reuse that same durable flow. `task` creates and enqueues a child Run and waits for its result; `subagent_start` returns immediately, while `subagent_status`, `subagent_cancel`, and `subagent_await` operate only on child Runs belonging to the current parent Run. `AgentRun.run_type` explicitly selects the public orchestrator (`chat`) or registered internal Agent (`subagent`); `parent_run_id` records only the relationship between Runs and must not be used as a type flag.

Important current boundary:

- `process_agent_run(...)` publishes `messages`, `values`, and `agent_execute_event` entries to `run:events:{run_id}`. Lifecycle notifications use `type: "status"` with `status: "running"`; every terminal notification uses `type: "end"` with `status: "completed"`, `"failed"`, or `"cancelled"`.
- Cancellation is two-phase: `POST /api/agent/runs/{run_id}/cancel` passes the request-scoped database session through `cancel_run_service(...)` to `request_cancel_agent_run(...)`. The latter first marks the target Run and all of that user's active direct child Runs as `cancel_requested` in one transaction, then writes each `run:cancel:{run_id}` and publishes its Run ID to the `run:cancel` channel after commit. Cancellation scope does not branch on `run_type`. The worker first checks the durable cancel key and otherwise blocks on Pub/Sub; the matching message sets a Run-local `asyncio.Event`, stops the current Agent stream awaitable, persists `cancelled`, publishes the terminal `end` event, and clears the cancel key.
- Do not describe enqueueing as invoking the SSE endpoint. The worker produces events, while consumers independently open the SSE read endpoint.
- Rebuild the Compose worker after backend source changes because the worker image does not bind-mount the checkout.

## Persistence and ID Boundaries

- PostgreSQL is the source of truth for users, agents, conversations, messages, attachments, knowledge records, and Agent Run lifecycle state.
- The content schema now includes `ScriptProject`, `Episode`, `EpisodeOutline`, `EpisodeScript`, `Character`, `ScriptScene`, `ScriptLine`, and `StoryboardFrame`. At this stage these are table definitions only; no repository, HTTP API, or application binding exists yet.
- Outlines use Markdown text in `EpisodeOutline`. Screenplays use relational scene and semantic-line rows instead of whole-document JSON: `ScriptScene` stores scene structure and `ScriptLine` stores ordered action, character, parenthetical, dialogue, beat, and transition content.
- `ScriptLine.position` is the stable semantic order inside a scene, not a rendered line or page number. Physical wrapping and pagination must be derived from screenplay layout settings.
- `ScriptProject.workspace_key` is unique per user. Episode numbers are unique per project, character names are unique per project, scene positions and assigned scene numbers are unique per Episode script, semantic-line positions are unique per scene, and storyboard positions are unique per Episode.
- `Conversation.id` is the internal database primary key; `Conversation.thread_id` is the external conversation/runtime identifier.
- `Message.id` identifies the persisted triggering input. `AgentRun.trigger_message_id` lets the worker reconstruct input from only `run_id`.
- `AgentRun.run_type` is the execution-kind flag: `chat` for a main conversation Run and `subagent` for an internally delegated Run. `AgentRun.parent_run_id` remains a relationship field and may also link consecutive main conversation Runs.
- `AgentRun.agent_status` is the only lifecycle field.
- Current coarse run states are `pending`, `running`, `cancel_requested`, `completed`, `failed`, and `cancelled`.
- Redis/ARQ queue state is separate from PostgreSQL run state.
- ARQ job IDs use `run:{run_id}`. Redis Stream event keys use `run:events:{run_id}`. Cancellation keys use `run:cancel:{run_id}`; the cancellation Pub/Sub channel is `run:cancel`.
- Redis Stream IDs are event cursors, not Agent Run IDs and not durable business status.

## Agent Responsibilities

Agent design references, in priority order:

1. Refer first to `DeerFlow2`, the ByteDance open-source project.
2. Refer second to `Deep Agents` (`Deep Agent`), the official LangChain library.

### LeaderAgent

`LeaderAgent` is the public general-purpose orchestrator. It interprets the user
goal, selects direct execution or planning and delegation, coordinates tools and
internal agents, and returns the integrated final result. Keep its base prompt
domain-neutral; specialized behavior belongs in explicit tools, subagents, or
runtime context rather than hard-coded product assumptions.

Construct `LeaderAgent` from its concrete `LeaderAgentContext`.
`_create_middlewares(...)` owns middleware assembly, while `get_agent(...)` loads
context-configured MCP tools and `_build_agent(...)` assembles the LangChain
agent. It delegates bounded work to registered internal agents through
`SubAgentMiddleware`. Do not move persistence, queueing, or storage behavior into
the agent.

### SearchAgent

`SearchAgent` is an internal search-task orchestrator. It currently exposes knowledge and web search tools and returns evidence-oriented search guidance to its caller.

Keep search opt-in through `LeaderAgent`; do not add automatic pre-retrieval
middleware around every request. `SearchAgent` owns query planning, retrieval,
source comparison, and evidence synthesis. It must not take over the parent
agent's final user response.

### OutlineAgent

`OutlineAgent` is an internal structure-planning agent. It receives a bounded
outline task, produces the requested outline artifact, and returns it to the
parent. Keep it tool-light and context-driven; it must not become a second
top-level orchestrator or own persistence and transport behavior.

## Development Commands

Backend API:

```bash
uv sync
python server/main.py
```

ARQ worker:

```bash
uv run --no-sync arq server.worker.WorkerSettings
```

Database migration sample:

```bash
uv run --no-sync alembic upgrade head
uv run --no-sync alembic downgrade -1
```

Local infrastructure and worker through Compose:

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis minio worker
```

Targeted backend validation:

```bash
uv run --no-sync python -m compileall server/router server/service server/worker.py src/agents src/database/repositories src/storage
git diff --check
```

`pytest` is not currently declared as a project dependency. Do not report pytest validation unless it is installed and the tests were actually run. If `uv run` is blocked by local cache permissions, use the repository virtual environment directly, for example `.venv/bin/python -m compileall -q <paths>`.

## Contribution Rules

- Follow `CONTRIBUTING.md` for repository contribution workflow.
- Pull requests should include a concise Chinese summary and motivation unless the task explicitly requires another language.
- Link the issue or task ID when available.
- Include verification notes with the commands run and outcomes.

## Git Commit Rules

- Use Conventional Commits.
- Commit format: `<type>(<scope>): <subject>`.
- `type` must be one of `feat`, `fix`, `refactor`, `doc`, `test`, `chore`, `build`, or `ci`.
- `scope` is recommended and should use a concise module name such as `agent`, `thread`, `worker`, `auth`, or `deps`.
- Keep the Conventional Commit `type` and `scope` tokens in lowercase English; write the `subject` and optional commit body in Chinese.
- Keep the Chinese subject concise, recommended no more than 72 characters, and do not end it with punctuation.
- Examples: `feat(worker): 发布 Agent Run 流式事件`, `fix(auth): 修复令牌校验失败`, `doc(agent): 更新仓库代理指南`.
- Do not wrap commit messages, subjects, or scopes with `@` characters.
- Before every push, especially after committing from PowerShell, inspect all outgoing commit subjects and bodies for accidental `@` characters or wrappers. Do not push until malformed commit messages are corrected.
- Keep one commit focused on one coherent change.

## Working Rules

- Before changing implementation code, provide a concrete file-level
  modification plan and wait for the user's explicit approval.
- Preserve the existing directory structure, module boundaries, and public
  contracts whenever possible. If a task requires moving or deleting existing
  files, changing established ownership, or restructuring existing modules,
  stop first, explain why the structural change is necessary and what it
  affects, then wait for the user's explicit approval before proceeding.
- Prefer existing local patterns over new abstractions.
- Keep agent responsibilities narrow.
- Keep API/service orchestration outside agents.
- Keep database reads and writes in repositories.
- Keep ARQ enqueueing, raw Redis Stream I/O, Agent Run semantics, worker execution, and SSE consumption as distinct layers.
- Read project source and config files using UTF-8 unless another encoding is explicitly required.
- Preserve user changes in the working tree; never revert unrelated modifications.
- Add tests or compile checks for behavior changes with non-trivial blast radius.
- Worker jobs, long-running async loops, and infrastructure I/O boundaries must catch unexpected `Exception`s with `try/except`, call the existing `logger.exception(...)` with relevant IDs and context, and re-raise unless the use case explicitly defines recovery. Do not silently swallow errors or log normal `asyncio.CancelledError` as a failure.
- Treat current FIXME/TODO comments as incomplete work, not proof that the described behavior already exists.
- If implementing run-event delivery, wire and verify worker event production and backend SSE reading.
- Do not create an abstraction for logic used only once, and do not reserve flexibility or configurability for hypothetical future requirements.
- Do not split simple linear logic into a collection of tiny helpers. Extract a function only for clear reuse, side-effect isolation, or a substantial reduction in cognitive load.
- Follow the Stepdown Rule: place public, high-level methods first and move implementation details progressively downward. A reader should be able to follow the call relationships continuously from top to bottom.
- Prefer early returns and a clear main path. Avoid unnecessary nesting, indirect jumps, aggregation layers, priority systems, protocol interpreters, and multi-level fallbacks.
- Place constants and named values in the smallest reasonable scope. Use module-level constants for cross-function reuse, protocol identifiers, configuration constraints, or values that require centralized maintenance. Prefer function-local named values for error messages and rules used by only one function, even when repeated locally. Do not force values inline merely to reduce variable count, and do not promote local implementation details to global state.
- Names should express business intent. Comments should explain reasons, constraints, and non-obvious trade-offs rather than restating visible code behavior.
- Match the existing file style when modifying code. Do not opportunistically improve adjacent implementations. Unrelated code smells may be reported, but must not be changed without authorization.
- Remove unused imports, variables, functions, and branches introduced by the current change. Do not clean up unrelated dead code that existed before the change unless explicitly requested.
- For small status, progress, or summary requirements, read the source directly, select only the necessary fields, and return the smallest useful result. Do not reconstruct event streams or debugging views.
- If an implementation is clearly longer than the problem itself, or 200 lines could be expressed clearly in 50, stop extending it and simplify first.
- New functions and classes must have clear, concise Chinese docstrings. Important or critical locations should include additional comments explaining reasons, constraints, or trade-offs.
- Code should prioritize readability and have clear paragraph-like structure. Leave one blank line between semantically distinct blocks when it improves continuous reading.
- Before submitting, ask whether a senior engineer would consider the implementation over-designed, over-defensive, excessively nested, or overly fragmented. If so, simplify it first.
