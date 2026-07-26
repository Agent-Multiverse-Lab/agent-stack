# Repository Agent Guide

This file is the single source of repository guidance for Claude/Codex-style coding agents. `CLAUDE.md` imports this file directly, so update `AGENTS.md` whenever architecture or workflow guidance changes.

## Current Project Shape

`multi-agent-s2c` is a script-driven visual creation system. The backend is a FastAPI service built around LangChain/LangGraph agents, SQLAlchemy repositories, PostgreSQL, Redis/ARQ background work, and MinIO-backed uploads. The frontend is a React + TypeScript + Vite application under `web/`.

Current top-level layout:

- `server/`: FastAPI application, auth middleware, routers, services, lifespan startup, and the ARQ worker entrypoint.
- `src/agents/`: shared agent primitives, the agent manager, `LeaderAgent`, internal subagents, middleware, model helpers, and sandbox backends.
- `src/configs/`: Pydantic settings loaded from environment variables and `.env`.
- `src/database/`: SQLAlchemy models, PostgreSQL lifecycle/session helpers, and repositories.
- `src/knowledge/`: the unified document-processing flow, knowledge providers, and Milvus integration.
- `src/storage/`: MinIO storage in `minio.py` and Redis/ARQ connection helpers under `redis/`.
- `web/`: React client and its frontend-specific `AGENTS.md`.
- `test/`: lightweight backend helper tests and manual smoke scripts.
- `tests/`: tracked backend unit tests, including the Knowledge Flow contract.
- `sandbox_server/`, `docker/`, and `scripts/`: local runtime support, Compose services, and helper scripts.

The public top-level agent is `LeaderAgent` in `src/agents/leaderagent/`. Internal subagents are `SearchAgent`, `OutlineAgent`, `CharacterAgent`, and `ScenarioAgent` under `src/agents/subagents/`.

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
- Agent Run creation and SSE exposure live in `server/router/agent_router.py`. Run orchestration helpers, including the shared `request_cancel_agent_run(...)` path for top-level and child Runs, live in `server/service/agent_run_service.py`.
- `server/service/arq_queue_servcie.py` owns ARQ pool access, direct Redis Stream `XADD`/`XREAD` operations, and Agent Run cancellation-key `SET`/`EXISTS`/`DELETE` operations. Keep the existing filename spelling unless a dedicated rename is requested.
- `server/service/subagent_service.py` owns child conversation/message/Run persistence, parent-child ownership checks, and enqueue handoff. It does not own generic Agent Run cancellation; `SubAgentMiddleware` verifies parent-child scope there before calling `request_cancel_agent_run(...)`.
- `src/storage/redis/redis_manger.py` owns only Redis/ARQ connection creation, lazy shared-client initialization, and close behavior. It must not own Agent Run semantics.
- `server/worker.py` is the independent ARQ worker entrypoint and the single startup owner for database bootstrap. Worker startup initializes PostgreSQL, creates missing model tables with `checkfirst=True`, applies the non-destructive `AgentRun.run_type` column/index patch for existing databases, and inserts only missing public/internal Agent registration rows before accepting jobs. It must not drop tables, seed users or conversations, or overwrite existing Agent rows. Worker shutdown only disposes its own PostgreSQL resources; it does not reuse the FastAPI lifespan.
- Database access belongs in `src/database/repositories/`. Do not put persistence queries inside agents.

## Knowledge Flow

- `src/knowledge/flow/pipeline.py` owns the document-processing order:
  async Parser execution, explicit Chunker selection, and the final Chunk list.
- `src/knowledge/flow/parser/parser.py` is the only public document Parser. It
  routes by normalized file suffix; it must not infer formats from document
  content or send one input through multiple format parsers.
- OCR implementations live under `src/knowledge/flow/extractor/` and are called
  only by PDF or image parsing paths. Extractors do not select file types,
  chunk content, or write knowledge records.
- Chunking lives under `src/knowledge/flow/chunker/`. `TokenChunker` uses a
  fixed token step. `TitleChunker` explicitly selects `group` or `hierarchy`;
  do not restore content-based `general` / `book` / `laws` / `paper` profile
  inference.
- Parser, Extractor, and Chunker share only the document block and chunk
  structures from `src/knowledge/flow/types.py`. Vectorization, persistence,
  object storage, and queue behavior remain outside the Flow.

## Agent Runtime Context

Agent runtime configuration has exactly three sources:

1. The context class defined by the concrete top-level agent or subagent, including its schema and defaults.
2. Values supplied by the frontend for the current run.
3. Values loaded by the backend from the database for the current agent or run.

