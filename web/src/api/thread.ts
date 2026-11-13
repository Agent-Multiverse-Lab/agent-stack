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

/**
 * 获取当前可用于发起会话的 Agent 列表。
 * @returns 可选 Agent 列表。
 */
export const listChatAgents = () =>
  apiClient.apiGet<Agent[]>("/api/chat/agents", {
    requiresAuth: true,
  });

/**
 * 分页查询当前用户的会话列表，支持关键词、项目归属和置顶过滤。
 * @param options 查询与过滤选项（query、cursor、limit、project_id、unassigned、pinned）。
 * @returns 会话列表及游标分页信息。
 */
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

/**
 * 更新会话标题、所属项目或置顶状态。
 * @param threadId 会话 ID。
 * @param fields 需要更新的字段，project_id 传 null 表示移出项目。
 * @returns 更新后的会话元数据。
 */
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

/**
 * 重命名指定会话的标题。
 * @param threadId 会话 ID。
 * @param title 新的会话标题。
 * @returns 更新后的会话元数据。
 */
export const renameThread = (threadId: string, title: string) => updateThread(threadId, { title });

/**
 * 根据首轮用户输入为会话生成建议标题。
 * @param threadId 会话 ID。
 * @param query 用于生成标题的用户输入文本。
 * @returns 生成的标题对象。
 */
export const generateThreadTitle = (threadId: string, query: string) =>
  apiClient.apiPost<{ title: string }, { query: string }>(
    `/api/chat/thread/${encodeURIComponent(threadId)}/title-suggestion`,
    { query: query.replace(/\s+/g, " ").trim().slice(0, 2000) },
    { requiresAuth: true },
  );

/**
 * 软删除指定会话及其关联子对话。
 * @param threadId 会话 ID。
 * @returns 删除完成后的空响应。
 */
export const deleteThread = (threadId: string) =>
  apiClient.apiDelete(`/api/chat/thread/${encodeURIComponent(threadId)}`, {
    requiresAuth: true,
  });

/**
 * 创建新会话。
 * @param agentId 绑定的 Agent 标识。
 * @param modelId 可选的模型标识，写入会话初始 metadata。
 * @param projectId 可选的归属项目 UUID。
 * @returns 新建会话的完整元数据。
 */
export const createThread = (agentId: string, modelId?: string, projectId?: string) =>
  apiClient.apiPost<ThreadResponse, CreateThreadRequest>(
    "/api/chat/thread",
    { agent_id: agentId, metadata: modelId ? { model: modelId } : {}, project_id: projectId },
    { requiresAuth: true },
  );

/**
 * 获取指定会话的详情、历史消息、活跃 Run 及待处理交互。
 * @param threadId 会话 ID。
 * @returns 会话详情响应数据。
 */
export const getThreadDetail = (threadId: string) =>
  apiClient.apiGet<ThreadDetailResponse>(
    `/api/chat/thread/${encodeURIComponent(threadId)}`,
    { requiresAuth: true },
  );
