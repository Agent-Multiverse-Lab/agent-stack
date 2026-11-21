import { Button } from "@/components/ui/button";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import { ArrowDown, PanelRight } from "lucide-react";
import { useNavigate, useParams } from "react-router";

import {
  createThread,
  generateThreadTitle,
  getThreadDetail,
  listChatAgents,
  renameThread,
} from "@/api/thread";
import { ApiError } from "@/api/client";
import type { UploadedAttachmentResponse } from "@/api/attachment";
import { Input } from "@/components/ui/input";
import type { AgentRunEndEvent } from "@/api/agent-run";
import { AskUser } from "@/pages/chat/components/AskUser";
import { AgentMessageComposer } from "@/pages/chat/components/AgentMessageComposer";
import {
  ChatWorkspaceSidebar,
  type ChatSidebarTab,
} from "@/pages/chat/components/ChatWorkspaceSidebar";
import { ConversationMessages } from "@/pages/chat/components/ConversationMessages";
import { Thinking } from "@/pages/chat/components/Thinking";
import { useAgentRun } from "@/pages/chat/hooks/useAgentRun";
import { useAttachments } from "@/pages/chat/hooks/useAttachments";
import { useThread } from "@/pages/chat/hooks/useThread";
import { useModel } from "@/context/ModelContext";
import { useTranslation } from "@/i18n";

/** 识别切换会话或卸载页面时主动中断请求产生的异常。 */
const isAbortError = (caught: unknown) =>
  caught instanceof DOMException && caught.name === "AbortError";

/** 识别并发晋升导致操作返回 409 冲突并附带 run_id 的响应异常。 */
const isPromotedConflictError = (caught: unknown) =>
  caught instanceof ApiError &&
  caught.status === 409 &&
  typeof caught.data?.run_id === "string";

const PROMOTE_RECHECK_DELAYS_MS = [80, 160, 320];

interface ChatSubmission {
  query: string;
  draft: string;
  attachments: UploadedAttachmentResponse[];
  optimisticMessageId: number;
}

