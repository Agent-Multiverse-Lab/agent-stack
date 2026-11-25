import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router";

import { ApiError } from "@/api/client";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import ChatPage from "./ChatPage";
import type { AgentRunStreamEvent } from "@/api/agent-run";
import type { ThreadDetailResponse } from "@/api/thread";

const mocks = vi.hoisted(() => ({
  getThreadDetail: vi.fn(),
  consume: vi.fn(),
  create: vi.fn(),
  resume: vi.fn(),
  cancel: vi.fn(),
  cancelQueued: vi.fn(),
  steerQueued: vi.fn(),
}));
vi.mock("@/i18n", () => ({ useTranslation: () => ({ t: (value: string) => value }) }));
vi.mock("@/context/ModelContext", () => ({
  useModel: () => ({ models: [], selectedModelId: "model", loading: false, selectModel: () => {} }),
}));
vi.mock("@/pages/chat/components/AgentMessageComposer", () => ({
  AgentMessageComposer: ({
    draft,
    setDraft,
    submit,
  }: {
    draft: string;
    setDraft: (value: string) => void;
    submit: (policy?: "enqueue" | "steer") => void;
  }) => (
    <div>
      <Input
        aria-label="Message"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
      <Button onClick={() => submit("enqueue")}>Queue</Button>
      <Button onClick={() => submit("steer")}>Steer now</Button>
    </div>
  ),
}));
vi.mock("@/pages/chat/components/AskUser", () => ({
  AskUser: ({ submit }: { submit: (answers: Record<string, string>) => void }) => (
    <Button onClick={() => submit({ database: "postgresql" })}>Answer question</Button>
  ),
}));
vi.mock("@/api/agent-run", () => ({
  consumeAgentRunStream: mocks.consume,
  createAgentRun: mocks.create,
  resumeAgentRun: mocks.resume,
  cancelAgentRun: mocks.cancel,
  cancelQueuedAgentRunRequest: mocks.cancelQueued,
  steerQueuedAgentRunRequest: mocks.steerQueued,
  buildAgentRunStreamUrl: (runId: string, threadId: string) => `/runs/${runId}/events?thread=${threadId}`,
}));
vi.mock("@/api/thread", () => ({
  getThreadDetail: mocks.getThreadDetail,
  createThread: vi.fn(),
  listChatAgents: vi.fn(),
}));
vi.mock("@/api/attachment", () => ({
  uploadChatAttachments: vi.fn(),
}));

const start = "2026-10-18T00:00:00Z";
const startMs = Date.parse(start);
const streams: { signal: AbortSignal; finish: () => void; emit: (event: AgentRunStreamEvent) => Promise<void> }[] = [];

function detail(id: string, startedAt: string | null = start): ThreadDetailResponse {
  return {
    thread: { thread_id: id, title: id, project_id: null, pinned: false, pinned_at: null, agent_id: "LeaderAgent", metadata: {}, created_at: start, updated_at: start },
    messages: [],
    active_run: { run_id: `run-${id}`, run_type: "chat", status: startedAt ? "running" : "pending", started_at: startedAt, finished_at: null, created_by_run_id: null, metadata: {} },
    pending_interaction: null,
    queued_requests: [],
    next_before_message_id: null,
  };
}

function event(extra: Partial<AgentRunStreamEvent>): AgentRunStreamEvent {
  return { id: "1-0", scope: "agent_run", type: "status", status: "running", run_id: "run-A", thread_id: "A", created_at: start, ...extra };
}

function Navigation() {
  const navigate = useNavigate();
  return <>{["A", "B"].map((id) => <Button key={id} onClick={() => navigate(`/c/${id}`)}>{id}</Button>)}</>;
}
function renderChat() {
  return render(<MemoryRouter initialEntries={["/c/A"]}><Navigation /><Routes><Route path="/c/:threadId" element={<ChatPage />} /></Routes></MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
  streams.length = 0;
  HTMLElement.prototype.scrollTo = vi.fn();
  mocks.getThreadDetail.mockImplementation(async (id: string) =>
    detail(id, id === "B" ? new Date(startMs + 1_000).toISOString() : start),
  );
  mocks.consume.mockImplementation((_url: string, signal: AbortSignal, emit: (event: AgentRunStreamEvent) => Promise<void>) => {
    return new Promise((resolve, reject) => {
      streams.push({ signal, emit, finish: () => resolve(event({ type: "end", status: "completed" })) });
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    });
  });
});
afterEach(cleanup);

