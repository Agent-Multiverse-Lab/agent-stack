import { apiClient } from "@/api/client";
import type { ThreadMessageAttachmentResponse } from "@/api/attachment";
import type {
  InteractionRequiredResponse,
  ThreadRunMetadataResponse,
} from "@/api/agent-run";
import type { Agent } from "@/types/agent";

export interface ThreadMetadataResponse {
  thread_id: string;
  title: string;
  project_id: string | null;
  pinned: boolean;
  pinned_at: string | null;
  summary: string | null;
  agent_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ThreadResponse extends ThreadMetadataResponse {
  uid: string;
}

export interface ThreadMessageResponse {
  message_id: number;
  role: string;
  content: string;
  reasoning_content?: string;
  tool_calls?: {
    tool_call_id: string;
    name: string;
    args: Record<string, unknown>;
    status: string;
    output: unknown;
    error: string | null;
  }[];
  agent_state?: { agent_todo: { content: string; status: string }[] } | null;
  image_content: string | null;
  message_type: string;
  status: string;
  request_id: string | null;
  run: ThreadRunMetadataResponse | null;
  attachments: ThreadMessageAttachmentResponse[];
  // 消息计时：顺序、观察时间与单调耗时。
  // 后端一定返回；乐观消息与历史记录可能没有，因此保持可选。
  sequence?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  execution_status?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ThreadDetailResponse {
  thread: ThreadMetadataResponse;
  messages: ThreadMessageResponse[];
  next_before_message_id: number | null;
  active_run: ThreadRunMetadataResponse | null;
  pending_interaction: InteractionRequiredResponse | null;
}

export interface ThreadListResponse {
  items: ThreadMetadataResponse[];
  next_cursor: string | null;
  has_more: boolean;
}

interface CreateThreadRequest {
  agent_id: string;
  project_id?: string;
  metadata: Record<string, unknown>;
}

export const listChatAgents = () =>
  apiClient.apiGet<Agent[]>("/api/chat/agents", {
    requiresAuth: true,
  });

export const listThreads = (options?: {
  query?: string;
  cursor?: string;
  limit?: number;
  project_id?: string;
  unassigned?: boolean;
  pinned?: boolean;
}) => {
  const params = new URLSearchParams();
  if (options?.query) params.set("q", options.query);
  if (options?.cursor) params.set("cursor", options.cursor);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.project_id !== undefined) params.set("project_id", options.project_id);
  if (options?.unassigned) params.set("unassigned", "true");
  if (options?.pinned !== undefined) params.set("pinned", String(options.pinned));
  const queryString = params.toString();
  const path = queryString
    ? `/api/chat/thread?${queryString}`
    : "/api/chat/thread";
  return apiClient.apiGet<ThreadListResponse>(path, {
    requiresAuth: true,
  });
};

export const updateThread = async (
  threadId: string,
  fields: { title?: string; project_id?: string | null; pinned?: boolean },
): Promise<ThreadMetadataResponse> => {
  const response = await apiClient.apiFetch(
    `/api/chat/thread/${encodeURIComponent(threadId)}`,
    {
      method: "PATCH",
      requiresAuth: true,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    },
  );
  return response.json();
};

export const renameThread = (threadId: string, title: string) => updateThread(threadId, { title });

export const generateThreadTitle = (threadId: string, query: string) =>
  apiClient.apiPost<{ title: string }, { query: string }>(
    `/api/chat/thread/${encodeURIComponent(threadId)}/title-suggestion`,
    { query: query.replace(/\s+/g, " ").trim().slice(0, 2000) },
    { requiresAuth: true },
  );

export const deleteThread = (threadId: string) =>
  apiClient.apiDelete(`/api/chat/thread/${encodeURIComponent(threadId)}`, {
    requiresAuth: true,
  });

export const createThread = (agentId: string, modelId?: string, projectId?: string) =>
  apiClient.apiPost<ThreadResponse, CreateThreadRequest>(
    "/api/chat/thread",
    { agent_id: agentId, metadata: modelId ? { model: modelId } : {}, project_id: projectId },
    { requiresAuth: true },
  );

export const getThreadDetail = (threadId: string) =>
  apiClient.apiGet<ThreadDetailResponse>(
    `/api/chat/thread/${encodeURIComponent(threadId)}`,
    { requiresAuth: true },
  );
