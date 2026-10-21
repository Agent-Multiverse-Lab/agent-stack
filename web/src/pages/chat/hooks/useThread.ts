import { useCallback, useRef, useState } from "react";

import {
  useStreamSmoother,
  type StreamTextChunk,
} from "@/pages/chat/hooks/useStreamSmoother";
import type {
  AgentRunMessagesEvent,
  AgentRunMessagesItemResponse,
  AgentRunStreamEvent,
} from "@/api/agent-run";
import type {
  ThreadMessageResponse,
  ThreadMetadataResponse,
} from "@/api/thread";
import type {
  AIMessageChunk,
  ChatMessage,
  ToolCallArguments,
} from "@/pages/chat/types";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const isAgentRunMessagesEvent = (
  event: AgentRunStreamEvent,
): event is AgentRunMessagesEvent =>
  event.type === "messages" && Array.isArray(event.items);

const asWireString = (value: unknown) => {
  if (typeof value !== "string") return undefined;
  const normalized = value.trim();
  return normalized && !["None", "null", "undefined"].includes(normalized)
    ? normalized
    : undefined;
};

const isAgentRunMessagesItem = (
  value: unknown,
): value is AgentRunMessagesItemResponse =>
  isRecord(value) && Array.isArray(value.stream_event);

const toAIMessageChunk = (value: unknown): AIMessageChunk | null => {
  if (
    !isRecord(value) ||
    value.type !== "tool_call" ||
    typeof value.message_id !== "string"
  )
    return null;
  return {
    type: "tool_call",
    message_id: value.message_id,
    thread_id:
      typeof value.thread_id === "string" || value.thread_id === null
        ? value.thread_id
        : undefined,
    tool_call_id:
      typeof value.tool_call_id === "string" || value.tool_call_id === null
        ? value.tool_call_id
        : undefined,
    name:
      typeof value.name === "string" || value.name === null
        ? value.name
        : undefined,
    args: value.args as ToolCallArguments | undefined,
    index:
      typeof value.index === "number" || value.index === null
        ? value.index
        : undefined,
  };
};

const messageChunks = (
  items: unknown[],
  previousCompoundSignature = "",
): { chunks: unknown[]; compoundSignature: string } => {
  const chunks: unknown[] = [];
  let compoundSignature = previousCompoundSignature;
  for (const item of items) {
    if (!isAgentRunMessagesItem(item)) {
      compoundSignature = "";
      continue;
    }
    const signature =
      item.stream_event.length > 1
        ? JSON.stringify(item.stream_event)
        : "";
    if (signature && signature === compoundSignature) continue;
    chunks.push(...item.stream_event);
    compoundSignature = signature;
  }
  return { chunks, compoundSignature };
};

const parseJsonValue = (value: string): ToolCallArguments | undefined => {
  let parsed: unknown = value;
  for (let pass = 0; pass < 2 && typeof parsed === "string"; pass += 1) {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      return pass === 0 ? undefined : (parsed as string);
    }
  }
  return parsed as ToolCallArguments;
};

const hasToolErrorStatus = (value: unknown): boolean => {
  if (Array.isArray(value)) return value.some(hasToolErrorStatus);
  if (!isRecord(value)) return false;
  if (value.status === "error") return true;
  return hasToolErrorStatus(value.update) || hasToolErrorStatus(value.messages);
};

interface ToolCallIdentity {
  toolCallId?: string;
  messageId?: string;
  index?: number;
}

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

interface ThreadState {
  thread: ThreadMetadataResponse | null;
  messages: ChatMessage[];
}

type ThreadStateUpdater = (previous: ThreadState) => ThreadState;

const initialThreadState = (): ThreadState => ({
  thread: null,
  messages: [],
});

