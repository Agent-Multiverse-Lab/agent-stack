import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import { ModelProvider } from "@/context/ModelContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ChatPage from "@/pages/chat/ChatPage";
import type { ChatModelOption } from "@/types/model";

const mocks = vi.hoisted(() => ({
  listModels: vi.fn(),
  getThreadDetail: vi.fn(),
  createThread: vi.fn(),
  listChatAgents: vi.fn(),
  createRun: vi.fn(),
}));

vi.mock("@/context/AuthContext", () => ({ useAuth: () => ({ accessToken: "token" }) }));
vi.mock("@/api/model", () => ({ listModels: mocks.listModels }));
vi.mock("@/api/agent", () => ({
  createThread: mocks.createThread,
  getThreadDetail: mocks.getThreadDetail,
  listChatAgents: mocks.listChatAgents,
  uploadChatAttachments: vi.fn(),
}));
vi.mock("@/i18n", () => ({ useTranslation: () => ({ t: (value: string) => value }) }));
vi.mock("@/pages/chat/hooks/useAgentRun", () => ({
  useAgentRun: () => ({
    state: { pendingInteraction: null, cancelling: false, resuming: false },
    getState: () => ({ pendingInteraction: null }),
    isActive: () => false,
    clearRun: () => {},
    restoreRunFromThread: () => null,
    createRun: mocks.createRun,
  }),
}));
vi.mock("@/pages/chat/components/ChatMessage", () => ({ ChatMessage: () => null }));
vi.mock("@/pages/chat/components/AgentMessageComposer", () => ({
  AgentMessageComposer: (props: {
    draft: string;
    setDraft: (draft: string) => void;
    modelId: string;
    models: ChatModelOption[];
    selectModel: (model: string) => void;
    submit: () => void;
    disabled: boolean;
  }) => (
    <div>
      <Input aria-label="Question" value={props.draft} onChange={(event) => props.setDraft(event.target.value)} />
      <output aria-label="Model">{props.modelId}</output>
      {props.models.map((model) => (
        <Button key={model.id} onClick={() => props.selectModel(model.id)}>{model.name}</Button>
      ))}
      <Button type="button" disabled={props.disabled} onClick={props.submit}>Submit</Button>
    </div>
  ),
}));

const qwen = "dashscope/qwen3.8-max";
const deepseek = "deepseek/deepseek-v4-flash";
const catalog = {
  default_model: qwen,
  fallback_model: "",
  flash_model: deepseek,
  image_model: "",
  models: [qwen, deepseek].map((id) => ({
    id, name: id, display_name: id, version: "", provider: id.split("/")[0], icon: "",
    is_available: true, is_default: id === qwen, is_fallback: false, is_flash: id === deepseek,
  })),
};

const thread = {
  uid: "user-1", thread_id: "thread-1", title: "Conversation", summary: null, agent_id: "LeaderAgent",
  metadata: { model: deepseek }, created_at: "2026-10-14T00:00:00Z", updated_at: "2026-10-14T00:00:00Z", last_message_at: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  HTMLElement.prototype.scrollTo = vi.fn();
  mocks.listModels.mockResolvedValue(catalog);
  mocks.listChatAgents.mockResolvedValue([{ id: "LeaderAgent", name: "Leader", description: "" }]);
  mocks.createThread.mockResolvedValue(thread);
  mocks.createRun.mockResolvedValue({ run_id: "run-1", status: "pending" });
  mocks.getThreadDetail.mockResolvedValue({
    thread, messages: [], active_run: null, pending_interaction: null, next_before_message_id: null,
  });
});

afterEach(cleanup);

function renderChat(path: string) {
  return render(
    <ModelProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/c/:threadId" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </ModelProvider>,
  );
}

it("binds the selected model while creating a conversation and its first Run", async () => {
  renderChat("/");
  await waitFor(() => expect(screen.getByLabelText("Model").textContent).toBe(qwen));
  fireEvent.click(screen.getByRole("button", { name: deepseek }));
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Hello" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit" }));
  await waitFor(() => expect(mocks.createRun).toHaveBeenCalled());
  expect(mocks.createThread).toHaveBeenCalledWith("LeaderAgent", deepseek);
  expect(mocks.createRun).toHaveBeenCalledWith(expect.objectContaining({ threadId: "thread-1", modelId: deepseek }));
});

it("restores a conversation model without resetting a later explicit selection", async () => {
  renderChat("/c/thread-1");
  await waitFor(() => expect(screen.getByLabelText("Model").textContent).toBe(deepseek));
  fireEvent.click(screen.getByRole("button", { name: qwen }));
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "New message" } });
  expect(screen.getByLabelText("Model").textContent).toBe(qwen);
});

it("restores the binding when the model catalog arrives after the conversation", async () => {
  let resolveCatalog!: (value: typeof catalog) => void;
  mocks.listModels.mockReturnValueOnce(new Promise((resolve) => { resolveCatalog = resolve; }));
  renderChat("/c/thread-1");
  await waitFor(() => expect(mocks.getThreadDetail).toHaveBeenCalledWith("thread-1"));
  resolveCatalog(catalog);
  await waitFor(() => expect(screen.getByLabelText("Model").textContent).toBe(deepseek));
});
