import { apiClient } from "@/api/client"
import type {
  ChatModelOption,
  ModelProvider,
  ModelProviderId,
  ModelProviderMetadata,
  SettingsModel,
} from "@/types/model"

export interface ChatModelListResponse {
  default_model: string
  fallback_model: string
  flash_model: string
  image_model: string
  models: ChatModelOption[]
}

export interface ModelSettingsRequest {
  base_url: string
  api_key?: string
  is_enabled: boolean
  models: SettingsModel[]
}

export interface ConnectionTestResult {
  success: boolean
  elapsed_ms: number
  error: string | null
  status_code: number | null
}

/**
 * 获取当前可用对话模型列表及各角色默认模型配置。
 * @returns 模型列表及默认、备用、快速、图像模型标识。
 */
export const listModels = () =>
  apiClient.apiGet<ChatModelListResponse>("/api/models", {
    requiresAuth: true
  })

/**
 * 获取所有模型供应商元数据列表。
 * @returns 模型供应商配置概览列表。
 */
export const listModelProviders = () =>
  apiClient.apiGet<ModelProviderMetadata[]>("/api/models/providers", modelRequestOptions())

/**
 * 获取指定模型供应商的详细配置。
 * @param id 模型供应商标识。
 * @returns 供应商详情及模型列表。
 */
export const getModelProvider = (id: ModelProviderId) =>
  apiClient.apiGet<ModelProvider>(`/api/models/providers/${id}`, modelRequestOptions())

/**
 * 保存指定模型供应商的配置与模型清单。
 * @param id 模型供应商标识。
 * @param body 供应商接入地址、密钥、启用状态及模型配置。
 * @returns 供应商标识及模型目录缓存是否已刷新。
 */
export const saveModelProvider = (id: ModelProviderId, body: ModelSettingsRequest) =>
  apiClient.apiPost<{ provider_id: string; cache_refreshed: boolean }, ModelSettingsRequest>(
    `/api/models/providers/${id}`, body, modelRequestOptions()
  )

/**
 * 从指定模型供应商远端发现可用模型列表。
 * @param id 模型供应商标识。
 * @param body 用于拉取模型目录的接入配置。
 * @returns 发现的模型配置列表。
 */
export const discoverProviderModels = (id: ModelProviderId, body: ModelSettingsRequest) =>
  apiClient.apiPost<SettingsModel[], ModelSettingsRequest>(
    `/api/models/providers/${id}/discover`, body, modelRequestOptions()
  )

/**
 * 测试与指定模型供应商的连通性。
 * @param id 模型供应商标识。
 * @param body 用于测试连接的接入配置。
 * @returns 测试结果、耗时、状态码及错误信息。
 */
export const testProviderConnection = (id: ModelProviderId, body: ModelSettingsRequest) =>
  apiClient.apiPost<ConnectionTestResult, ModelSettingsRequest>(
    `/api/models/providers/${id}/test`, body, modelRequestOptions()
  )

/**
 * 构建模型相关接口的默认鉴权请求选项。
 * @returns 包含 requiresAuth: true 的请求选项。
 */
function modelRequestOptions() {
  return { requiresAuth: true }
}