it("submits resume answers with the current agent and unified request metadata", async () => {
  mocks.getThreadDetail.mockResolvedValue({
    ...detail("A"),
    active_run: null,
    pending_interaction: {
      name: "ask_user",
      created_by_run_id: "parent-run",
      questions: [{
        question_id: "database", question: "Database?",
        options: [{ label: "PostgreSQL", value: "postgresql" }],
      }],
    },
  });
  mocks.resume.mockResolvedValue({
    run_id: "resume-run", thread_id: "A", status: "pending",
    stream_url: "/runs/resume-run/events",
  });
  renderChat();
  fireEvent.click(await screen.findByRole("button", { name: "Answer question" }));
  await waitFor(() => expect(mocks.resume).toHaveBeenCalledWith("parent-run", {
    agent_id: "LeaderAgent",
    thread_id: "A",
    request_metadata: {
      type: "resume", request_id: expect.any(String),
      resume: { answers: { database: "postgresql" } },
    },
  }));
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(mocks.consume.mock.calls[0][0]).toBe("/runs/resume-run/events");
});

it("maintains active status after A to B to A while reconnecting the same Run", async () => {
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(screen.getByRole("status").textContent).toContain("Thinking");
  fireEvent.click(screen.getByRole("button", { name: "B" }));
  await waitFor(() => expect(streams).toHaveLength(2));
  expect(streams[0].signal.aborted).toBe(true);
  expect(screen.getByRole("status").textContent).toContain("Thinking");
  fireEvent.click(screen.getByRole("button", { name: "A" }));
  await waitFor(() => expect(streams).toHaveLength(3));
  expect(screen.getByRole("status").textContent).toContain("Thinking");
  expect(mocks.consume.mock.calls[2][0]).toBe(mocks.consume.mock.calls[0][0]);
  expect(mocks.create).not.toHaveBeenCalled();
  expect(mocks.resume).not.toHaveBeenCalled();
  expect(mocks.cancel).not.toHaveBeenCalled();
});

it("preserves active status as process activity appears and disappears", async () => {
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  await act(() => streams[0].emit(event({ type: "custom", name: "agent_state", agent_state: { agent_todo: [{ content: "Work", status: "in_progress" }] } })));
  expect(screen.getByText("Work")).toBeTruthy();
  expect(screen.getByRole("status").textContent).toMatch(/Thinking|Working/);
  await act(() => streams[0].emit(event({ type: "custom", name: "agent_state", agent_state: { agent_todo: [] } })));
  expect(screen.queryByText("Work")).toBeNull();
  expect(screen.getByRole("status").textContent).toMatch(/Thinking|Working/);
});

it.each([null, "invalid"])("hydrates active status (%s) from running events", async (startedAt) => {
  mocks.getThreadDetail.mockResolvedValueOnce(detail("A", startedAt));
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(screen.getByRole("status").textContent).toContain("Thinking");
  await act(() => streams[0].emit(event({ created_at: "invalid" })));
  expect(screen.getByRole("status").textContent).toContain("Thinking");
  await act(() => streams[0].emit(event({ created_at: new Date(startMs + 300).toISOString() })));
  expect(screen.getByRole("status").textContent).toContain("Thinking");
  fireEvent.click(screen.getByRole("button", { name: "B" }));
  await waitFor(() => expect(streams).toHaveLength(2));
  fireEvent.click(screen.getByRole("button", { name: "A" }));
  await waitFor(() => expect(streams).toHaveLength(3));
  expect(screen.getByRole("status").textContent).toContain("Thinking");
});

