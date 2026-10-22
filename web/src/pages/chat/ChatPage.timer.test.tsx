import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router";

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
}));
vi.mock("@/i18n", () => ({ useTranslation: () => ({ t: (value: string) => value }) }));
vi.mock("@/context/ModelContext", () => ({
  useModel: () => ({ models: [], selectedModelId: "model", loading: false, selectModel: () => {} }),
}));
vi.mock("@/pages/chat/components/AgentMessageComposer", () => ({ AgentMessageComposer: () => null }));
vi.mock("@/pages/chat/components/ChatMessage", () => ({ ChatMessage: () => <span>Activity</span> }));
vi.mock("@/pages/chat/components/AskUser", () => ({ AskUser: () => null }));
vi.mock("@/api/agent-run", () => ({
  consumeAgentRunStream: mocks.consume,
  createAgentRun: mocks.create,
  resumeAgentRun: mocks.resume,
  cancelAgentRun: mocks.cancel,
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
    thread: { thread_id: id, title: id, summary: null, agent_id: "LeaderAgent", metadata: {}, created_at: start, updated_at: start },
    messages: [],
    active_run: { run_id: `run-${id}`, run_type: "chat", status: startedAt ? "running" : "pending", started_at: startedAt, finished_at: null, parent_run_id: null, metadata: {} },
    pending_interaction: null,
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
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(startMs + 12_300);
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
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

it("restores elapsed time after A to B to A while reconnecting the same Run", async () => {
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(screen.getByText("12.3s")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "B" }));
  await waitFor(() => expect(streams).toHaveLength(2));
  expect(streams[0].signal.aborted).toBe(true);
  expect(screen.getByText("11.3s")).toBeTruthy();
  vi.setSystemTime(startMs + 17_300);
  fireEvent.click(screen.getByRole("button", { name: "A" }));
  await waitFor(() => expect(streams).toHaveLength(3));
  expect(screen.getByText("17.3s")).toBeTruthy();
  expect(mocks.consume.mock.calls[2][0]).toBe(mocks.consume.mock.calls[0][0]);
  expect(mocks.create).not.toHaveBeenCalled();
  expect(mocks.resume).not.toHaveBeenCalled();
  expect(mocks.cancel).not.toHaveBeenCalled();
});

it("preserves elapsed time when activity moves Thinking into and out of a tool row", async () => {
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  vi.setSystemTime(startMs + 18_300);
  await act(() => streams[0].emit(event({ type: "custom", name: "agent_state", agent_state: { agent_todo: [{ content: "Work", status: "in_progress" }] } })));
  expect(screen.getByText("Activity")).toBeTruthy();
  expect(screen.getByText("18.3s")).toBeTruthy();
  vi.setSystemTime(startMs + 22_300);
  await act(() => streams[0].emit(event({ type: "custom", name: "agent_state", agent_state: { agent_todo: [] } })));
  expect(screen.queryByText("Activity")).toBeNull();
  expect(screen.getByText("22.3s")).toBeTruthy();
});

it.each([null, "invalid"])("hydrates a missing/invalid start (%s) from running events and prefers persisted starts on return", async (startedAt) => {
  mocks.getThreadDetail.mockResolvedValueOnce(detail("A", startedAt));
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(screen.getByRole("status").textContent).toBe("Thinking");
  await act(() => streams[0].emit(event({ created_at: "invalid" })));
  expect(screen.getByRole("status").textContent).toBe("Thinking");
  await act(() => streams[0].emit(event({ created_at: new Date(startMs + 300).toISOString() })));
  expect(screen.getByText("12.0s")).toBeTruthy();
  await act(() => streams[0].emit(event({ created_at: new Date(startMs + 10_000).toISOString() })));
  expect(screen.getByText("12.0s")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "B" }));
  await waitFor(() => expect(streams).toHaveLength(2));
  fireEvent.click(screen.getByRole("button", { name: "A" }));
  await waitFor(() => expect(streams).toHaveLength(3));
  expect(screen.getByText("12.3s")).toBeTruthy();
  await act(() => streams[2].emit(event({ created_at: new Date(startMs + 300).toISOString() })));
  expect(screen.getByText("12.3s")).toBeTruthy();
});


it("removes Thinking and its interval after a terminal event", async () => {
  const clearInterval = vi.spyOn(window, "clearInterval");
  renderChat();
  await waitFor(() => expect(streams).toHaveLength(1));
  expect(screen.getByText("12.3s")).toBeTruthy();
  mocks.getThreadDetail.mockResolvedValue({ ...detail("A"), active_run: null });
  await act(() => streams[0].finish());
  await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  expect(clearInterval).toHaveBeenCalled();
  clearInterval.mockRestore();
});