/** Owns the backend Thread and its persisted and streamed messages. */
export function useThread() {
  const [state, setState] = useState<ThreadState>(initialThreadState);
  const current = useRef(state);
  const nextOptimisticId = useRef(-1);
  const interactionToolCalls = useRef(new Map<string, Set<string>>());
  const toolArgumentBuffers = useRef(new Map<string, string>());
  const activeToolCalls = useRef(new Map<string, ToolCallIdentity>());
  const compoundChunkSignatures = useRef(new Map<string, string>());

  // Async stream callbacks must always read the latest Conversation snapshot.
  const getState = useCallback(() => current.current, []);
  const update = useCallback(
    (updater: ThreadStateUpdater) => {
      const next = updater(current.current);
      current.current = next;
      setState(next);
    },
    [],
  );
  const getMessages = useCallback(() => current.current.messages, []);
  const updateMessages = useCallback(
    (change: ChatMessage[] | ((previous: ChatMessage[]) => ChatMessage[])) => {
      update((previous) => ({
        ...previous,
        messages:
          typeof change === "function" ? change(previous.messages) : change,
      }));
    },
    [update],
  );

  function mergeHistory(historyMessages: ThreadMessageResponse[]) {
    const history = historyMessages.map(toChatMessage);
    const retained = getMessages().filter(
      (message) => message.type === "ai" && message.payload.type === "tool",
    );
    for (const activity of retained) {
      const activityRunId = chatMessageRunId(activity);
      const insertAt = history.findIndex(
        (message) =>
          message.type === "ai" &&
          message.payload.type === "text" &&
          chatMessageRunId(message) === activityRunId,
      );
      history.splice(insertAt === -1 ? history.length : insertAt, 0, activity);
    }
    return history;
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
    streamSmoother.resetRun(runId);
    interactionToolCalls.current.delete(runId);
    for (const storage of [
      toolArgumentBuffers.current,
      activeToolCalls.current,
      compoundChunkSignatures.current,
    ]) {
      for (const key of storage.keys()) {
        if (key.startsWith(`${runId}\u0000`)) storage.delete(key);
      }
    }
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

  function resolveToolCallIdentity(
    event: AgentRunStreamEvent,
    threadId: string | null,
    chunk: AIMessageChunk,
  ): ToolCallIdentity {
    const index = typeof chunk.index === "number" ? chunk.index : 0;
    const positionKey = [event.run_id, threadId ?? "", index].join("\u0000");
    const previous = activeToolCalls.current.get(positionKey);
    const toolCallId = asWireString(chunk.tool_call_id);
    const messageId = asWireString(chunk.message_id);
    const continuesPreviousMessage =
      !messageId || messageId === previous?.messageId;
    const identity: ToolCallIdentity = {
      toolCallId:
        toolCallId ??
        (continuesPreviousMessage ? previous?.toolCallId : undefined),
      messageId: messageId ?? previous?.messageId,
      index,
    };
    if (toolCallId || messageId) activeToolCalls.current.set(positionKey, identity);
    return identity;
  }

  function accumulateToolArguments(
    event: AgentRunStreamEvent,
    threadId: string | null,
    identity: ToolCallIdentity,
    chunk: AIMessageChunk,
  ): ToolCallArguments | undefined {
    if (chunk.args === undefined || chunk.args === null) return undefined;
    if (typeof chunk.args !== "string") return chunk.args;

    const key = [
      event.run_id,
      threadId ?? "",
      identity.toolCallId ?? identity.messageId ?? "tool",
      identity.index ?? 0,
    ].join("\u0000");
    let fragment = chunk.args;
    try {
      const decoded = JSON.parse(fragment) as unknown;
      if (typeof decoded !== "string") {
        toolArgumentBuffers.current.delete(key);
        return decoded as ToolCallArguments;
      }
      fragment = decoded;
    } catch {
      // LC v3 may already provide an undecorated string fragment.
    }

    const accumulated = `${toolArgumentBuffers.current.get(key) ?? ""}${fragment}`;
    toolArgumentBuffers.current.set(key, accumulated);
    const parsed = parseJsonValue(accumulated);
    if (parsed === undefined) return accumulated;
    toolArgumentBuffers.current.delete(key);
    return parsed;
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
              chatMessageId(message) === chunk.messageId &&
              chatMessageRunId(message) === chunk.runId &&
              chatMessageEvent(message)?.thread_id === chunk.threadId,
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
    identity: ToolCallIdentity,
    patch: Record<string, unknown>,
  ) {
    streamSmoother.flushThread(threadId);
    const matchesToolCall = (message: ChatMessage) => {
      const item = chatMessageEvent(message);
      if (
        message.type !== "ai" ||
        message.payload.type !== "tool" ||
        item?.type !== "tool_call" ||
        item.run_id !== event.run_id ||
        item.thread_id !== threadId
      )
        return false;
      const sameCallId =
        Boolean(identity.toolCallId) &&
        item.tool_call_id === identity.toolCallId;
      const sameMessagePosition =
        Boolean(identity.messageId) &&
        item.message_id === identity.messageId &&
        Number(item.index ?? 0) === (identity.index ?? 0);
      return sameCallId || sameMessagePosition;
    };
    const callKey = JSON.stringify([
      threadId,
      identity.toolCallId ?? identity.messageId,
      identity.index ?? 0,
    ]);
    if (patch.name === "ask_user") {
      // Later tool events omit the name, so retain the call ID for interaction routing.
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
        activity_id:
          currentEvent?.activity_id ??
          [
            event.run_id,
            threadId ?? "",
            identity.toolCallId ??
              `${identity.messageId ?? "tool"}:${identity.index ?? 0}`,
          ].join(":"),
        tool_call_id:
          identity.toolCallId ??
          currentEvent?.tool_call_id ??
          `${identity.messageId ?? "tool"}:${identity.index ?? 0}`,
        message_id: identity.messageId ?? currentEvent?.message_id,
        index: identity.index ?? currentEvent?.index,
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
    if (event.run_id !== runId) return;
    if (event.type === "end" || event.type === "interrupt") {
      streamSmoother.flushRun(runId);
      for (const storage of [
        toolArgumentBuffers.current,
        activeToolCalls.current,
        compoundChunkSignatures.current,
      ]) {
        for (const key of storage.keys()) {
          if (key.startsWith(`${runId}\u0000`)) storage.delete(key);
        }
      }
      if (event.type === "end") {
        updateMessages((messages) =>
          messages.map((message) => {
            const item = chatMessageEvent(message);
            if (message.payload.type !== "tool" || item?.type !== "tool_call" ||
                item.run_id !== runId || !["pending", "running"].includes(String(item.status)))
              return message;
            return {
              ...message,
              payload: {
                ...message.payload,
                event: {
                  ...item,
                  status: event.status === "cancelled" || event.status === "interrupted"
                    ? event.status : "stopped",
                },
              },
            };
          }),
        );
      }
      return;
    }
    if (isAgentRunMessagesEvent(event)) {
      const signatureKey = [event.run_id, event.thread_id ?? ""].join("\u0000");
      const flattened = messageChunks(
        event.items,
        compoundChunkSignatures.current.get(signatureKey),
      );
      if (flattened.compoundSignature)
        compoundChunkSignatures.current.set(
          signatureKey,
          flattened.compoundSignature,
        );
      else compoundChunkSignatures.current.delete(signatureKey);
      for (const delta of flattened.chunks) {
        if (!isRecord(delta)) continue;
        const threadId =
          typeof delta.thread_id === "string"
            ? delta.thread_id
            : event.thread_id;
        const toolChunk = toAIMessageChunk(delta);
        if (toolChunk) {
          const identity = resolveToolCallIdentity(event, threadId, toolChunk);
          const patch: Record<string, unknown> = {};
          const name = asWireString(toolChunk.name);
          if (name) patch.name = name;
          const args = accumulateToolArguments(
            event,
            threadId,
            identity,
            toolChunk,
          );
          if (args !== undefined) patch.args = args;
          upsertToolCall(event, threadId, identity, patch);
          continue;
        }
        if (delta.type !== "message_delta" || typeof delta.message_id !== "string")
          continue;
        const reasoning = [
          delta.reasoning_content_delta,
          delta.additional_kwargs_reasoning_content,
        ].find(
          (value): value is string =>
            typeof value === "string" && value.length > 0,
        );
        if (reasoning)
          appendReasoning(event, delta.message_id, threadId, reasoning);
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
      return;
    }
    if (event.type === "messages") return;
    if (event.type === "custom" && event.name === "agent_execute_event") {
      const execution = isRecord(event.event) ? event.event : null;
      const data = isRecord(execution?.stream_data) ? execution.stream_data : null;
      const toolCallId = asWireString(data?.tool_call_id);
      if (!data || !toolCallId) return;
      const patch: Record<string, unknown> = {};
      switch (data.event) {
        case "tool-started":
          patch.status = "running";
          if (typeof data.tool_name === "string" && data.tool_name) patch.name = data.tool_name;
          if (data.input !== undefined)
            patch.args = data.input;
          break;
        case "tool-output-delta":
          patch.output_deltas = [data.delta];
          break;
        case "tool-finished":
          patch.status = hasToolErrorStatus(data.output) ? "error" : "completed";
          patch.output = data.output;
          break;
        case "tool-error":
          patch.status = "error";
          patch.error = data.message;
          break;
        default:
          return;
      }
      upsertToolCall(
        event,
        event.thread_id,
        { toolCallId },
        patch,
      );
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
        item?.thread_id === event.thread_id &&
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

  function resetMessageRuntime() {
    streamSmoother.reset();
    interactionToolCalls.current.clear();
    toolArgumentBuffers.current.clear();
    activeToolCalls.current.clear();
    compoundChunkSignatures.current.clear();
  }

  function clearMessages() {
    resetMessageRuntime();
    updateMessages([]);
  }

  function setThread(thread: ThreadMetadataResponse | null) {
    update((previous) => ({ ...previous, thread }));
  }

  function clearThread() {
    setThread(null);
  }

  function setMessages(messages: ThreadMessageResponse[]) {
    update((previous) => ({
      ...previous,
      messages: mergeHistory(messages),
    }));
  }

  function resetThread() {
    resetMessageRuntime();
    update(() => initialThreadState());
  }

  return {
    state,
    getState,
    setThread,
    clearThread,
    setMessages,
    clearRunStreamMessages,
    applyRunMessageEvent,
    flushStream: streamSmoother.flushThread,
    flushRunStream: streamSmoother.flushRun,
    resetStream: streamSmoother.reset,
    clearMessages,
    addOptimisticMessage,
    removeOptimisticMessage,
    resetThread,
  };
}
