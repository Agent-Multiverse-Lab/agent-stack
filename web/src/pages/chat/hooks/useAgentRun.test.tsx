import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { useAgentRun } from "@/pages/chat/hooks/useAgentRun";
import { useChat } from "@/pages/chat/hooks/useChat";
import type { AgentRunEndEvent, AgentRunStreamEvent } from "@/types/chat";

const mocks = vi.hoisted(() => ({ createRun: vi.fn(), consumeStream: vi.fn() }));
vi.mock("@/api/agent", () => ({
  createAgentRun: mocks.createRun,
  consumeAgentRunStream: mocks.consumeStream,
  buildAgentRunStreamUrl: vi.fn(),
  cancelAgentRun: vi.fn(),
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
  const { result } = renderHook(() => ({ run: useAgentRun(), chat: useChat() }));
  await act(async () => {
    await result.current.run.createRun({ query: "hello", agentId: "leader", threadId: "thread-1", attachmentFileIds: [] });
    await result.current.run.consumeRunStream(new AbortController().signal, (item) => result.current.chat.applyRunMessageEvent(item, "run-1"));
  });
  expect(result.current.run.state.pendingInteraction).toEqual({ name: "ask_user", parent_run_id: "run-1", questions });
  expect(result.current.run.state.runStatus).toBe("interrupted");
  expect(result.current.chat.state.messages).toHaveLength(1);
  expect(result.current.chat.state.messages[0].payload.event).toMatchObject({ content: "Please confirm." });
  expect(result.current.chat.state.error).toBe("");
});
