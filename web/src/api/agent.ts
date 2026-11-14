import { apiClient } from "@/api/client"
import type { Agent, AgentContext } from "@/types/agent"

export interface AgentUpdateRequest {
  name?: string
  description?: string
  enabled?: boolean
}

/**
 * 获取当前可用的 Agent 列表。
 * @param signal 可选的中断信号，用于取消请求。
 * @returns Agent 配置列表。
 */
export const listAgents = (signal?: AbortSignal) =>
  apiClient.apiGet<Agent[]>("/api/agent", {
    requiresAuth: true,
    signal,
  })

/**
 * 获取指定 Agent 的上下文详情。
 * @param agentId Agent 唯一标识。
 * @param signal 可选的中断信号，用于取消请求。
 * @returns Agent 的上下文配置与提示词等信息。
 */
export const getAgentContext = (agentId: string, signal?: AbortSignal) =>
  apiClient.apiGet<AgentContext>(
    `/api/agent/${encodeURIComponent(agentId)}/context`,
    {
      requiresAuth: true,
      signal,
    }
  )

/**
 * 更新指定 Agent 的名称、描述或启用状态。
 * @param agentId Agent 唯一标识。
 * @param request 需要修改的 Agent 字段。
 * @returns 更新后的 Agent 信息。
 */
export const updateAgent = async (
  agentId: string,
  request: AgentUpdateRequest
): Promise<Agent> => {
  const response = await apiClient.apiFetch(
    `/api/agent/${encodeURIComponent(agentId)}`,
    {
      method: "PATCH",
      requiresAuth: true,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  )
  return response.json()
}