/** 编排当前会话的消息展示、用户发送、Run 订阅及提问恢复。 */
export default function ChatPage() {
  const { t } = useTranslation();
  /** 提取可展示的异常消息，未知异常使用统一提示。 */
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
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<ChatSidebarTab>("state");

  /** 仅在版本仍匹配时拉取并同步等待区列表，避免流式输出期间覆盖页面消息。 */
  async function syncQueuedRequests(id: string, expected: number) {
    const detail = await getThreadDetail(id);
    if (operation.current === expected) {
      run.setQueuedRequests(detail.queued_requests ?? []);
    }
  }

  /** 中断当前页面的事件订阅并释放控制器引用。 */
  const abortStream = () => {
    controller.current?.abort();
    controller.current = null;
  };
  /** 使旧会话及附件上传的在途操作失效，重置流合并状态并断开旧订阅。 */
  const invalidate = () => {
    operation.current++;
    attachments.invalidate();
    thread.resetStream();
    abortStream();
  };

  /** 加载会话和持久化消息；仅在操作版本仍匹配时更新页面，并返回活动 Run。 */
  async function loadThreadDetail(id: string, expected: number) {
    const detail = await getThreadDetail(id);
    if (operation.current !== expected) return null;
    thread.setThread(detail.thread);
    thread.setMessages(detail.messages);
    return run.restoreRunFromThread(detail);
  }

  /**
   * 持续订阅指定会话的当前 Run，将流事件交给 useThread 合并到消息列表。
   * 断流后读取会话状态，仍在运行则间隔一秒重连；终态后重新加载持久化消息。
   */
  async function monitorRun(id: string, expected: number) {
    let monitoredRunId = run.getState().runId ?? "";
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
          // 会话详情读取失败时保留已知 Run 状态，继续尝试订阅。
        }
        if (operation.current !== expected) return;
        if (run.isActive() && run.getState().runId !== monitoredRunId) {
          monitoredRunId = run.getState().runId ?? "";
          continue;
        }
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
      const hadSteerQueued = run
        .getState()
        .queuedRequests.some((item) => item.dispatch_policy === "steer");
      try {
        await loadThreadDetail(id, expected);
      } catch (caught) {
        if (operation.current === expected && !isAbortError(caught)) {
          setError(errorText(caught));
        }
      }
      if (operation.current !== expected) return;
      if (run.isActive() && run.getState().runId !== monitoredRunId) {
        monitoredRunId = run.getState().runId ?? "";
        continue;
      }

      const shouldRecheckPromotion =
        endEvent.status === "completed" ||
        (endEvent.status === "cancelled" &&
          (hadSteerQueued ||
            run
              .getState()
              .queuedRequests.some((item) => item.dispatch_policy === "steer")));
      if (shouldRecheckPromotion) {
        for (const delay of PROMOTE_RECHECK_DELAYS_MS) {
          if (
            operation.current !== expected ||
            run.isActive() ||
            run.getState().pendingInteraction ||
            run.getState().queuedRequests.length === 0
          ) {
            break;
          }
          await new Promise((resolve) => window.setTimeout(resolve, delay));
          if (operation.current !== expected) return;
          try {
            await loadThreadDetail(id, expected);
          } catch {
            // 仅作等待区切换窗口的短暂补偿重拉，读取失败时不覆盖终态页面。
          }
          if (operation.current !== expected) return;
          if (run.isActive() && run.getState().runId !== monitoredRunId) {
            break;
          }
        }
        if (run.isActive() && run.getState().runId !== monitoredRunId) {
          monitoredRunId = run.getState().runId ?? "";
          continue;
        }
      }

      if (endEvent.status === "failed") {
        setError(endEvent.error || t("Agent execution failed"));
      }
      return;
    }
  }

  /** 切换到指定会话，重置本地输入和 Run 状态，加载详情后接续已有活动 Run。 */
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

  /** 根据路由进入新会话空白页，或加载被打开的已有会话。 */
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
  /** 页面卸载时使在途操作失效，并关闭当前事件订阅。 */
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

  /** 将当前会话标题复制到编辑草稿，并打开标题编辑框。 */
  function startTitleEdit() {
    const current = thread.getState().thread;
    if (!current) return;
    setTitleDraft(current.title);
    setEditingTitle(true);
  }

  /** 保存非空且已修改的标题，成功后通知会话导航刷新标题。 */
  async function saveTitle() {
    const current = thread.getState().thread;
    const next = titleDraft.trim();
    setEditingTitle(false);
    if (!current || !next || next === current.title) return;
    try {
      const updated = await renameThread(current.thread_id, next);
      thread.setThread({ ...current, title: updated.title });
      window.dispatchEvent(new Event("thread-title-updated"));
    } catch (caught) {
      setError(errorText(caught));
    }
  }

  /**
   * 检查输入和附件上传状态，插入临时用户消息并清空输入框。
   * 返回用于提交及失败恢复的正文、附件和草稿快照；不能提交时返回 null。
   */
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

  /** 创建 Run 未成功返回时移除临时消息，并恢复本次提交的草稿和附件。 */
  function rollbackSubmission(submission: ChatSubmission) {
    thread.removeOptimisticMessage(submission.optimisticMessageId);
    setDraft(submission.draft);
    attachments.setAttachments(submission.attachments);
  }

  /** 刷新会话详情并切流监控当前（或新晋升）的活动 Run。 */
  async function refreshAndMonitorThread(threadId: string) {
    const expected = ++operation.current;
    abortStream();
    const activeRun = await loadThreadDetail(threadId, expected);
    if (operation.current === expected && activeRun && run.isActive()) {
      void monitorRun(threadId, expected);
    }
  }

  /** 在会话运行中以 enqueue 或 steer 即时请求后端落库，返回 200 时直接切流到新 Run。 */
  async function sendBusySubmission(packet: {
    query: string;
    attachments: UploadedAttachmentResponse[];
    dispatchPolicy: "enqueue" | "steer";
  }) {
    const currentThread = thread.getState().thread;
    if (!currentThread || submissionInFlight.current) return false;
    let activeExpected = operation.current;
    submissionInFlight.current = true;
    setSubmitting(true);
    setError("");
    try {
      const result = await run.createRun({
        query: packet.query,
        agentId: currentThread.agent_id,
        threadId: currentThread.thread_id,
        attachmentFileIds: packet.attachments.map((item) => item.file_id),
        modelId: selectedModelId || undefined,
        dispatchPolicy: packet.dispatchPolicy,
      });
      if (operation.current !== activeExpected) return false;
      setDraft("");
      attachments.clearAttachments();
      attachments.clearAttachmentError();
      if (result.run_id !== null) {
        activeExpected = ++operation.current;
        abortStream();
        const activeRun = await loadThreadDetail(
          currentThread.thread_id,
          activeExpected,
        );
        if (operation.current !== activeExpected) return false;
        if (result.status === "failed") setError(t("Agent execution failed"));
        if (activeRun && run.isActive()) {
          void monitorRun(currentThread.thread_id, activeExpected);
        }
      } else {
        await syncQueuedRequests(currentThread.thread_id, activeExpected);
      }
      return true;
    } catch (caught) {
      if (operation.current === activeExpected && !isAbortError(caught)) {
        setError(errorText(caught));
      }
      return false;
    } finally {
      if (operation.current === activeExpected) {
        submissionInFlight.current = false;
        setSubmitting(false);
      }
    }
  }

  /**
   * 处理普通发送：需要时先创建会话，再提交 chat Run、刷新消息并订阅事件。
   * 运行中无论是 enqueue 还是 steer 均立即发送 POST /api/agent/runs 持久化到数据库等待区。
   */
  async function submit(dispatchPolicy: "enqueue" | "steer" = "enqueue") {
    if (run.getState().pendingInteraction) return;
    if (run.isActive()) {
      const currentThread = thread.getState().thread;
      const selected = [...attachments.getState().attachments];
      const query = draft.trim();
      if (
        !currentThread ||
        submissionInFlight.current ||
        attachments.getState().uploadingCount > 0 ||
        (!query && selected.length === 0)
      ) {
        return;
      }
      await sendBusySubmission({
        query,
        attachments: selected,
        dispatchPolicy,
      });
      return;
    }
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
      void monitorRun(currentThread.thread_id, expected);
    } catch (caught) {
      if (operation.current === expected && !isAbortError(caught)) {
        setError(errorText(caught));
        if (!runCreated) rollbackSubmission(submission);
      }
    } finally {
      if (operation.current === expected) {
        submissionInFlight.current = false;
        setSubmitting(false);
      }
    }
  }

  /** 乐观移除等待区条目并调用逻辑软取消接口；409 已晋升时自动接入新 Run，其余失败回滚。 */
  async function removeQueuedRequest(requestId: string) {
    const currentThread = thread.getState().thread;
    if (!currentThread) return;
    const expected = operation.current;
    const previous = run.getState().queuedRequests;
    run.setQueuedRequests((items) =>
      items.filter((item) => item.request_id !== requestId),
    );
    setError("");
    try {
      await run.cancelQueuedRequest(requestId);
      if (operation.current !== expected) return;
      await syncQueuedRequests(currentThread.thread_id, expected);
    } catch (caught) {
      if (operation.current !== expected || isAbortError(caught)) return;
      if (isPromotedConflictError(caught)) {
        try {
          await refreshAndMonitorThread(currentThread.thread_id);
        } catch (refreshCaught) {
          if (!isAbortError(refreshCaught)) {
            setError(errorText(refreshCaught));
          }
        }
        return;
      }
      run.setQueuedRequests(previous);
      setError(errorText(caught));
    }
  }

  /** 将等待区请求原地升级为 steer（202），或在会话空闲时就地晋升执行（200）。 */
  async function steerQueuedRequest(requestId: string) {
    const currentThread = thread.getState().thread;
    if (!currentThread || submissionInFlight.current) return;
    let activeExpected = operation.current;
    submissionInFlight.current = true;
    setSubmitting(true);
    setError("");
    try {
      const result = await run.steerQueuedRequest(requestId);
      if (operation.current !== activeExpected) return;
      if (result.run_id !== null) {
        activeExpected = ++operation.current;
        abortStream();
        const activeRun = await loadThreadDetail(
          currentThread.thread_id,
          activeExpected,
        );
        if (operation.current !== activeExpected) return;
        if (result.status === "failed") setError(t("Agent execution failed"));
        if (activeRun && run.isActive()) {
          void monitorRun(currentThread.thread_id, activeExpected);
        }
      } else {
        await syncQueuedRequests(currentThread.thread_id, activeExpected);
      }
    } catch (caught) {
      if (operation.current !== activeExpected || isAbortError(caught)) return;
      if (isPromotedConflictError(caught)) {
        try {
          await refreshAndMonitorThread(currentThread.thread_id);
        } catch (refreshCaught) {
          if (!isAbortError(refreshCaught)) {
            setError(errorText(refreshCaught));
          }
        }
        return;
      }
      setError(errorText(caught));
      try {
        await syncQueuedRequests(currentThread.thread_id, activeExpected);
      } catch {
        // 同步失败时不覆盖已记录的业务错误提示。
      }
    } finally {
      if (operation.current === activeExpected) {
        submissionInFlight.current = false;
        setSubmitting(false);
      }
    }
  }

  /** 根据首条正文生成并保存会话标题，再通知导航刷新；失败记录到控制台。 */
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

  /** 将停止操作交给 Run Hook，取消请求失败时在页面展示错误。 */
  async function cancel() {
    setError("");
    try {
      await run.cancelCurrentRun();
    } catch (caught) {
      setError(errorText(caught));
    }
  }

  /**
   * 将提问组件提交的 question_id → 选项 value 字典放入 request_metadata.resume。
   * 携带当前会话和 Agent、type=resume 及新请求 ID，成功后订阅新的 Resume Run。
   */
  async function submitResume(answers: Record<string, string>) {
    const interaction = run.getState().pendingInteraction;
    const currentThread = thread.getState().thread;
    if (!interaction || !currentThread || run.getState().resuming) return;
    const expected = ++operation.current;
    abortStream();
    setError("");
    try {
      await run.resumeRun(interaction.created_by_run_id, {
        agent_id: currentThread.agent_id,
        thread_id: currentThread.thread_id,
        request_metadata: {
          type: "resume",
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
    submitting;
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
    <section className="relative flex h-full min-h-0 flex-row bg-card text-foreground">
      <div className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-border bg-card px-(--page-padding)">
          <div className="flex min-w-0 items-center gap-2">
            {editingTitle ? (
              <Input
                value={titleDraft}
                onChange={(event) => setTitleDraft(event.target.value)}
                onBlur={() => void saveTitle()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    void saveTitle();
                  }
                  if (event.key === "Escape") setEditingTitle(false);
                }}
                autoFocus
                aria-label={t("Conversation title")}
                className="h-7 w-[min(42vw,360px)] text-sm"
              />
            ) : (
              <h2 className="min-w-0 truncate text-sm font-medium">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-auto max-w-full truncate rounded-sm p-0 text-left text-sm font-medium hover:bg-transparent hover:text-foreground/80"
                  title={
                    threadState.thread
                      ? t("Rename conversation")
                      : conversationTitle
                  }
                  onClick={startTitleEdit}
                >
                  {conversationTitle}
                </Button>
              </h2>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              type="button"
              aria-label={t("Open workspace")}
              title={t("Open workspace")}
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen((current) => !current)}
            >
              <PanelRight />
            </Button>
          </div>
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
          className={`inset-x-0 ${docked
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
              <Button
                variant="ghost"
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
                key={pending.created_by_run_id}
                interaction={pending}
                disabled={runState.resuming}
                submit={(answers) => void submitResume(answers)}
              />
            )}
            {runState.queuedRequests.length > 0 && (
              <ul aria-label={t("Waiting requests")} className="m-0 grid list-none gap-1 rounded-lg border border-border bg-muted p-2">
                {runState.queuedRequests.map((item) => (
                  <li key={item.request_id} className="flex items-center gap-2 text-sm">
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {item.dispatch_policy === "steer" ? t("Steer") : t("Queued")}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{item.content || t("Attachment")}</span>
                    {(!active || item.dispatch_policy !== "steer") && !pending && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={submitting}
                        onClick={() => void steerQueuedRequest(item.request_id)}
                      >
                        {active ? t("Steer") : t("Run now")}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void removeQueuedRequest(item.request_id)}
                    >
                      {t("Remove")}
                    </Button>
                  </li>
                ))}
              </ul>
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
              threadId={threadState.thread?.thread_id}
              selectModel={selectModel}
              upload={(files) => void attachments.uploadFiles(files)}
              removeAttachment={attachments.removeAttachment}
              submit={(policy) => void submit(policy)}
              cancel={() => void cancel()}
            />
          </div>
        </footer>
      </div>

      <ChatWorkspaceSidebar
        open={sidebarOpen}
        tab={sidebarTab}
        onTabChange={setSidebarTab}
        onClose={() => setSidebarOpen(false)}
        threadId={threadState.thread?.thread_id}
        agentId={threadState.thread?.agent_id}
        modelId={selectedModelId}
        runId={runState.runId}
        runStatus={runState.runStatus}
        statusLabel={statusLabel}
        statusDotClass={statusDotClass}
        active={active}
        messages={threadState.messages}
      />
    </section>
  );
}
