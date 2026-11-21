import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { useAgentRun } from "@/pages/chat/hooks/useAgentRun";
import { useThread } from "@/pages/chat/hooks/useThread";
import type { AgentRunEndEvent, AgentRunStreamEvent } from "@/api/agent-run";
import type { ThreadDetailResponse } from "@/api/thread";

const mocks = vi.hoisted(() => ({
  createRun: vi.fn(),
  consumeStream: vi.fn(),
  cancelRun: vi.fn(),
  resumeRun: vi.fn(),
  cancelQueued: vi.fn(),
  steerQueued: vi.fn(),
}));
vi.mock("@/api/agent-run", () => ({
  createAgentRun: mocks.createRun,
  consumeAgentRunStream: mocks.consumeStream,
  buildAgentRunStreamUrl: vi.fn(),
  cancelAgentRun: mocks.cancelRun,
  resumeAgentRun: mocks.resumeRun,
  cancelQueuedAgentRunRequest: mocks.cancelQueued,
  steerQueuedAgentRunRequest: mocks.steerQueued,
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("keeps Run and AskHuman state while forwarding process and terminal events to the message consumer", async () => {
  const event = (type: string, fields: Record<string, unknown> = {}): AgentRunStreamEvent => ({
    id: type, scope: "agent_run", type, run_id: "run-1", thread_id: "thread-1",
    created_at: null, ...fields,
  });
  const status = event("status", { status: "running" });
  const tool = event("custom", { name: "agent_execute_event" });
  const interaction = event("interrupt", {
    name: "ask_user", created_by_run_id: "run-1",
    questions: [{ question_id: "choice", question: "Continue?", options: [{ label: "Yes", value: "yes" }] }],
  });
  const end = event("end", { status: "interrupted" }) as AgentRunEndEvent;
  mocks.createRun.mockResolvedValue({ run_id: "run-1", thread_id: "thread-1", status: "pending", stream_url: "/events" });
  mocks.consumeStream.mockImplementation(async (_url, _signal, callback) => {
    for (const item of [status, tool, interaction]) await callback(item);
    return end;
  });
  const { result } = renderHook(() => useAgentRun());
  const consumeMessage = vi.fn();
  await act(async () => {
    await result.current.createRun({ query: "hello", agentId: "leader", threadId: "thread-1", attachmentFileIds: [] });
    await result.current.consumeRunStream(new AbortController().signal, consumeMessage);
  });
  expect(consumeMessage.mock.calls.map(([item]) => item)).toEqual([status, tool, interaction, end]);
  expect(result.current.state.runStatus).toBe("interrupted");
  expect(result.current.state.streamUrl).toBeNull();
  expect(result.current.state.pendingInteraction).toMatchObject({ name: "ask_user", created_by_run_id: "run-1" });
});

it("routes ask_user to pending interaction while preserving preceding text without a duplicate tool card", async () => {
  const event = (type: string, fields: Record<string, unknown> = {}): AgentRunStreamEvent => ({
    id: type, scope: "agent_run", type, run_id: "run-1", thread_id: "thread-1",
    created_at: null, ...fields,
  });
  const questions = [{ question_id: "choice", question: "Continue?", options: [{ label: "Yes", value: "yes" }] }];
  const end = event("end", { status: "interrupted" }) as AgentRunEndEvent;
  mocks.createRun.mockResolvedValue({ run_id: "run-1", thread_id: "thread-1", status: "pending", stream_url: "/events" });
  mocks.consumeStream.mockImplementation(async (_url, _signal, callback) => {
    for (const item of [
      event("messages", { items: [{ stream_event: [{ type: "message_delta", message_id: "before", content_delta: "Please confirm." }] }] }),
      event("custom", { name: "agent_execute_event", event: { stream_data: { event: "tool-started", tool_call_id: "ask-1", tool_name: "ask_user", input: { questions } } } }),
      event("custom", { name: "agent_execute_event", event: { stream_data: { event: "tool-error", tool_call_id: "ask-1", message: "GraphInterrupt" } } }),
      event("interrupt", { name: "ask_user", created_by_run_id: "run-1", questions }),
    ]) await callback(item);
    return end;
  });
  const { result } = renderHook(() => ({ run: useAgentRun(), thread: useThread() }));
  await act(async () => {
    await result.current.run.createRun({ query: "hello", agentId: "leader", threadId: "thread-1", attachmentFileIds: [] });
    await result.current.run.consumeRunStream(new AbortController().signal, (item) => result.current.thread.applyRunMessageEvent(item, "run-1"));
  });
  expect(result.current.run.state.pendingInteraction).toEqual({ name: "ask_user", created_by_run_id: "run-1", questions });
  expect(result.current.run.state.runStatus).toBe("interrupted");
  expect(result.current.thread.state.messages).toHaveLength(1);
  expect(result.current.thread.state.messages[0].payload.event).toMatchObject({ content: "Please confirm." });
});

it("does not let a late cancel response overwrite an SSE terminal state", async () => {
  let resolveCancel!: (value: {
    run_id: string;
    thread_id: string;
    agent_id: string;
    status: string;
  }) => void;
  mocks.createRun.mockResolvedValue({
    run_id: "run-1",
    thread_id: "thread-1",
    status: "running",
    stream_url: "/events",
  });
  mocks.cancelRun.mockReturnValue(new Promise((resolve) => {
    resolveCancel = resolve;
  }));
  mocks.consumeStream.mockResolvedValue({
    id: "end",
    scope: "agent_run",
    type: "end",
    run_id: "run-1",
    thread_id: "thread-1",
    created_at: null,
    status: "completed",
  } satisfies AgentRunEndEvent);
  const { result } = renderHook(() => useAgentRun());

  await act(async () => {
    await result.current.createRun({
      query: "hello",
      agentId: "leader",
      threadId: "thread-1",
      attachmentFileIds: [],
    });
  });
  let cancellation!: Promise<void>;
  act(() => {
    cancellation = result.current.cancelCurrentRun();
  });
  await act(async () => {
    await result.current.consumeRunStream(
      new AbortController().signal,
      vi.fn(),
    );
  });
  expect(result.current.state.runStatus).toBe("completed");

  await act(async () => {
    resolveCancel({
      run_id: "run-1",
      thread_id: "thread-1",
      agent_id: "leader",
      status: "cancel_requested",
    });
    await cancellation;
  });
  expect(result.current.state.runStatus).toBe("completed");
  expect(result.current.state.streamUrl).toBeNull();
  expect(result.current.state.cancelling).toBe(false);
});

const start = "2026-10-18T00:00:00Z";
const detail: ThreadDetailResponse = {
  thread: {
    thread_id: "thread",
    title: "Thread",
    project_id: null,
    pinned: false,
    pinned_at: null,
    summary: null,
    agent_id: "LeaderAgent",
    metadata: {},
    created_at: start,
    updated_at: start,
  },
  messages: [],
  active_run: {
    run_id: "old-run",
    run_type: "chat",
    status: "running",
    started_at: start,
    finished_at: null,
    created_by_run_id: null,
    metadata: {},
  },
  pending_interaction: null,
  next_before_message_id: null,
};

it.each(["create", "resume"])(
  "clears the old Run's start when a new %s Run is accepted",
  async (kind) => {
    const { result } = renderHook(() => useAgentRun());
    act(() => result.current.restoreRunFromThread(detail));
    expect(result.current.state.startedAt).toBe(Date.parse(start));
    const response = {
      run_id: "new-run",
      status: "pending",
      stream_url: "/runs/new-run/events",
    };
    mocks.createRun.mockResolvedValue(response);
    mocks.resumeRun.mockResolvedValue(response);
    await act(async () => {
      if (kind === "create") {
        await result.current.createRun({
          query: "Hello",
          agentId: "LeaderAgent",
          threadId: "thread",
          attachmentFileIds: [],
        });
      } else {
        await result.current.resumeRun("old-run", {
          agent_id: "LeaderAgent",
          thread_id: "thread",
          request_metadata: {
            type: "resume",
            request_id: "request",
            resume: { answers: { question: "answer" } },
          },
        });
      }
    });
    expect(result.current.state.runId).toBe("new-run");
    expect(result.current.state.startedAt).toBeNull();
  },
);

it("preserves a known start when same-run metadata lacks it, but clears on another run", () => {
  const { result } = renderHook(() => useAgentRun());
  act(() => result.current.restoreRunFromThread(detail));
  act(() =>
    result.current.restoreRunFromThread({
      ...detail,
      active_run: { ...detail.active_run!, started_at: "invalid" },
    }),
  );
  expect(result.current.state.startedAt).toBe(Date.parse(start));
  act(() =>
    result.current.restoreRunFromThread({
      ...detail,
      active_run: {
        ...detail.active_run!,
        run_id: "other-run",
        started_at: null,
      },
    }),
  );
  expect(result.current.state.startedAt).toBeNull();
});

it.each(["enqueue", "steer"] as const)("keeps the active stream when a busy %s request is queued", async (policy) => {
  const { result } = renderHook(() => useAgentRun());
  act(() => result.current.restoreRunFromThread(detail));
  mocks.createRun.mockResolvedValue({ run_id: null, status: "queued", dispatch_policy: policy, request_id: "q", queue_position: 1, stream_url: null });
  await act(async () => {
    await result.current.createRun({ query: "next", agentId: "LeaderAgent", threadId: "thread", attachmentFileIds: [], dispatchPolicy: policy });
  });
  expect(result.current.state.runId).toBe("old-run");
  expect(result.current.state.runStatus).toBe("running");
  expect(mocks.createRun).toHaveBeenLastCalledWith("next", "LeaderAgent", "thread", [], undefined, policy);
});

it("restores, updates, cancels, and steers persisted queued requests", async () => {
  const queued = [
    { request_id: "req-1", dispatch_policy: "enqueue", queue_seq: 1, content: "Queued item", created_at: start },
  ];
  const { result } = renderHook(() => useAgentRun());
  act(() => result.current.restoreRunFromThread({ ...detail, queued_requests: queued }));
  expect(result.current.state.queuedRequests).toEqual(queued);

  act(() => result.current.setQueuedRequests((items) => items.filter((item) => item.request_id !== "req-1")));
  expect(result.current.state.queuedRequests).toEqual([]);

  mocks.steerQueued.mockResolvedValueOnce({
    run_id: null, thread_id: "thread", status: "queued", dispatch_policy: "steer",
    request_id: "req-1", queue_position: 1, steering_run_id: "old-run", stream_url: null,
  });
  await act(async () => {
    await result.current.steerQueuedRequest("req-1");
  });
  expect(result.current.state.runId).toBe("old-run");
  expect(result.current.state.runStatus).toBe("running");

  mocks.steerQueued.mockResolvedValueOnce({
    run_id: "promoted-run", thread_id: "thread", status: "pending",
    request_id: "req-1", stream_url: "/runs/promoted-run/events",
  });
  await act(async () => {
    await result.current.steerQueuedRequest("req-1");
  });
  expect(result.current.state.runId).toBe("promoted-run");
  expect(result.current.state.streamUrl).toBe("/runs/promoted-run/events");
});
