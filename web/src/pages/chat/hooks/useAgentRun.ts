import { useCallback, useRef, useState } from "react";

import {
  buildAgentRunStreamUrl,
  cancelAgentRun,
  consumeAgentRunStream,
  createAgentRun,
  resumeAgentRun,
} from "@/api/agent-run";
import type {
  AgentRunResumeRequest,
  AgentRunStreamEvent,
  ThreadRunMetadataResponse,
} from "@/api/agent-run";
import type { ThreadDetailResponse } from "@/api/thread";
import type {
  AgentRunCreateInput,
  HumanQuestion,
  InteractionRequired,
} from "@/pages/chat/types";

interface RunState {
  runId: string | null;
  runStatus: string | null;
  startedAt: number | null;
  streamUrl: string | null;
  pendingInteraction: InteractionRequired | null;
  cancelling: boolean;
  resuming: boolean;
}

type RunStateUpdater = (previous: RunState) => RunState;

const initialState = (): RunState => ({
  runId: null,
  runStatus: null,
  startedAt: null,
  streamUrl: null,
  pendingInteraction: null,
  cancelling: false,
  resuming: false,
});

const activeStatuses = new Set(["pending", "running", "cancel_requested"]);
const isActiveStatus = (status: string | null) =>
  Boolean(status && activeStatuses.has(status));

const parseStartedAt = (value: unknown): number | null => {
  const timestamp = typeof value === "string" ? Date.parse(value) : NaN;
  return Number.isFinite(timestamp) ? timestamp : null;
};

const isHumanQuestion = (value: unknown): value is HumanQuestion =>
  typeof value === "object" &&
  value !== null &&
  "question_id" in value &&
  typeof value.question_id === "string" &&
  "question" in value &&
  typeof value.question === "string" &&
  "options" in value &&
  Array.isArray(value.options) &&
  value.options.every(
    (option: unknown) =>
      typeof option === "object" &&
      option !== null &&
      "label" in option &&
      typeof option.label === "string" &&
      "value" in option &&
      typeof option.value === "string",
  );

const isInteractionRequiredEvent = (
  event: AgentRunStreamEvent,
): event is AgentRunStreamEvent & InteractionRequired & { type: "interrupt" } =>
  event.type === "interrupt" &&
  event.name === "ask_user" &&
  typeof event.parent_run_id === "string" &&
  Array.isArray(event.questions) &&
  event.questions.length > 0 &&
  event.questions.every(isHumanQuestion);

export function useAgentRun() {
  const [state, setState] = useState<RunState>(initialState);
  const current = useRef(state);
  const version = useRef(0);

  const getState = useCallback(() => current.current, []);
  const isActive = useCallback(
    () => isActiveStatus(current.current.runStatus),
    [],
  );
  const update = useCallback((updater: RunStateUpdater) => {
    const next = updater(current.current);
    current.current = next;
    setState(next);
  }, []);

  async function createRun(request: AgentRunCreateInput) {
    const expected = ++version.current;
    const run = await createAgentRun(
      request.query,
      request.agentId,
      request.threadId,
      request.attachmentFileIds,
      request.modelId,
    );
    if (version.current === expected) {
      update((previous) => ({
        ...previous,
        runId: run.run_id,
        runStatus: run.status,
        startedAt: null,
        streamUrl: run.stream_url,
        cancelling: false,
        pendingInteraction: null,
      }));
    }
    return run;
  }

  async function resumeRun(
    parentRunId: string,
    request: AgentRunResumeRequest,
  ) {
    const expected = ++version.current;
    update((previous) => ({ ...previous, resuming: true }));
    try {
      const run = await resumeAgentRun(parentRunId, request);
      if (version.current === expected) {
        update((previous) => ({
          ...previous,
          runId: run.run_id,
          runStatus: run.status,
          startedAt: null,
          streamUrl: run.stream_url,
          pendingInteraction: null,
          cancelling: false,
        }));
      }
      return run;
    } finally {
      if (version.current === expected)
        update((previous) => ({ ...previous, resuming: false }));
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
    update((previous) => ({
      ...previous,
      pendingInteraction: detail.pending_interaction,
      runId: restored?.run_id ?? null,
      runStatus: restored?.status ?? null,
      startedAt:
        parseStartedAt(restored?.started_at) ??
        (previous.runId === restored?.run_id ? previous.startedAt : null),
      streamUrl: activeRun
        ? buildAgentRunStreamUrl(activeRun.run_id, detail.thread.thread_id)
        : null,
      cancelling:
        previous.runId === restored?.run_id ? previous.cancelling : false,
    }));
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
          const runStatus = event.status;
          update((previous) => ({
            ...previous,
            runStatus,
            // Pending runs may not have a persisted start yet; replay must not reset it.
            startedAt:
              previous.startedAt ??
              (runStatus === "running"
                ? parseStartedAt(event.created_at)
                : null),
          }));
        }
        if (isInteractionRequiredEvent(event)) {
          const pendingInteraction: InteractionRequired = {
            name: event.name,
            parent_run_id: event.parent_run_id,
            questions: event.questions,
          };
          update((previous) => ({
            ...previous,
            pendingInteraction,
          }));
        }
        await onMessageEvent(event);
      },
    );
    if (getState().runId === runId) {
      await onMessageEvent(endEvent);
      if (getState().runId === runId) {
        update((previous) => ({
          ...previous,
          runStatus: endEvent.status,
          streamUrl: null,
        }));
      }
    }
    return endEvent;
  }

  async function cancelCurrentRun() {
    const { runId, cancelling } = getState();
    if (!runId || cancelling || !isActive()) return;
    update((previous) => ({ ...previous, cancelling: true }));
    try {
      const response = await cancelAgentRun(runId);
      const latest = getState();
      if (latest.runId === runId && isActiveStatus(latest.runStatus)) {
        update((previous) => ({
          ...previous,
          runStatus: response.status,
        }));
      }
    } catch (error) {
      const latest = getState();
      if (latest.runId === runId && isActiveStatus(latest.runStatus)) {
        throw error;
      }
    } finally {
      if (getState().runId === runId)
        update((previous) => ({ ...previous, cancelling: false }));
    }
  }

  function clearRun() {
    version.current += 1;
    update(() => initialState());
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
