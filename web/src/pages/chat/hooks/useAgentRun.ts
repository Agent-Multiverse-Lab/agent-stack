import { useCallback, useRef, useState } from "react";

import {
  buildAgentRunStreamUrl,
  cancelAgentRun,
  consumeAgentRunStream,
  createAgentRun,
  resumeAgentRun,
} from "@/api/agent-run";
import type {
  AgentRunCreateRequest,
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

/** 创建空的 Run 状态，供 Hook 初始化和切换会话时重置。 */
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
/** 判断 Run 是否仍需等待执行结果，包含已请求取消但尚未结束的情况。 */
const isActiveStatus = (status: string | null) =>
  Boolean(status && activeStatuses.has(status));

/** 将后端开始时间转换为毫秒时间戳，缺失或无法解析时返回 null。 */
const parseStartedAt = (value: unknown): number | null => {
  const timestamp = typeof value === "string" ? Date.parse(value) : NaN;
  return Number.isFinite(timestamp) ? timestamp : null;
};

/** 检查流事件中的问题和选项结构，确认其可交给提问组件展示。 */
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

/** 识别携带父 Run ID 和有效问题列表的 ask_user 打断事件。 */
const isInteractionRequiredEvent = (
  event: AgentRunStreamEvent,
): event is AgentRunStreamEvent & InteractionRequired & { type: "interrupt" } =>
  event.type === "interrupt" &&
  event.name === "ask_user" &&
  typeof event.created_by_run_id === "string" &&
  Array.isArray(event.questions) &&
  event.questions.length > 0 &&
  event.questions.every(isHumanQuestion);

/** 管理当前会话的 Run 状态、待回答交互，以及创建、恢复、订阅和取消操作。 */
export function useAgentRun() {
  const [state, setState] = useState<RunState>(initialState);
  const current = useRef(state);
  const version = useRef(0);

  /** 从 ref 读取最新状态，供异步流程判断响应是否仍属于当前 Run。 */
  const getState = useCallback(() => current.current, []);
  /** 判断当前 Run 是否处于 pending、running 或 cancel_requested 状态。 */
  const isActive = useCallback(
    () => isActiveStatus(current.current.runStatus),
    [],
  );
  /** 同步更新异步流程读取的状态 ref 和驱动页面渲染的 React state。 */
  const update = useCallback((updater: RunStateUpdater) => {
    const next = updater(current.current);
    current.current = next;
    setState(next);
  }, []);

  /**
   * 提交正文、附件和模型选择，记录返回的 Run ID、状态及订阅地址。
   * 操作版本避免过期响应覆盖当前状态；返回创建结果，由页面加载消息和订阅事件。
   */
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

  /** 提交父 Run 的回答，切换到新 Resume Run，并清除已提交的待回答交互。 */
  async function resumeRun(
    createdByRunId: string,
    request: AgentRunCreateRequest,
  ) {
    const expected = ++version.current;
    update((previous) => ({ ...previous, resuming: true }));
    try {
      const run = await resumeAgentRun(createdByRunId, request);
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

  /**
   * 从会话详情恢复 Run 和待回答交互，优先采用 active_run，再采用消息中的最近 Run。
   * 仅为活动 Run 重建订阅地址，并将它返回给页面决定是否重新连接事件流。
   */
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

  /**
   * 订阅当前活动 Run，更新运行状态与提问信息，并将事件交给页面合并消息。
   * 终态事件也交给页面处理，随后清除订阅地址；无可订阅 Run 时返回 null。
   */
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
            // pending 可能尚无开始时间；事件重放时保留已知开始时间。
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
            created_by_run_id: event.created_by_run_id,
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

  /** 请求取消当前活动 Run，防止重复点击，并忽略已切换 Run 的迟到响应。 */
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

  /** 清空本地 Run 状态并使在途操作失效，后台执行是否停止由取消接口决定。 */
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
