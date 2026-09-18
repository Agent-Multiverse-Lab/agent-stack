import { useEffect, useEffectEvent, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";
import { useNavigate, useParams } from "react-router";

import {
  createThread,
  getThreadDetail,
  listChatAgents,
  uploadChatAttachments,
} from "@/api/agent";
import { AskUser } from "@/pages/chat/components/AskUser";
import { ChatMessage } from "@/pages/chat/components/ChatMessage";
import { MessageInput } from "@/pages/chat/components/MessageInput";
import { Thinking } from "@/pages/chat/components/Thinking";
import { useAgentRun } from "@/pages/chat/hooks/useAgentRun";
import { useChat } from "@/pages/chat/hooks/useChat";
import { useModel } from "@/context/ModelContext";
import type { AgentRunEndEvent, ChatMessage as ChatMessageType } from "@/types/chat";

const errorText = (caught: unknown) =>
  caught instanceof Error ? caught.message : "请求失败";
const isAbortError = (caught: unknown) =>
  caught instanceof DOMException && caught.name === "AbortError";
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;
const messageRunId = (message: ChatMessageType) =>
  isRecord(message.payload.event) ? message.payload.event.run_id : undefined;
const messageKey = (message: ChatMessageType, index: number) => {
  const event = isRecord(message.payload.event) ? message.payload.event : null;
  return `${message.type}:${message.payload.type}:${event?.message_id ?? event?.id ?? index}`;
};

export default function ChatPage() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const {
    models,
    selectedModelId,
    loading: modelsLoading,
    selectModel,
  } = useModel();
  const chat = useChat();
  const run = useAgentRun();
  const scroller = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const operation = useRef(0);
  const uploadGeneration = useRef(0);
  const [showScroll, setShowScroll] = useState(false);

  const abortStream = () => {
    controller.current?.abort();
    controller.current = null;
  };
  const invalidate = () => {
    operation.current++;
    uploadGeneration.current++;
    abortStream();
  };

  async function loadAndApplyThread(id: string, expected: number) {
    const detail = await getThreadDetail(id);
    if (operation.current !== expected) return null;
    chat.applyThreadDetail(detail);
    return run.restoreRunFromThread(detail);
  }

  async function monitorRun(id: string, expected: number) {
    const monitoredRunId = run.getState().runId;
    if (!monitoredRunId || !run.getState().streamUrl || !run.isActive()) return;

    while (
      operation.current === expected &&
      run.getState().runId === monitoredRunId &&
      run.getState().streamUrl &&
      run.isActive()
    ) {
      chat.clearRunStreamMessages(monitoredRunId);
      const activeController = new AbortController();
      controller.current = activeController;
      let endEvent: AgentRunEndEvent;
      try {
        const consumed = await run.consumeRunStream(
          activeController.signal,
          (event) => {
            if (
              operation.current === expected &&
              run.getState().runId === monitoredRunId
            ) {
              chat.applyRunMessageEvent(event, monitoredRunId);
            }
          },
        );
        if (!consumed) return;
        endEvent = consumed;
      } catch (caught) {
        if (operation.current !== expected || isAbortError(caught)) return;
        chat.update({ error: errorText(caught) });
        try {
          await loadAndApplyThread(id, expected);
        } catch {
          // Keep the known Run state and retry the stream.
        }
        if (
          operation.current !== expected ||
          run.getState().runId !== monitoredRunId
        )
          return;
        if (!run.isActive()) {
          chat.update({
            error:
              run.getState().runStatus === "failed" ? "Agent 执行失败" : "",
          });
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        continue;
      } finally {
        if (controller.current === activeController) controller.current = null;
      }

      if (operation.current !== expected) return;
      chat.update({ error: "" });
      try {
        await loadAndApplyThread(id, expected);
      } catch (caught) {
        if (operation.current === expected && !isAbortError(caught)) {
          chat.update({ error: errorText(caught) });
        }
      }
      if (operation.current !== expected) return;
      if (endEvent.status === "failed") {
        chat.update({ error: endEvent.error || "Agent 执行失败" });
      }
      return;
    }
  }

  async function loadThread(id: string) {
    const expected = ++operation.current;
    uploadGeneration.current++;
    abortStream();
    run.clearRun();
    chat.update({
      thread: null,
      messages: [],
      draft: "",
      attachments: [],
      uploadingCount: 0,
      uploadError: "",
      submitting: false,
      loading: true,
      error: "",
    });
    try {
      const activeRun = await loadAndApplyThread(id, expected);
      if (activeRun && run.isActive()) void monitorRun(id, expected);
    } catch (caught) {
      if (operation.current === expected && !isAbortError(caught)) {
        chat.update({ thread: null, messages: [], error: errorText(caught) });
      }
    } finally {
      if (operation.current === expected) chat.update({ loading: false });
    }
  }

  const onRouteChange = useEffectEvent((id?: string) => {
    if (!id) {
      invalidate();
      run.clearRun();
      chat.resetThread();
    } else if (chat.getState().thread?.thread_id !== id) {
      void loadThread(id);
    }
  });
  const onUnmount = useEffectEvent(() => invalidate());
  useEffect(() => {
    onRouteChange(threadId);
  }, [threadId]);

  useEffect(() => () => onUnmount(), []);
  useEffect(() => {
    const element = scroller.current;
    if (element) {
      element.scrollTo({ top: element.scrollHeight, behavior: "auto" });
      setShowScroll(false);
    }
  }, [chat.state.messages, run.state.pendingInteraction]);

  async function uploadFiles(files: File[]) {
    if (!files.length) return;
    const expected = uploadGeneration.current;
    chat.update((previous) => ({
      uploadingCount: previous.uploadingCount + files.length,
      uploadError: "",
    }));
    try {
      const uploaded = await uploadChatAttachments(files);
      if (uploadGeneration.current === expected)
        chat.appendUploadedAttachments(uploaded);
    } catch (caught) {
      if (uploadGeneration.current === expected)
        chat.update({ uploadError: errorText(caught) });
    } finally {
      if (uploadGeneration.current === expected) {
        chat.update((previous) => ({
          uploadingCount: Math.max(0, previous.uploadingCount - files.length),
        }));
      }
    }
  }

  async function submit() {
    if (run.isActive() || run.getState().pendingInteraction) return;
    const submission = chat.beginSubmission();
    if (!submission) return;
    const expected = ++operation.current;
    abortStream();
    let runCreated = false;
    try {
      let currentThread = chat.getState().thread;
      if (!currentThread) {
        const agents = await listChatAgents();
        const leader = agents.find((agent) => agent.id === "LeaderAgent");
        if (!leader) throw new Error("LeaderAgent 当前不可用");
        const created = await createThread(leader.id);
        if (operation.current !== expected) return;
        currentThread = chat.applyCreatedThread(created);
        if (threadId !== created.thread_id) {
          navigate(`/c/${encodeURIComponent(created.thread_id)}`, {
            replace: true,
          });
        }
      }
      if (operation.current !== expected) return;
      const createdRun = await run.createRun({
        query: submission.query,
        agentId: currentThread.agent_id,
        threadId: currentThread.thread_id,
        attachmentFileIds: submission.attachments.map((item) => item.file_id),
        modelId: selectedModelId || undefined,
      });
      if (operation.current !== expected) return;
      runCreated = true;
      try {
        await loadAndApplyThread(currentThread.thread_id, expected);
      } catch (caught) {
        if (operation.current === expected && !isAbortError(caught)) {
          chat.update({ error: errorText(caught) });
        }
      }
      if (operation.current !== expected) return;
      if (createdRun.status === "failed")
        chat.update({ error: "Agent 执行失败" });
      await monitorRun(currentThread.thread_id, expected);
    } catch (caught) {
      if (operation.current === expected && !isAbortError(caught)) {
        chat.update({ error: errorText(caught) });
        if (!runCreated) chat.rollbackSubmission(submission);
      }
    } finally {
      if (operation.current === expected) {
        controller.current = null;
        chat.update({ submitting: false });
      }
    }
  }

  async function cancel() {
    chat.update({ error: "" });
    try {
      await run.cancelCurrentRun();
    } catch (caught) {
      chat.update({ error: errorText(caught) });
    }
  }

  async function submitResume(answers: Record<string, string>) {
    const interaction = run.getState().pendingInteraction;
    const currentThread = chat.getState().thread;
    if (!interaction || !currentThread || run.getState().resuming) return;
    const expected = ++operation.current;
    abortStream();
    chat.update({ error: "" });
    try {
      await run.resumeRun(interaction.parent_run_id, {
        thread_id: currentThread.thread_id,
        thread_metadata: {
          request_id: crypto.randomUUID(),
          resume: { answers },
        },
      });
      if (operation.current === expected) {
        await monitorRun(currentThread.thread_id, expected);
      }
    } catch (caught) {
      if (operation.current === expected && !isAbortError(caught)) {
        chat.update({ error: errorText(caught) });
      }
    }
  }

  const chatState = chat.state;
  const runState = run.state;
  const active = run.isActive();
  const pending = runState.pendingInteraction;
  const inputDisabled =
    chatState.loading ||
    runState.cancelling ||
    runState.resuming ||
    Boolean(pending) ||
    (chatState.submitting && !active);
  const docked = chatState.messages.length > 0 || Boolean(pending);
  const hasAssistantText = chatState.messages.some((message) => {
    if (message.type !== "ai" || message.payload.type !== "text") return false;
    const event = isRecord(message.payload.event)
      ? message.payload.event
      : null;
    return (
      messageRunId(message) === runState.runId &&
      typeof event?.content === "string" &&
      event.content.trim().length > 0
    );
  });
  const showThinking =
    !chatState.loading && active && !pending && !hasAssistantText;
  const firstActivityIndex = chatState.messages.findIndex(
    (message) =>
      message.type === "ai" &&
      message.payload.type === "tool" &&
      messageRunId(message) === runState.runId,
  );
  const displayedError = chatState.uploadError || chatState.error;

  return (
    <section className="relative flex h-full min-h-0 flex-col bg-paper text-graphite">
      <div
        ref={scroller}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
        onScroll={(event) => {
          const element = event.currentTarget;
          setShowScroll(
            element.scrollHeight - element.scrollTop - element.clientHeight >
              48,
          );
        }}
      >
        <div className="mx-auto grid w-full max-w-[52rem] content-start gap-7 px-[clamp(1rem,4vw,2rem)] pt-6 pb-10">
          {chatState.loading ? (
            <Thinking label="Loading conversation" />
          ) : (
            chatState.messages.map((message, index) => (
              <div key={messageKey(message, index)}>
                {showThinking && index === firstActivityIndex && <Thinking />}
                <ChatMessage message={message} />
              </div>
            ))
          )}
          {showThinking && firstActivityIndex === -1 && <Thinking />}
        </div>
      </div>

      <footer
        className={`inset-x-0 px-[clamp(0.75rem,4vw,2rem)] ${
          docked
            ? "shrink-0 bg-paper pt-2 pb-[max(1rem,env(safe-area-inset-bottom))]"
            : "absolute top-[38%] -translate-y-1/2"
        } ${pending ? "max-h-full overflow-y-auto overscroll-contain" : ""}`}
      >
        <div className="relative mx-auto grid w-full max-w-[48rem] gap-2">
          {!docked && !chatState.loading && (
            <div className="mb-4 text-center select-none">
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                Welcome to AM
              </h1>
              <p className="mt-2 text-sm text-slate sm:text-base">
                What would you like to explore or build today?
              </p>
            </div>
          )}
          {displayedError && (
            <p
              role="alert"
              className="m-0 rounded-md bg-danger/6 px-3 py-2 text-sm text-danger"
            >
              {displayedError}
            </p>
          )}
          {docked && showScroll && (
            <button
              type="button"
              aria-label="Scroll to latest message"
              title="Scroll to latest message"
              className="z-10 grid size-9 place-items-center justify-self-center rounded-full border border-graphite/10 bg-paper text-slate shadow-sm"
              onClick={() => {
                scroller.current?.scrollTo({
                  top: scroller.current.scrollHeight,
                  behavior: "smooth",
                });
                setShowScroll(false);
              }}
            >
              <ArrowDown size={17} />
            </button>
          )}
          {!chatState.loading && pending && (
            <AskUser
              key={pending.parent_run_id}
              interaction={pending}
              disabled={runState.resuming}
              submit={(answers) => void submitResume(answers)}
            />
          )}
          <MessageInput
            draft={chatState.draft}
            setDraft={(draft) => chat.update({ draft })}
            attachments={chatState.attachments}
            uploading={chatState.uploadingCount}
            running={active}
            disabled={inputDisabled}
            modelId={selectedModelId}
            models={models}
            modelsLoading={modelsLoading}
            placement={docked ? "top" : "bottom"}
            selectModel={selectModel}
            upload={(files) => void uploadFiles(files)}
            removeAttachment={chat.removeAttachment}
            submit={() => void submit()}
            cancel={() => void cancel()}
          />
        </div>
      </footer>
    </section>
  );
}