Frontend-supplied and database-loaded values must be merged into the concrete agent context before execution. The resulting context is the only source of runtime configuration for agents, subagents, middleware, tools, and backends. Do not introduce parallel runtime configuration through module globals, middleware-local defaults, ad hoc keyword arguments, or direct database/config reads; resolve those values first and bind them to the context.

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
- Cancellation is two-phase: `request_cancel_agent_run(...)` first persists `cancel_requested`, then writes `run:cancel:{run_id}`. Cancelling a `run_type="chat"` Run also marks all of that user's active direct `run_type="subagent"` Runs in the same transaction and signals each one after commit; cancelling a subagent Run affects only that child. The worker stops consuming each Agent stream, persists `cancelled`, publishes the terminal `end` event, and clears the cancel key.
- After run creation, the frontend navigates to the independent `/workspace/{run_id}` route, immediately shows the local optimistic human message, then opens the returned `stream_url` with an authenticated `fetch` stream.
- `web/src/api/agent.ts` owns the SSE transport/parser, `useAgentRunStream` maps run events into UI state, and `WorkspaceView` only renders the optimistic input, streaming assistant content, status, and transport errors.
- Do not describe enqueueing as invoking the SSE endpoint. The worker produces events and the frontend independently opens the SSE read endpoint.
- Rebuild the Compose worker after backend source changes because the worker image does not bind-mount the checkout.

## Persistence and ID Boundaries

- PostgreSQL is the source of truth for users, agents, conversations, messages, attachments, knowledge records, and Agent Run lifecycle state.
- The content schema now includes `ScriptProject`, `Episode`, `EpisodeOutline`, `EpisodeScript`, `Character`, `ScriptScene`, `ScriptLine`, and `StoryboardFrame`. At this stage these are table definitions only; no repository, HTTP API, or frontend persistence binding exists yet.
- Outlines use Markdown text in `EpisodeOutline`. Screenplays use relational scene and semantic-line rows instead of whole-document JSON: `ScriptScene` stores scene structure and `ScriptLine` stores ordered action, character, parenthetical, dialogue, beat, and transition content.
- `ScriptLine.position` is the stable semantic order inside a scene, not a rendered line or page number. Physical wrapping and pagination must be derived from screenplay layout settings.
- `ScriptProject.workspace_key` is unique per user. Episode numbers are unique per project, character names are unique per project, scene positions and assigned scene numbers are unique per Episode script, semantic-line positions are unique per scene, and storyboard positions are unique per Episode.
- `Conversation.id` is the internal database primary key; `Conversation.thread_id` is the external conversation/runtime identifier.
- `Message.id` identifies the persisted triggering input. `AgentRun.trigger_message_id` lets the worker reconstruct input from only `run_id`.
- `AgentRun.run_type` is the execution-kind flag: `chat` for a main conversation Run and `subagent` for an internally delegated Run. `AgentRun.parent_run_id` remains a relationship field and may also link consecutive main conversation Runs.
- `AgentRun.agent_status` is the current lifecycle field. The older `AgentRun.status` field is temporarily mirrored for compatibility and should not become a second source of truth.
- Current coarse run states are `pending`, `running`, `cancel_requested`, `completed`, `failed`, and `cancelled`.
- Redis/ARQ queue state is separate from PostgreSQL run state.
- ARQ job IDs use `run:{run_id}`. Redis Stream event keys use `run:events:{run_id}`. Cancellation keys use `run:cancel:{run_id}`.
- Redis Stream IDs are event cursors, not Agent Run IDs and not durable business status.

## Agent Responsibilities

Agent design references, in priority order:

1. Refer first to `DeerFlow2`, the ByteDance open-source project.
2. Refer second to `Deep Agents` (`Deep Agent`), the official LangChain library.

### LeaderAgent

`LeaderAgent` is the public script and storyboard creation orchestrator. Its context prompt asks for production-ready story concepts, character relationships, dramatic structure, scenes, camera language, pacing, dialogue, storyboard plans, and sound/music guidance.

It currently has no direct tools. It delegates retrieval and fact-checking to a separately persisted and queued `SearchAgent` Run through `SubAgentMiddleware`, and uses retry middleware around model execution. The middleware provides `task`, `subagent_start`, `subagent_status`, `subagent_cancel`, and `subagent_await`.

### SearchAgent

`SearchAgent` is an internal search-task orchestrator. It currently exposes knowledge and web search tools, uses `SearchToolMiddleware`, and returns evidence-oriented search guidance to its caller.

Keep search opt-in through `LeaderAgent`; do not add automatic pre-retrieval middleware around every request. `SearchAgent` should not generate the final script or storyboard.

### LayoutAgent

`LayoutAgent` is responsible for composition analysis, visual hierarchy, and generation-ready prompt drafting. It should not call image-generation APIs unless that responsibility is explicitly changed.

