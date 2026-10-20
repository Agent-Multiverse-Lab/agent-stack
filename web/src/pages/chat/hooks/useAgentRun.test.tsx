import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

import { useAgentRun } from "./useAgentRun";
import type { ThreadDetailResponse } from "@/types/chat";

const mocks = vi.hoisted(() => ({ create: vi.fn(), resume: vi.fn() }));
vi.mock("@/api/agent", () => ({
  createAgentRun: mocks.create,
  resumeAgentRun: mocks.resume,
  buildAgentRunStreamUrl: (runId: string) => `/runs/${runId}/events`,
  cancelAgentRun: vi.fn(),
  consumeAgentRunStream: vi.fn(),
}));
afterEach(cleanup);

const start = "2026-10-18T00:00:00Z";
const detail: ThreadDetailResponse = {
  thread: { thread_id: "thread", title: "Thread", summary: null, agent_id: "LeaderAgent", metadata: {}, created_at: start, updated_at: start, last_message_at: null },
  messages: [],
  active_run: { run_id: "old-run", run_type: "chat", status: "running", started_at: start, finished_at: null, parent_run_id: null, metadata: {} },
  pending_interaction: null,
  next_before_message_id: null,
};

it.each(["create", "resume"])("clears the old Run's start when a new %s Run is accepted", async (kind) => {
  const { result } = renderHook(() => useAgentRun());
  act(() => result.current.restoreRunFromThread(detail));
  expect(result.current.state.startedAt).toBe(Date.parse(start));
  const response = { run_id: "new-run", status: "pending", stream_url: "/runs/new-run/events" };
  mocks.create.mockResolvedValue(response);
  mocks.resume.mockResolvedValue(response);
  await act(async () => {
    if (kind === "create") {
      await result.current.createRun({ query: "Hello", agentId: "LeaderAgent", threadId: "thread", attachmentFileIds: [] });
    } else {
      await result.current.resumeRun("old-run", { thread_id: "thread", thread_metadata: { request_id: "request", resume: { answers: { question: "answer" } } } });
    }
  });
  expect(result.current.state.runId).toBe("new-run");
  expect(result.current.state.startedAt).toBeNull();
});

it("preserves a known start when same-run metadata lacks it, but clears on another run", () => {
  const { result } = renderHook(() => useAgentRun());
  act(() => result.current.restoreRunFromThread(detail));
  act(() => result.current.restoreRunFromThread({ ...detail, active_run: { ...detail.active_run!, started_at: "invalid" } }));
  expect(result.current.state.startedAt).toBe(Date.parse(start));
  act(() => result.current.restoreRunFromThread({ ...detail, active_run: { ...detail.active_run!, run_id: "other-run", started_at: null } }));
  expect(result.current.state.startedAt).toBeNull();
});
