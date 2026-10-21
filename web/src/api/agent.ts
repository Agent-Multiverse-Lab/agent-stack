import { apiClient } from "@/api/client"
import type { Agent, AgentContext } from "@/types/agent"

export interface AgentUpdateRequest {
  name?: string
  description?: string
  enabled?: boolean
}

export const listAgents = (signal?: AbortSignal) =>
  apiClient.apiGet<Agent[]>("/api/agent", {
    requiresAuth: true,
    signal,
  })

export const getAgentContext = (agentId: string, signal?: AbortSignal) =>
  apiClient.apiGet<AgentContext>(
    `/api/agent/${encodeURIComponent(agentId)}/context`,
    {
      requiresAuth: true,
      signal,
    }
  )

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
