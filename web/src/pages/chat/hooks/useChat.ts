import { useCallback, useRef, useState } from "react";

import {
  useStreamSmoother,
  type StreamTextChunk,
} from "@/pages/chat/hooks/useStreamSmoother";
import type { UploadedAttachmentResponse } from "@/types/attachment";
import type {
  AgentRunStreamEvent,
  ChatMessage,
  ThreadDetailResponse,
  ThreadMessageResponse,
  ThreadResponse,
  ThreadSummaryResponse,
} from "@/types/chat";

interface ChatState {
  thread: ThreadSummaryResponse | null;
  messages: ChatMessage[];
  draft: string;
  attachments: UploadedAttachmentResponse[];
  uploadingCount: number;
  uploadError: string;
  loading: boolean;
  submitting: boolean;
  error: string;
}

export interface ChatSubmission {
  query: string;
  draft: string;
  attachments: UploadedAttachmentResponse[];
  optimisticMessageId: number;
}

const initialState = (): ChatState => ({
  thread: null,
  messages: [],
  draft: "",
  attachments: [],
  uploadingCount: 0,
  uploadError: "",
  loading: false,
  submitting: false,
  error: "",
});

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const toChatMessage = (message: ThreadMessageResponse): ChatMessage => ({
  type: message.role === "user" ? "human" : "ai",
  payload: { type: "text", event: message },
});

const chatMessageEvent = (message: ChatMessage) =>
  isRecord(message.payload.event) ? message.payload.event : null;

const chatMessageId = (message: ChatMessage) =>
  chatMessageEvent(message)?.message_id;

const chatMessageRunId = (message: ChatMessage) => {
  const event = chatMessageEvent(message);
  if (typeof event?.run_id === "string") return event.run_id;
  if (!isRecord(event?.run) || typeof event.run.run_id !== "string")
    return null;
  return event.run.run_id;
};

const hasAgentTodo = (event: AgentRunStreamEvent) => {
  if (!isRecord(event.agent_state)) return false;
  const todos = event.agent_state.agent_todo;
  return (
    Array.isArray(todos) &&
    todos.some(
      (todo) =>
        isRecord(todo) &&
        typeof todo.content === "string" &&
        todo.content.trim().length > 0 &&
        ["pending", "in_progress", "completed"].includes(String(todo.status)),
    )
  );
};