it("removes Thinking status indicator after a terminal event", async () => {
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(screen.getByRole("status").textContent).toContain("Thinking");
  mocks.getThreadDetail.mockResolvedValue({ ...detail("A"), active_run: null });
  await act(() => streams[0].finish());
  await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
});

it("persists busy enqueue submissions immediately, supports reload recovery, optimistic delete, steer, and post-end handover", async () => {
  const queuedDrop = { request_id: "req-drop", dispatch_policy: "enqueue", queue_seq: 1, content: "Drop me", created_at: start };
  const queuedNext = { request_id: "req-next", dispatch_policy: "enqueue", queue_seq: 2, content: "Next question", created_at: start };

  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));

  // 1. 运行中发起 enqueue 立即调 POST /api/agent/runs 并刷新等待区，同时不中断当前流
  mocks.create.mockResolvedValueOnce({
    run_id: null, thread_id: "A", status: "queued", dispatch_policy: "enqueue",
    request_id: "req-drop", queue_position: 1, steering_run_id: null, stream_url: null,
  });
  mocks.getThreadDetail.mockResolvedValueOnce({ ...detail("A"), queued_requests: [queuedDrop] });

  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Drop me" } });
  fireEvent.click(screen.getByRole("button", { name: "Queue" }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledWith("Drop me", "LeaderAgent", "A", [], "model", "enqueue"));
  expect(await screen.findByText("Drop me")).toBeTruthy();
  expect(streams).toHaveLength(1);
  expect(streams[0].signal.aborted).toBe(false);

  // 2. 点击 Remove 乐观删除并调用 DELETE；失败时回滚并显示错误
  let rejectDelete!: (err: unknown) => void;
  mocks.cancelQueued.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectDelete = reject; }));
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(screen.queryByText("Drop me")).toBeNull();
  await act(async () => rejectDelete(new Error("Delete failed")));
  expect(screen.getByText("Drop me")).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toBe("Delete failed");

  // 3. 删除成功后保持清空
  mocks.cancelQueued.mockResolvedValueOnce({ request_id: "req-drop", status: "cancelled" });
  mocks.getThreadDetail.mockResolvedValueOnce({ ...detail("A"), queued_requests: [] });
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  await waitFor(() => expect(mocks.cancelQueued).toHaveBeenCalledTimes(2));
  expect(screen.queryByText("Drop me")).toBeNull();

  // 4. 切走会话再切回可从 ThreadDetailResponse.queued_requests 恢复，并支持原地升级 steer
  mocks.create.mockResolvedValueOnce({
    run_id: null, thread_id: "A", status: "queued", dispatch_policy: "enqueue",
    request_id: "req-next", queue_position: 1, steering_run_id: null, stream_url: null,
  });
  mocks.getThreadDetail.mockResolvedValueOnce({ ...detail("A"), queued_requests: [queuedNext] });
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Next question" } });
  fireEvent.click(screen.getByRole("button", { name: "Queue" }));
  expect(await screen.findByText("Next question")).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "B" }));
  await waitFor(() => expect(streams).toHaveLength(2));
  mocks.getThreadDetail.mockResolvedValueOnce({ ...detail("A"), queued_requests: [queuedNext] });
  fireEvent.click(screen.getByRole("button", { name: "A" }));
  expect(await screen.findByText("Next question")).toBeTruthy();
  await waitFor(() => expect(streams).toHaveLength(3));

  mocks.steerQueued.mockResolvedValueOnce({
    run_id: null, thread_id: "A", status: "queued", dispatch_policy: "steer",
    request_id: "req-next", queue_position: 1, steering_run_id: "run-A", stream_url: null,
  });
  mocks.getThreadDetail.mockResolvedValueOnce({
    ...detail("A"),
    queued_requests: [{ ...queuedNext, dispatch_policy: "steer" }],
  });
  fireEvent.click(screen.getByRole("button", { name: "Steer" }));
  await waitFor(() => expect(mocks.steerQueued).toHaveBeenCalledWith("req-next"));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Steer" })).toBeNull());

  // 5. 收到 end 后首次详情若短暂无 active_run，通过短退避重查接入 Worker 晋升的新 Run
  mocks.getThreadDetail
    .mockResolvedValueOnce({ ...detail("A"), active_run: null, queued_requests: [{ ...queuedNext, dispatch_policy: "steer" }] })
    .mockResolvedValueOnce({
      ...detail("A"),
      active_run: { ...detail("A").active_run!, run_id: "next-run" },
      queued_requests: [],
    });
  await act(async () => streams[2].finish());
  await waitFor(() => expect(streams).toHaveLength(4));
  expect(mocks.consume.mock.calls[3][0]).toBe("/runs/next-run/events?thread=A");
  expect(screen.queryByText("Next question")).toBeNull();
});

