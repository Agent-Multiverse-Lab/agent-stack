import { apiClient } from "@/api/client"
import type {
  SandboxFileContentResponse,
  SandboxWorkspaceResponse,
} from "@/pages/sandbox/types"

export const listSandboxWorkspace = (threadId: string, path = "/workspace") => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  return apiClient.apiGet<SandboxWorkspaceResponse>(
    `/api/sandbox/workspace?${params.toString()}`,
    { requiresAuth: true }
  )
}

export const readSandboxFile = (threadId: string, path: string) => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  return apiClient.apiGet<SandboxFileContentResponse>(
    `/api/sandbox/workspace/content?${params.toString()}`,
    { requiresAuth: true }
  )
}
