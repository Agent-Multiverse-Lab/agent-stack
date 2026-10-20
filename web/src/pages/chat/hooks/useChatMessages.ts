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
  const interactionToolCalls = useRef(new Map<string, Set<string>>());

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
    interactionToolCalls.current.delete(runId);
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

  function appendReasoning(
    event: AgentRunStreamEvent,
    messageId: string,
    threadId: string | null,
    content: string,
  ) {
    updateMessages((previous) => {
      const messages = [...previous];
      const index = messages.findIndex((message) => {
        const item = chatMessageEvent(message);
        return message.type === "ai" && message.payload.type === "tool" &&
          item?.type === "reasoning" && item.message_id === messageId &&
          item.run_id === event.run_id && item.thread_id === threadId;
      });
      const currentEvent = index === -1 ? null : chatMessageEvent(messages[index]);
      const message: ChatMessage = {
        type: "ai",
        payload: {
          type: "tool",
          event: {
            type: "reasoning",
            message_id: messageId,
            run_id: event.run_id,
            thread_id: threadId,
            created_at: currentEvent?.created_at ?? event.created_at,
            content: String(currentEvent?.content ?? "") + content,
          },
        },
      };
      if (index === -1) messages.push(message);
      else messages[index] = message;
      return messages;
    });
  }

  function upsertToolCall(
    event: AgentRunStreamEvent,
    threadId: string | null,
    toolCallId: string,
    patch: Record<string, unknown>,
  ) {
    const matchesToolCall = (message: ChatMessage) => {
      const item = chatMessageEvent(message);
      return message.type === "ai" && message.payload.type === "tool" &&
        item?.type === "tool_call" && item.tool_call_id === toolCallId &&
        item.run_id === event.run_id && item.thread_id === threadId;
    };
    const callKey = JSON.stringify([threadId, toolCallId]);
    if (patch.name === "ask_user") {
      // 后续工具输出和结束事件不含名称，记录调用 ID 以便继续走独立交互通道。
      const calls = interactionToolCalls.current.get(event.run_id) ?? new Set<string>();
      calls.add(callKey);
      interactionToolCalls.current.set(event.run_id, calls);
    }
    if (interactionToolCalls.current.get(event.run_id)?.has(callKey)) {
      const messages = getMessages();
      const remaining = messages.filter((message) => !matchesToolCall(message));
      if (remaining.length !== messages.length) updateMessages(remaining);
      return;
    }
    updateMessages((previous) => {
      const messages = [...previous];
      const index = messages.findIndex(matchesToolCall);
      const currentEvent = index === -1 ? null : chatMessageEvent(messages[index]);
      const nextEvent: Record<string, unknown> = {
        ...currentEvent,
        ...patch,
        type: "tool_call",
        tool_call_id: toolCallId,
        run_id: event.run_id,
        thread_id: threadId,
        created_at: currentEvent?.created_at ?? event.created_at,
        status: patch.status ?? currentEvent?.status ?? "pending",
      };
      if (Array.isArray(patch.output_deltas)) {
        nextEvent.output_deltas = [
          ...(Array.isArray(currentEvent?.output_deltas) ? currentEvent.output_deltas : []),
          ...patch.output_deltas,
        ];
      }
      const message: ChatMessage = {
        type: "ai",
        payload: { type: "tool", event: nextEvent },
      };
      if (index === -1) messages.push(message);
      else messages[index] = message;
      return messages;
    });
  }

  function applyRunMessageEvent(event: AgentRunStreamEvent, runId: string) {
    if (event.type === "messages") {
      if (!Array.isArray(event.items)) return;
      for (const item of event.items) {
        if (!isRecord(item) || !Array.isArray(item.stream_event)) continue;
        for (const delta of item.stream_event) {
          if (!isRecord(delta)) continue;
          const threadId =
            typeof delta.thread_id === "string"
              ? delta.thread_id
              : event.thread_id;
          if (delta.type === "tool_call" && typeof delta.tool_call_id === "string") {
            const patch: Record<string, unknown> = {};
            if (typeof delta.name === "string" && delta.name) patch.name = delta.name;
            if (delta.args !== undefined) patch.args = delta.args;
            upsertToolCall(event, threadId, delta.tool_call_id, patch);
            continue;
          }
          if (delta.type !== "message_delta" || typeof delta.message_id !== "string") continue;
          const reasoning = [delta.reasoning_content_delta, delta.additional_kwargs_reasoning_content]
            .find((value): value is string => typeof value === "string" && value.length > 0);
          if (reasoning) appendReasoning(event, delta.message_id, threadId, reasoning);
          if (typeof delta.content_delta === "string" && delta.content_delta) {
            streamSmoother.pushChunk({
              messageId: delta.message_id,
              content: delta.content_delta,
              threadId,
              runId,
              createdAt: event.created_at,
            });
          }
        }
      }
      return;
    }
    if (event.type === "custom" && event.name === "agent_execute_event") {
      const execution = isRecord(event.event) ? event.event : null;
      const data = isRecord(execution?.stream_data) ? execution.stream_data : null;
      if (!data || typeof data.tool_call_id !== "string") return;
      const patch: Record<string, unknown> = {};
      switch (data.event) {
        case "tool-started":
          patch.status = "running";
          if (typeof data.tool_name === "string" && data.tool_name) patch.name = data.tool_name;
          if (data.input !== undefined) patch.args = data.input;
          break;
        case "tool-output-delta":
          patch.output_deltas = [data.delta];
          break;
        case "tool-finished":
          patch.status = isRecord(data.output) && data.output.status === "error" ? "error" : "completed";
          patch.output = data.output;
          break;
        case "tool-error":
          patch.status = "error";
          patch.error = data.message;
          break;
        default:
          return;
      }
      upsertToolCall(event, event.thread_id, data.tool_call_id, patch);
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
    interactionToolCalls.current.clear();
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
