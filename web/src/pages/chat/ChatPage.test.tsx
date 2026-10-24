import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import { ModelProvider } from "@/context/ModelContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ChatPage from "@/pages/chat/ChatPage";
import type { UploadedAttachmentResponse } from "@/api/attachment";
import type { ChatModelOption } from "@/types/model";

const mocks = vi.hoisted(() => ({
  listModels: vi.fn(),
  getThreadDetail: vi.fn(),
  createThread: vi.fn(),
  generateThreadTitle: vi.fn(),
  renameThread: vi.fn(),
  listChatAgents: vi.fn(),
  createRun: vi.fn(),
  uploadAttachments: vi.fn(),
}));

vi.mock("@/context/AuthContext", () => ({ useAuth: () => ({ accessToken: "token" }) }));
vi.mock("@/api/model", () => ({ listModels: mocks.listModels }));
vi.mock("@/api/thread", () => ({
  createThread: mocks.createThread,
  generateThreadTitle: mocks.generateThreadTitle,
  renameThread: mocks.renameThread,
  getThreadDetail: mocks.getThreadDetail,
  listChatAgents: mocks.listChatAgents,
}));
vi.mock("@/api/attachment", () => ({
  uploadChatAttachments: mocks.uploadAttachments,
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
    attachments: UploadedAttachmentResponse[];
    upload: (files: File[]) => void;
    submit: () => void;
    disabled: boolean;
  }) => (
    <div>
      <Input aria-label="Question" value={props.draft} onChange={(event) => props.setDraft(event.target.value)} />
      <output aria-label="Model">{props.modelId}</output>
      {props.models.map((model) => (
        <Button key={model.id} onClick={() => props.selectModel(model.id)}>{model.name}</Button>
      ))}
      <output aria-label="Attachments">{props.attachments.map((item) => item.file_name).join(",")}</output>
      <Button
        type="button"
        onClick={() => props.upload([new File(["draft"], "draft.txt", { type: "text/plain" })])}
      >
        Upload
      </Button>
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
  metadata: { model: deepseek }, created_at: "2026-10-14T00:00:00Z", updated_at: "2026-10-14T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  HTMLElement.prototype.scrollTo = vi.fn();
  mocks.listModels.mockResolvedValue(catalog);
  mocks.listChatAgents.mockResolvedValue([{ id: "LeaderAgent", name: "Leader", description: "" }]);
  mocks.createThread.mockResolvedValue(thread);
  mocks.generateThreadTitle.mockResolvedValue({ title: "Greeting" });
  mocks.renameThread.mockResolvedValue({ ...thread, title: "Greeting" });
  mocks.createRun.mockResolvedValue({ run_id: "run-1", status: "pending" });
  mocks.uploadAttachments.mockResolvedValue([{
    file_id: "file-1",
    file_name: "draft.txt",
    content_type: "text/plain",
    file_size: 5,
    bucket_name: "attachments",
    object_name: "draft.txt",
    access_url: "/files/file-1",
  }]);
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
  await waitFor(() => expect(mocks.renameThread).toHaveBeenCalledWith("thread-1", "Greeting"));
  expect(mocks.generateThreadTitle).toHaveBeenCalledWith("thread-1", "Hello");
});

it("submits the Run without waiting for title generation", async () => {
  mocks.generateThreadTitle.mockReturnValueOnce(new Promise(() => {}));
  renderChat("/");
  await waitFor(() => expect(screen.getByLabelText("Model").textContent).toBe(qwen));
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Hello" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit" }));
  await waitFor(() => expect(mocks.generateThreadTitle).toHaveBeenCalled());
  expect(mocks.createRun).toHaveBeenCalledTimes(1);
  expect(mocks.renameThread).not.toHaveBeenCalled();
});

it("does not regenerate the title for a conversation with messages", async () => {
  mocks.getThreadDetail.mockResolvedValue({
    thread,
    messages: [{
      message_id: 1, role: "user", content: "Earlier question", image_content: null,
      message_type: "text", status: "completed", request_id: null, run: null,
      attachments: [], created_at: thread.created_at, updated_at: thread.updated_at,
    }],
    active_run: null, pending_interaction: null, next_before_message_id: null,
  });
  renderChat("/c/thread-1");
  await waitFor(() => expect(screen.getByLabelText("Model").textContent).toBe(deepseek));
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Another question" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit" }));
  await waitFor(() => expect(mocks.createRun).toHaveBeenCalled());
  expect(mocks.generateThreadTitle).not.toHaveBeenCalled();
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

it("restores the draft and attachments when creating the first conversation fails", async () => {
  mocks.createThread.mockRejectedValueOnce(new Error("Thread creation failed"));
  renderChat("/");
  await waitFor(() => expect(screen.getByLabelText("Model").textContent).toBe(qwen));

  fireEvent.change(screen.getByLabelText("Question"), {
    target: { value: "Keep this draft" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Upload" }));
  await waitFor(() =>
    expect(screen.getByLabelText("Attachments").textContent).toBe("draft.txt"),
  );
  fireEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toBe("Thread creation failed"),
  );
  expect((screen.getByLabelText("Question") as HTMLInputElement).value).toBe(
    "Keep this draft",
  );
  expect(screen.getByLabelText("Attachments").textContent).toBe("draft.txt");
  expect(mocks.createRun).not.toHaveBeenCalled();
});