## Frontend Architecture

For frontend-specific conventions, follow `web/AGENTS.md`.

Current frontend stack:

- React 19, TypeScript, and Vite 7.
- Radix UI primitives and Tailwind CSS 4.
- Zustand 5 and `react-router-dom` 7.
- `motion/react` for component motion and GSAP for the authentication landing choreography.

Current frontend boundaries:

- `web/src/App.tsx` owns route guards and router setup.
- Any newly introduced UI container with its own visual boundary, layout
  responsibility, state, or interaction must be implemented as a dedicated
  React component and imported by its parent. Do not leave substantial
  container markup inline in a page or list loop, even when it currently has
  only one call site; see `web/AGENTS.md` for the detailed component-boundary
  principle.
- Authenticated routes live under `/app/:sectionId` and `/app/:sectionId/:pageId`. `/` and `/app` redirect to `/app/script`.
- `AuthLanding` owns the mounted login/register experience for `/login` and `/register`. The standalone `LoginView.tsx` and `RegisterView.tsx` files are not the current routed UI.
- `web/src/pages/AppView/AppView.tsx` owns the authenticated studio shell and page-level state. Tab/page components live under `web/src/pages/AppView/components/`.
- `web/src/api/index.ts` currently provides only the shared JSON request primitive plus `get` and `post` helpers.
- `web/src/api/auth.ts` owns email auth calls. `web/src/api/agent.ts` owns thread creation, Agent Run creation, and authenticated Agent Run SSE transport/parsing.
- `useAuthStore` is the active persisted shared auth store. The former `web/src/store/chat.ts`, `web/src/hooks/useChat.ts`, and `web/src/api/library.ts` paths have been deleted; do not reference or restore them unless a feature explicitly requires it.
- `NewPromptPage` submits through `AppView`, creates a new thread and run, then navigates to the standalone `WorkspaceView` route at `/workspace/{run_id}`.
- `WorkspaceView` is not embedded in the `AppView` shell. It owns its full-screen resource rail, central canvas, Agent configuration rail, and floating chat panel. `insertOptimisticHumanMessage(...)` adds the submitted user bubble to router state before navigation.
- Script creation, imports, and script cards in Recent or the script list all open in the same standalone `WorkspaceView`; keep screenplay work on this shared page.
- The frontend must not ship seeded scripts, storyboard projects, community entries, update notices, preset prompts, preset images, or mock Agent output. Studio collections start empty until real API or user-created data is available.
- `useAgentRunStream` consumes run events and projects model text/status into `WorkspaceView`; the optimistic human message remains local UI state and is not an SSE event.

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

Local infrastructure and worker through Compose:

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis minio worker
```

Frontend:

```bash
cd web
npm install
npm run dev
npm run build
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
- For UI changes in `web/`, include screenshots or video.
- Include verification notes with the commands run and outcomes.

## Git Commit Rules

- Use Conventional Commits.
- Commit format: `<type>(<scope>): <subject>`.
- `type` must be one of `feat`, `fix`, `refactor`, `doc`, `test`, `chore`, `build`, or `ci`.
- `scope` is recommended and should use a concise module name such as `agent`, `thread`, `worker`, `web`, `auth`, or `deps`.
- Keep the Conventional Commit `type` and `scope` tokens in lowercase English; write the `subject` and optional commit body in Chinese.
- Keep the Chinese subject concise, recommended no more than 72 characters, and do not end it with punctuation.
- Examples: `feat(worker): 发布 Agent Run 流式事件`, `fix(web): 修复任务创建后未订阅事件流`, `doc(agent): 更新仓库代理指南`.
- Do not wrap commit messages, subjects, or scopes with `@` characters.
- Before every push, especially after committing from PowerShell, inspect all outgoing commit subjects and bodies for accidental `@` characters or wrappers. Do not push until malformed commit messages are corrected.
- Keep one commit focused on one coherent change.

## Working Rules

- Prefer existing local patterns over new abstractions.
- Keep agent responsibilities narrow.
- Keep API/service orchestration outside agents.
- Keep database reads and writes in repositories.
- Keep ARQ enqueueing, raw Redis Stream I/O, Agent Run semantics, worker execution, and frontend SSE consumption as distinct layers.
- Read project source and config files using UTF-8 unless another encoding is explicitly required.
- Preserve user changes in the working tree; never revert unrelated modifications.
- Add tests or compile checks for behavior changes with non-trivial blast radius.
- Treat current FIXME/TODO comments as incomplete work, not proof that the described behavior already exists.
- If implementing run-event delivery, wire and verify all three boundaries: worker event production, backend SSE reading, and frontend authenticated stream consumption.