export function useChat() {
  const [state, setState] = useState<ChatState>(initialState);
  const current = useRef(state);
  const nextOptimisticId = useRef(-1);

  // Stream callbacks need the latest state while an earlier request is awaiting.
  const getState = useCallback(() => current.current, []);
  const update = useCallback(
    (
      change:
        Partial<ChatState> | ((previous: ChatState) => Partial<ChatState>),
    ) => {
      const patch =
        typeof change === "function" ? change(current.current) : change;
      const next = { ...current.current, ...patch };
      current.current = next;
      setState(next);
    },
    [],
  );

  function clearPendingInput() {
    update({ draft: "", attachments: [], uploadingCount: 0, uploadError: "" });
  }

  function applyThreadDetail(detail: ThreadDetailResponse) {
    const history = detail.messages.map(toChatMessage);
    const retained = getState().messages.filter(
      (message) => message.type === "ai" && message.payload.type === "tool",
    );
    for (const activity of [...retained].reverse()) {
      const activityRunId = chatMessageRunId(activity);
      const insertAt = history.findIndex(
        (message) =>
          message.type === "ai" &&
          message.payload.type === "text" &&
          chatMessageRunId(message) === activityRunId,
      );
      history.splice(insertAt === -1 ? history.length : insertAt, 0, activity);
    }
    update({ thread: detail.thread, messages: history });
  }

  function applyCreatedThread(created: ThreadResponse): ThreadSummaryResponse {
    const thread: ThreadSummaryResponse = {
      thread_id: created.thread_id,
      title: created.title,
      summary: null,
      agent_id: created.agent_id,
      metadata: created.metadata,
      created_at: created.created_at,
      updated_at: created.updated_at,
      last_message_at: null,
    };
    update({ thread });
    return thread;
  }

  function clearRunStreamMessages(runId: string) {
    update((previous) => ({
      messages: previous.messages.filter((message) => {
        if (message.type !== "ai") return true;
        const event = chatMessageEvent(message);
        if (event?.run_id !== runId) return true;
        return !(
          message.payload.type === "tool" || event.status === "streaming"
        );
      }),
    }));
  }

  const appendAiText = useCallback(
    (chunks: StreamTextChunk[]) => {
      if (!chunks.length) return;
      update((previous) => {
        const messages = [...previous.messages];
        for (const chunk of chunks) {
          const index = messages.findIndex(
            (message) =>
              message.type === "ai" &&
              message.payload.type === "text" &&
              chatMessageId(message) === chunk.messageId,
          );
          if (index === -1) {
            messages.push({
              type: "ai",
              payload: {
                type: "text",
                event: {
                  message_id: chunk.messageId,
                  thread_id: chunk.threadId,
                  run_id: chunk.runId,
                  content: chunk.content,
                  status: "streaming",
                  attachments: [],
                  created_at: chunk.createdAt,
                },
              },
            });
            continue;
          }
          const message = messages[index];
          const currentEvent = chatMessageEvent(message);
          if (!currentEvent) continue;
          const content =
            typeof currentEvent.content === "string" ? currentEvent.content : "";
          messages[index] = {
            ...message,
            payload: {
              ...message.payload,
              event: {
                ...currentEvent,
                content: content + chunk.content,
              },
            },
          };
        }
        return { messages };
      });
    },
    [update],
  );
  const streamSmoother = useStreamSmoother(appendAiText);

  function applyRunMessageEvent(event: AgentRunStreamEvent, runId: string) {
    if (event.type === "messages") {
      if (!Array.isArray(event.items)) return;
      const chunks = new Map<string, StreamTextChunk>();
      for (const item of event.items) {
        if (!isRecord(item) || !Array.isArray(item.stream_event)) continue;
        for (const delta of item.stream_event) {
          if (
            !isRecord(delta) ||
            delta.type !== "message_delta" ||
            typeof delta.message_id !== "string" ||
            typeof delta.content_delta !== "string"
          )
            continue;
          const threadId =
            typeof delta.thread_id === "string"
              ? delta.thread_id
              : event.thread_id;
          const key = `${threadId ?? ""}\u0000${delta.message_id}`;
          const current = chunks.get(key);
          if (current) current.content += delta.content_delta;
          else {
            chunks.set(key, {
              messageId: delta.message_id,
              content: delta.content_delta,
              threadId,
              runId,
              createdAt: event.created_at,
            });
          }
        }
      }
      for (const chunk of chunks.values()) streamSmoother.pushChunk(chunk);
      return;
    }
    if (event.type !== "custom" || event.name !== "agent_state") return;
    const messages = getState().messages;
    const index = messages.findIndex((message) => {
      const item = chatMessageEvent(message);
      return (
        message.type === "ai" &&
        message.payload.type === "tool" &&
        item?.run_id === runId &&
        item?.name === "agent_state"
      );
    });
    if (!hasAgentTodo(event)) {
      if (index !== -1)
        update({
          messages: messages.filter((_, position) => position !== index),
        });
      return;
    }
    const toolMessage: ChatMessage = {
      type: "ai",
      payload: { type: "tool", event },
    };
    if (index === -1) update({ messages: [...messages, toolMessage] });
    else {
      const next = [...messages];
      next[index] = toolMessage;
      update({ messages: next });
    }
  }

  function beginSubmission(): ChatSubmission | null {
    const snapshot = getState();
    const query = snapshot.draft.trim();
    const attachments = [...snapshot.attachments];
    if (
      (!query && attachments.length === 0) ||
      snapshot.uploadingCount > 0 ||
      snapshot.submitting
    )
      return null;
    const createdAt = new Date().toISOString();
    const optimistic: ThreadMessageResponse = {
      message_id: nextOptimisticId.current--,
      role: "user",
      content: query,
      image_content: null,
      message_type: attachments.length
        ? query
          ? "multimodal"
          : "attachment"
        : "text",
      status: "pending",
      request_id: null,
      run: null,
      attachments: attachments.map((attachment) => ({
        file_id: attachment.file_id,
        file_name: attachment.file_name,
        content_type: attachment.content_type,
        file_size: attachment.file_size,
        available: true,
        access_url: attachment.access_url,
      })),
      created_at: createdAt,
      updated_at: createdAt,
    };
    update({
      messages: [...snapshot.messages, toChatMessage(optimistic)],
      draft: "",
      attachments: [],
      uploadError: "",
      submitting: true,
      error: "",
    });
    return {
      query,
      draft: snapshot.draft,
      attachments,
      optimisticMessageId: optimistic.message_id,
    };
  }

  function rollbackSubmission(submission: ChatSubmission) {
    update((previous) => ({
      messages: previous.messages.filter(
        (message) => chatMessageId(message) !== submission.optimisticMessageId,
      ),
      draft: submission.draft,
      attachments: submission.attachments,
    }));
  }

  function appendUploadedAttachments(uploaded: UploadedAttachmentResponse[]) {
    update((previous) => ({
      attachments: [...previous.attachments, ...uploaded],
    }));
  }

  function removeAttachment(fileId: string) {
    update((previous) => ({
      attachments: previous.attachments.filter(
        (attachment) => attachment.file_id !== fileId,
      ),
    }));
  }

  function resetThread() {
    streamSmoother.reset();
    update(initialState());
  }

  return {
    state,
    getState,
    update,
    clearPendingInput,
    applyThreadDetail,
    applyCreatedThread,
    clearRunStreamMessages,
    applyRunMessageEvent,
    flushStream: streamSmoother.flushThread,
    resetStream: streamSmoother.reset,
    beginSubmission,
    rollbackSubmission,
    appendUploadedAttachments,
    removeAttachment,
    resetThread,
  };
}
