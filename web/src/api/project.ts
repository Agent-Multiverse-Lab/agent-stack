import { apiClient } from "@/api/client"

export interface ProjectResponse {
  project_id: string
  name: string
  pinned: boolean
  pinned_at: string | null
  created_at: string
  updated_at: string
}

export const listProjects = () =>
  apiClient.apiGet<ProjectResponse[]>("/api/projects", { requiresAuth: true })

export const createProject = (name: string) =>
  apiClient.apiPost<ProjectResponse, { name: string }>("/api/projects", { name }, { requiresAuth: true })

export const updateProject = async (projectId: string, fields: { name?: string; pinned?: boolean }): Promise<ProjectResponse> => {
  const response = await apiClient.apiFetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH", requiresAuth: true,
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields),
  })
  return response.json()
}

export const deleteProject = (projectId: string) =>
  apiClient.apiDelete(`/api/projects/${encodeURIComponent(projectId)}`, { requiresAuth: true })
