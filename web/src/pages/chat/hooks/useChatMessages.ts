import { useCallback, useRef, useState } from "react";

import {
  useStreamSmoother,
  type StreamTextChunk,
} from "@/pages/chat/hooks/useStreamSmoother";
import type {
  AgentRunStreamEvent,
  ChatMessage,
  ThreadMessageResponse,
} from "@/types/chat";

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

/** Owns history, optimistic messages, streamed output, and text buffering. */
export function useChatMessages() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const current = useRef(messages);
  const nextOptimisticId = useRef(-1);

  const getMessages = useCallback(() => current.current, []);
  const updateMessages = useCallback(
    (change: ChatMessage[] | ((previous: ChatMessage[]) => ChatMessage[])) => {
      const next = typeof change === "function" ? change(current.current) : change;
      current.current = next;
      setMessages(next);
    },
    [],
  );

  function applyHistory(historyMessages: ThreadMessageResponse[]) {
    const history = historyMessages.map(toChatMessage);
    const retained = getMessages().filter(
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
    updateMessages(history);
  }

  function addOptimisticMessage(message: Omit<ThreadMessageResponse, "message_id">) {
    const messageId = nextOptimisticId.current--;
    updateMessages((previous) => [
      ...previous,
      toChatMessage({ ...message, message_id: messageId }),
    ]);
    return messageId;
  }

  function removeOptimisticMessage(messageId: number) {
    updateMessages((previous) => previous.filter(
      (message) => chatMessageId(message) !== messageId,
    ));
  }

  function clearRunStreamMessages(runId: string) {
    updateMessages((messages) =>
      messages.filter((message) => {
        if (message.type !== "ai") return true;
        const event = chatMessageEvent(message);
        if (event?.run_id !== runId) return true;
        return !(
          message.payload.type === "tool" || event.status === "streaming"
        );
      }),
    );
  }

  const appendAiText = useCallback(
    (chunks: StreamTextChunk[]) => {
      if (!chunks.length) return;
      updateMessages((previous) => {
        const messages = [...previous];
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
        return messages;
      });
    },
    [updateMessages],
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
    const messages = getMessages();
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
        updateMessages(messages.filter((_, position) => position !== index));
      return;
    }
    const toolMessage: ChatMessage = {
      type: "ai",
      payload: { type: "tool", event },
    };
    if (index === -1) updateMessages([...messages, toolMessage]);
    else {
      const next = [...messages];
      next[index] = toolMessage;
      updateMessages(next);
    }
  }

  function clearMessages() {
    streamSmoother.reset();
    updateMessages([]);
  }

  return {
    messages,
    getMessages,
    applyHistory,
    addOptimisticMessage,
    removeOptimisticMessage,
    clearRunStreamMessages,
    applyRunMessageEvent,
    flushStream: streamSmoother.flushThread,
    resetStream: streamSmoother.reset,
    clearMessages,
  };
}
