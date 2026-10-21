import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { useAgentRun } from "@/pages/chat/hooks/useAgentRun";
import { useThread } from "@/pages/chat/hooks/useThread";
import type { AgentRunEndEvent, AgentRunStreamEvent } from "@/api/agent-run";

const mocks = vi.hoisted(() => ({
  createRun: vi.fn(),
  consumeStream: vi.fn(),
  cancelRun: vi.fn(),
}));
vi.mock("@/api/agent-run", () => ({
  createAgentRun: mocks.createRun,
  consumeAgentRunStream: mocks.consumeStream,
  buildAgentRunStreamUrl: vi.fn(),
  cancelAgentRun: mocks.cancelRun,
  resumeAgentRun: vi.fn(),
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
    name: "ask_user", parent_run_id: "run-1",
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
  expect(result.current.state.pendingInteraction).toMatchObject({ name: "ask_user", parent_run_id: "run-1" });
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
      event("interrupt", { name: "ask_user", parent_run_id: "run-1", questions }),
    ]) await callback(item);
    return end;
  });
  const { result } = renderHook(() => ({ run: useAgentRun(), thread: useThread() }));
  await act(async () => {
    await result.current.run.createRun({ query: "hello", agentId: "leader", threadId: "thread-1", attachmentFileIds: [] });
    await result.current.run.consumeRunStream(new AbortController().signal, (item) => result.current.thread.applyRunMessageEvent(item, "run-1"));
  });
  expect(result.current.run.state.pendingInteraction).toEqual({ name: "ask_user", parent_run_id: "run-1", questions });
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
