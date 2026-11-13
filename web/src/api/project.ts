import { apiClient } from "@/api/client"

export interface ProjectResponse {
  project_id: string
  name: string
  pinned: boolean
  pinned_at: string | null
  created_at: string
  updated_at: string
}

/**
 * 获取当前用户的项目列表。
 * @returns 项目列表。
 */
export const listProjects = () =>
  apiClient.apiGet<ProjectResponse[]>("/api/projects", { requiresAuth: true })

/**
 * 创建一个新项目。
 * @param name 项目名称。
 * @returns 新创建的项目详情。
 */
export const createProject = (name: string) =>
  apiClient.apiPost<ProjectResponse, { name: string }>("/api/projects", { name }, { requiresAuth: true })

/**
 * 更新项目名称或置顶状态。
 * @param projectId 项目的对外 UUID。
 * @param fields 需要更新的项目字段。
 * @returns 更新后的项目详情。
 */
export const updateProject = async (projectId: string, fields: { name?: string; pinned?: boolean }): Promise<ProjectResponse> => {
  const response = await apiClient.apiFetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH", requiresAuth: true,
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields),
  })
  return response.json()
}

/**
 * 软删除指定项目，并将其下会话转为未归属状态。
 * @param projectId 项目的对外 UUID。
 * @returns 删除完成后的空响应。
 */
export const deleteProject = (projectId: string) =>
  apiClient.apiDelete(`/api/projects/${encodeURIComponent(projectId)}`, { requiresAuth: true })