it("handles 409 already-promoted conflicts, idle Run now, and non-polling failed termination correctly", async () => {
  const queuedItem = { request_id: "req-1", dispatch_policy: "enqueue", queue_seq: 1, content: "Manual run", created_at: start };
  mocks.getThreadDetail.mockResolvedValueOnce({ ...detail("A"), queued_requests: [queuedItem] });

  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(await screen.findByText("Manual run")).toBeTruthy();

  // Remove 并发遇 409 run_id 时刷新并切流到新 active_run
  mocks.cancelQueued.mockRejectedValueOnce(new ApiError("请求已开始执行", 409, { detail: "请求已开始执行", run_id: "promoted-1" }));
  mocks.getThreadDetail.mockResolvedValueOnce({
    ...detail("A"),
    active_run: { ...detail("A").active_run!, run_id: "promoted-1" },
    queued_requests: [],
  });
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  await waitFor(() => expect(streams).toHaveLength(2));
  expect(mocks.consume.mock.calls[1][0]).toBe("/runs/promoted-1/events?thread=A");

  // 验证 failed 终态：不自动轮询，保留等待区与 Run now，点击后发起 200 新流
  cleanup();
  streams.length = 0;
  const consumeCallsBefore = mocks.consume.mock.calls.length;
  mocks.getThreadDetail.mockReset();
  mocks.getThreadDetail
    .mockResolvedValueOnce({
      ...detail("A"),
      active_run: { ...detail("A").active_run!, run_id: "run-fail" },
      queued_requests: [queuedItem],
    })
    .mockResolvedValueOnce({ ...detail("A"), active_run: null, queued_requests: [queuedItem] })
    .mockResolvedValueOnce({
      ...detail("A"),
      active_run: { ...detail("A").active_run!, run_id: "manual-run" },
      queued_requests: [],
    });
  mocks.consume.mockImplementationOnce((_url: string, signal: AbortSignal) =>
    new Promise((resolve, reject) => {
      streams.push({ signal, emit: async () => {}, finish: () => resolve(event({ type: "end", status: "failed", error: "Boom" })) });
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }),
  );

  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  await act(async () => streams[0].finish());
  const runNowButton = await screen.findByRole("button", { name: "Run now" });
  expect(screen.getByRole("alert").textContent).toBe("Boom");
  expect(mocks.getThreadDetail).toHaveBeenCalledTimes(2);

  mocks.consume.mockImplementationOnce((_url: string, signal: AbortSignal, emit: (ev: AgentRunStreamEvent) => Promise<void>) =>
    new Promise((resolve, reject) => {
      streams.push({ signal, emit, finish: () => resolve(event({ type: "end", status: "completed" })) });
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }),
  );
  mocks.steerQueued.mockResolvedValueOnce({
    run_id: "manual-run", thread_id: "A", status: "pending",
    request_id: "req-1", stream_url: "/runs/manual-run/events?thread=A",
  });
  fireEvent.click(runNowButton);
  await waitFor(() => expect(mocks.steerQueued).toHaveBeenCalledWith("req-1"));
  await waitFor(() => expect(streams).toHaveLength(2));
  expect(mocks.consume.mock.calls[consumeCallsBefore + 1][0]).toBe("/runs/manual-run/events?thread=A");
});
