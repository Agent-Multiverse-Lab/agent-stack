import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { useAgentRun } from "@/pages/chat/hooks/useAgentRun";
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
