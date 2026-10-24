import { Button } from "@/components/ui/button";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";
import { useNavigate, useParams } from "react-router";

import {
  createThread,
  generateThreadTitle,
  getThreadDetail,
  listChatAgents,
  renameThread,
} from "@/api/thread";
import type { UploadedAttachmentResponse } from "@/api/attachment";
import type { AgentRunEndEvent } from "@/api/agent-run";
import { AskUser } from "@/pages/chat/components/AskUser";
import { AgentMessageComposer } from "@/pages/chat/components/AgentMessageComposer";
import { ConversationMessages } from "@/pages/chat/components/ConversationMessages";
import { Thinking } from "@/pages/chat/components/Thinking";
import { useAgentRun } from "@/pages/chat/hooks/useAgentRun";
import { useAttachments } from "@/pages/chat/hooks/useAttachments";
import { useThread } from "@/pages/chat/hooks/useThread";
import { useModel } from "@/context/ModelContext";
import { useTranslation } from "@/i18n";

const isAbortError = (caught: unknown) =>
  caught instanceof DOMException && caught.name === "AbortError";

interface ChatSubmission {
  query: string;
  draft: string;
  attachments: UploadedAttachmentResponse[];
  optimisticMessageId: number;
}

export default function ChatPage() {
  const { t } = useTranslation();
  const errorText = (caught: unknown) =>
    caught instanceof Error ? caught.message : t("Request failed");
  const { threadId } = useParams();
  const navigate = useNavigate();
  const {
    models,
    selectedModelId,
    loading: modelsLoading,
    selectModel,
  } = useModel();
  const thread = useThread();
  const attachments = useAttachments(errorText);
  const run = useAgentRun();
  const scroller = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const operation = useRef(0);
  const submissionInFlight = useRef(false);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [showScroll, setShowScroll] = useState(false);

  const abortStream = () => {
    controller.current?.abort();
    controller.current = null;
  };
  const invalidate = () => {
    operation.current++;
    attachments.invalidate();
    thread.resetStream();
    abortStream();
  };

  async function loadThreadDetail(id: string, expected: number) {
    const detail = await getThreadDetail(id);
    if (operation.current !== expected) return null;
    thread.setThread(detail.thread);
    thread.setMessages(detail.messages);
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
      thread.resetStream(id);
      thread.clearRunStreamMessages(monitoredRunId);
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
              thread.applyRunMessageEvent(event, monitoredRunId);
            }
          },
        );
        if (!consumed) return;
        thread.flushRunStream(monitoredRunId);
        endEvent = consumed;
      } catch (caught) {
        if (operation.current !== expected || isAbortError(caught)) return;
        thread.flushRunStream(monitoredRunId);
        setError(errorText(caught));
        try {
          await loadThreadDetail(id, expected);
        } catch {
          // Keep the known Run state and retry the stream.
        }
        if (
          operation.current !== expected ||
          run.getState().runId !== monitoredRunId
        )
          return;
        if (!run.isActive()) {
          setError(
            run.getState().runStatus === "failed"
              ? t("Agent execution failed")
              : "",
          );
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        continue;
      } finally {
        if (controller.current === activeController) controller.current = null;
      }

      if (operation.current !== expected) return;
      setError("");
      try {
        await loadThreadDetail(id, expected);
      } catch (caught) {
        if (operation.current === expected && !isAbortError(caught)) {
          setError(errorText(caught));
        }
      }
      if (operation.current !== expected) return;
      if (endEvent.status === "failed") {
        setError(endEvent.error || t("Agent execution failed"));
      }
      return;
    }
  }

  async function loadThread(id: string) {
    const expected = ++operation.current;
    attachments.reset();
    abortStream();
    run.clearRun();
    thread.resetThread();
    setDraft("");
    submissionInFlight.current = false;
    setSubmitting(false);
    setLoading(true);
    setError("");
    try {
      const activeRun = await loadThreadDetail(id, expected);
      if (activeRun && run.isActive()) void monitorRun(id, expected);
    } catch (caught) {
      if (operation.current === expected && !isAbortError(caught)) {
        thread.resetThread();
        setError(errorText(caught));
      }
    } finally {
      if (operation.current === expected) setLoading(false);
    }
  }

  const onRouteChange = useEffectEvent((id?: string) => {
    if (!id) {
      invalidate();
      run.clearRun();
      thread.resetThread();
      attachments.reset();
      setDraft("");
      setLoading(false);
      submissionInFlight.current = false;
      setSubmitting(false);
      setError("");
    } else if (thread.getState().thread?.thread_id !== id) {
      void loadThread(id);
    }
  });
  const onUnmount = useEffectEvent(() => invalidate());
  const boundModelId = thread.state.thread?.metadata.model;
  useEffect(() => {
    if (typeof boundModelId === "string" && boundModelId) selectModel(boundModelId);
  }, [boundModelId, thread.state.thread?.thread_id, selectModel]);
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
  }, [thread.state.messages, run.state.pendingInteraction]);

  function beginSubmission(): ChatSubmission | null {
    const attachmentState = attachments.getState();
    const query = draft.trim();
    const selectedAttachments = [...attachmentState.attachments];
    if (
      (!query && selectedAttachments.length === 0) ||
      attachmentState.uploadingCount > 0 ||
      submissionInFlight.current
    )
      return null;

    const createdAt = new Date().toISOString();
    const optimisticMessageId = thread.addOptimisticMessage({
      role: "user",
      content: query,
      image_content: null,
      message_type: selectedAttachments.length
        ? query
          ? "multimodal"
          : "attachment"
        : "text",
      status: "pending",
      request_id: null,
      run: null,
      attachments: selectedAttachments.map((attachment) => ({
        file_id: attachment.file_id,
        file_name: attachment.file_name,
        content_type: attachment.content_type,
        file_size: attachment.file_size,
        available: true,
        access_url: attachment.access_url,
      })),
      created_at: createdAt,
      updated_at: createdAt,
    });
    setDraft("");
    attachments.clearAttachments();
    attachments.clearAttachmentError();
    submissionInFlight.current = true;
    setSubmitting(true);
    setError("");
    return {
      query,
      draft,
      attachments: selectedAttachments,
      optimisticMessageId,
    };
  }

  function rollbackSubmission(submission: ChatSubmission) {
    thread.removeOptimisticMessage(submission.optimisticMessageId);
    setDraft(submission.draft);
    attachments.setAttachments(submission.attachments);
  }

  async function submit() {
    if (run.isActive() || run.getState().pendingInteraction) return;
    const isFirstMessage = thread.getState().messages.length === 0;
    const submission = beginSubmission();
    if (!submission) return;
    const expected = ++operation.current;
    abortStream();
    let runCreated = false;
    try {
      let currentThread = thread.getState().thread;
      if (!currentThread) {
        const agents = await listChatAgents();
        const leader = agents.find((agent) => agent.id === "LeaderAgent");
        if (!leader) throw new Error(t("Leader agent is unavailable"));
        const created = await createThread(leader.id, selectedModelId || undefined);
        if (operation.current !== expected) return;
        currentThread = created;
        thread.setThread(currentThread);
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
      if (isFirstMessage && submission.query) {
        void updateTitle(currentThread.thread_id, submission.query);
      }
      try {
        await loadThreadDetail(currentThread.thread_id, expected);
      } catch (caught) {
        if (operation.current === expected && !isAbortError(caught)) {
          setError(errorText(caught));
        }
      }
      if (operation.current !== expected) return;
      if (createdRun.status === "failed")
        setError(t("Agent execution failed"));
      await monitorRun(currentThread.thread_id, expected);
    } catch (caught) {
      if (operation.current === expected && !isAbortError(caught)) {
        setError(errorText(caught));
        if (!runCreated) rollbackSubmission(submission);
      }
    } finally {
      if (operation.current === expected) {
        controller.current = null;
        submissionInFlight.current = false;
        setSubmitting(false);
      }
    }
  }

  async function updateTitle(id: string, query: string) {
    try {
      const { title } = await generateThreadTitle(id, query);
      const updated = await renameThread(id, title);
      const current = thread.getState().thread;
      if (current?.thread_id === id) {
        thread.setThread({ ...current, title: updated.title });
      }
      window.dispatchEvent(new Event("thread-title-updated"));
    } catch (caught) {
      console.error("Failed to update conversation title", caught);
    }
  }

  async function cancel() {
    setError("");
    try {
      await run.cancelCurrentRun();
    } catch (caught) {
      setError(errorText(caught));
    }
  }

  async function submitResume(answers: Record<string, string>) {
    const interaction = run.getState().pendingInteraction;
    const currentThread = thread.getState().thread;
    if (!interaction || !currentThread || run.getState().resuming) return;
    const expected = ++operation.current;
    abortStream();
    setError("");
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
        setError(errorText(caught));
      }
    }
  }

  const threadState = thread.state;
  const attachmentState = attachments.state;
  const runState = run.state;
  const active = run.isActive();
  const pending = runState.pendingInteraction;
  const inputDisabled =
    loading ||
    runState.cancelling ||
    runState.resuming ||
    Boolean(pending) ||
    (submitting && !active);
  const docked = threadState.messages.length > 0 || Boolean(pending);
  const displayedError = attachmentState.uploadError || error;
  const conversationTitle =
    threadState.thread?.title ||
    (threadId ? t("Untitled Conversation") : t("New chat"));
  const statusLabel = active
    ? t("In progress")
    : pending
      ? t("Interrupted")
      : runState.runStatus === "failed" || Boolean(displayedError)
        ? t("Failed")
        : runState.runStatus === "cancelled"
          ? t("Cancelled")
          : t("Active");
  const statusDotClass = active
    ? "bg-primary animate-pulse motion-reduce:animate-none"
    : pending
      ? "bg-warning"
      : runState.runStatus === "failed" || Boolean(displayedError)
        ? "bg-destructive"
        : runState.runStatus === "cancelled"
          ? "bg-muted-foreground"
          : "bg-success";

  return (
    <section className="relative flex h-full min-h-0 flex-col bg-card text-foreground">
      <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-(--page-padding)">
        <h2 className="min-w-0 truncate text-sm font-medium">
          {conversationTitle}
        </h2>
        <Button
          variant="ghost"
          size="sm"
          type="button"
          aria-label={`${t("Status")}: ${statusLabel}`}
          className="h-7 shrink-0 gap-1.5 rounded-md px-2.5 text-xs font-medium text-muted-foreground"
        >
          <span
            aria-hidden="true"
            className={`size-2 rounded-full ${statusDotClass}`}
          />
          <span>{statusLabel}</span>
        </Button>
      </header>
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
        <div className="mx-auto grid w-full max-w-[800px] content-start gap-6 px-8 py-4">
          {loading ? (
            <Thinking label="Loading conversation" />
          ) : (
            <ConversationMessages
              messages={threadState.messages}
              threadId={threadState.thread?.thread_id}
              currentRunId={runState.runId}
              status={runState.runStatus}
              active={active}
              waiting={Boolean(pending)}
              startedAt={runState.startedAt}
            />
          )}
        </div>
      </div>

      <footer
        className={`inset-x-0 ${
          docked
            ? "shrink-0 bg-card px-3.5 pt-3.5 pb-[max(1rem,env(safe-area-inset-bottom))]"
            : "absolute top-[45%] mx-auto w-[90%] max-w-[800px] -translate-y-1/2 px-0"
        } ${pending ? "max-h-full overflow-y-auto overscroll-contain" : ""}`}
      >
        <div className="relative mx-auto grid w-full max-w-[800px] gap-2">
          {!docked && !loading && (
            <div className="mb-4 text-center select-none">
              <h1 className="text-2xl font-semibold">
                {t("Welcome to AM")}
              </h1>
            </div>
          )}
          {displayedError && (
            <p
              role="alert"
              className="m-0 rounded-md bg-destructive-muted px-3 py-2 text-sm text-destructive"
            >
              {displayedError}
            </p>
          )}
          {docked && showScroll && (
            <Button variant="ghost"
              type="button"
              aria-label={t("Scroll to latest message")}
              title={t("Scroll to latest message")}
              className="z-10 grid size-9 place-items-center justify-self-center rounded-full border border-border bg-card text-muted-foreground"
              onClick={() => {
                scroller.current?.scrollTo({
                  top: scroller.current.scrollHeight,
                  behavior: "smooth",
                });
                setShowScroll(false);
              }}
            >
              <ArrowDown size={17} />
            </Button>
          )}
          {!loading && pending && (
            <AskUser
              key={pending.parent_run_id}
              interaction={pending}
              disabled={runState.resuming}
              submit={(answers) => void submitResume(answers)}
            />
          )}
          <AgentMessageComposer
            draft={draft}
            setDraft={setDraft}
            attachments={attachmentState.attachments}
            uploading={attachmentState.uploadingCount}
            running={active}
            disabled={inputDisabled}
            modelId={selectedModelId}
            models={models}
            modelsLoading={modelsLoading}
            placement={docked ? "top" : "bottom"}
            selectModel={selectModel}
            upload={(files) => void attachments.uploadFiles(files)}
            removeAttachment={attachments.removeAttachment}
            submit={() => void submit()}
            cancel={() => void cancel()}
          />
        </div>
      </footer>
    </section>
  );
}
