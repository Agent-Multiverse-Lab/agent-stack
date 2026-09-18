import { useCallback, useRef, useState } from "react";

import {
  buildAgentRunStreamUrl,
  cancelAgentRun,
  consumeAgentRunStream,
  createAgentRun,
  resumeAgentRun,
} from "@/api/agent";
import type {
  AgentRunResumeRequest,
  AgentRunStreamEvent,
  InteractionRequired,
  ThreadDetailResponse,
  ThreadRunMetadataResponse,
} from "@/types/chat";

interface RunState {
  runId: string | null;
  runStatus: string | null;
  streamUrl: string | null;
  pendingInteraction: InteractionRequired | null;
  cancelling: boolean;
  resuming: boolean;
}

interface AgentRunCreateRequest {
  query: string;
  agentId: string;
  threadId: string;
  attachmentFileIds: string[];
  modelId?: string;
}

const initialState = (): RunState => ({
  runId: null,
  runStatus: null,
  streamUrl: null,
  pendingInteraction: null,
  cancelling: false,
  resuming: false,
});

const activeStatuses = new Set(["pending", "running", "cancel_requested"]);
const isActiveStatus = (status: string | null) =>
  Boolean(status && activeStatuses.has(status));

export function useAgentRun() {
  const [state, setState] = useState<RunState>(initialState);
  const current = useRef(state);
  const version = useRef(0);

  const getState = useCallback(() => current.current, []);
  const isActive = useCallback(
    () => isActiveStatus(current.current.runStatus),
    [],
  );
  const update = useCallback((change: Partial<RunState>) => {
    const next = { ...current.current, ...change };
    current.current = next;
    setState(next);
  }, []);

  async function createRun(request: AgentRunCreateRequest) {
    const expected = ++version.current;
    const run = await createAgentRun(
      request.query,
      request.agentId,
      request.threadId,
      request.attachmentFileIds,
      request.modelId,
    );
    if (version.current === expected) {
      update({
        runId: run.run_id,
        runStatus: run.status,
        streamUrl: run.stream_url,
        cancelling: false,
        pendingInteraction: null,
      });
    }
    return run;
  }

  async function resumeRun(
    parentRunId: string,
    request: AgentRunResumeRequest,
  ) {
    const expected = ++version.current;
    update({ resuming: true });
    try {
      const run = await resumeAgentRun(parentRunId, request);
      if (version.current === expected) {
        update({
          runId: run.run_id,
          runStatus: run.status,
          streamUrl: run.stream_url,
          pendingInteraction: null,
          cancelling: false,
        });
      }
      return run;
    } finally {
      if (version.current === expected) update({ resuming: false });
    }
  }

  function restoreRunFromThread(
    detail: ThreadDetailResponse,
  ): ThreadRunMetadataResponse | null {
    version.current += 1;
    const latestRun =
      [...detail.messages].reverse().find((message) => message.run)?.run ??
      null;
    const activeRun = detail.active_run;
    const restored = activeRun ?? latestRun;
    update({
      pendingInteraction: detail.pending_interaction,
      runId: restored?.run_id ?? null,
      runStatus: restored?.status ?? null,
      streamUrl: activeRun
        ? buildAgentRunStreamUrl(activeRun.run_id, detail.thread.thread_id)
        : null,
      cancelling:
        getState().runId === restored?.run_id ? getState().cancelling : false,
    });
    return activeRun;
  }

  async function consumeRunStream(
    signal: AbortSignal,
    onMessageEvent: (event: AgentRunStreamEvent) => void | Promise<void>,
  ) {
    const { runId, streamUrl } = getState();
    if (!runId || !streamUrl || !isActive()) return null;
    const endEvent = await consumeAgentRunStream(
      streamUrl,
      signal,
      async (event) => {
        if (getState().runId !== runId) return;
        if (event.type === "status" && typeof event.status === "string") {
          update({ runStatus: event.status });
          return;
        }
        if (
          event.type === "interaction_required" &&
          event.kind === "ask_user" &&
          typeof event.parent_run_id === "string" &&
          Array.isArray(event.questions) &&
          event.questions.length > 0 &&
          event.questions.every(
            (question) =>
              question &&
              typeof question.question_id === "string" &&
              typeof question.question === "string" &&
              Array.isArray(question.options) &&
              question.options.every(
                (option: unknown) =>
                  typeof option === "object" &&
                  option !== null &&
                  "label" in option &&
                  typeof option.label === "string" &&
                  "value" in option &&
                  typeof option.value === "string",
              ),
          )
        ) {
          update({
            pendingInteraction: {
              kind: "ask_user",
              parent_run_id: event.parent_run_id,
              questions: event.questions,
            },
          });
          return;
        }
        await onMessageEvent(event);
      },
    );
    if (getState().runId === runId) {
      update({ runStatus: endEvent.status, streamUrl: null });
    }
    return endEvent;
  }

  async function cancelCurrentRun() {
    const { runId, cancelling } = getState();
    if (!runId || cancelling || !isActive()) return;
    update({ cancelling: true });
    try {
      const response = await cancelAgentRun(runId);
      if (getState().runId === runId) update({ runStatus: response.status });
    } catch (error) {
      if (getState().runId === runId) throw error;
    } finally {
      if (getState().runId === runId) update({ cancelling: false });
    }
  }

  function clearRun() {
    version.current += 1;
    update(initialState());
  }

  return {
    state,
    getState,
    isActive,
    createRun,
    resumeRun,
    restoreRunFromThread,
    consumeRunStream,
    cancelCurrentRun,
    clearRun,
  };
}
