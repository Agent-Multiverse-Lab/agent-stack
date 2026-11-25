import { apiClient } from "@/api/client"
import type {
  ModelApiResponse,
  ModelCatalog,
  ModelCategory,
  ModelProtocol,
  ModelProvider,
  ModelProviderId,
  SettingsModel,
} from "@/types/model"

export interface ModelSettingsRequest {
  base_url: string
  embedding_base_url: string
  rerank_base_url: string
  api_key?: string
  is_enabled: boolean
  models: SettingsModel[]
}

export interface CreateModelProviderRequest extends ModelSettingsRequest {
  provider_id: string
  name: string
  protocol: ModelProtocol
}

export interface ConnectionTestResult {
  success: boolean
  elapsed_ms: number
  error: string | null
  status_code: number | null
}

async function unwrapModelResponse<T>(
  request: Promise<ModelApiResponse<T>>
): Promise<T> {
  const response = await request
  return response.data
}

/**
 * 按分类获取已启用的脱敏模型目录（按厂商分组）。
 * @param category 模型分类，默认 chat。
 * @returns 以 provider_id 为键的模型目录映射。
 */
export const listModels = (category: ModelCategory = "chat") =>
  unwrapModelResponse(
    apiClient.apiGet<ModelApiResponse<ModelCatalog>>(
      `/api/models?category=${encodeURIComponent(category)}`,
      modelRequestOptions()
    )
  )

/**
 * 获取所有模型供应商配置列表。
 * @returns 模型供应商配置列表。
 */
export const listModelProviders = () =>
  unwrapModelResponse(
    apiClient.apiGet<ModelApiResponse<ModelProvider[]>>(
      "/api/models/providers",
      modelRequestOptions()
    )
  )

/**
 * 获取指定模型供应商的详细配置。
 * @param id 模型供应商标识。
 * @returns 供应商详情及模型列表。
 */
export const getModelProvider = (id: ModelProviderId) =>
  unwrapModelResponse(
    apiClient.apiGet<ModelApiResponse<ModelProvider>>(
      `/api/models/providers/${id}`,
      modelRequestOptions()
    )
  )

/**
 * 创建新的平台模型供应商配置。
 * @param body 供应商标识、展示名、协议、地址、密钥及启用状态。
 * @returns 供应商标识及模型目录缓存是否已刷新。
 */
export const createModelProvider = (body: CreateModelProviderRequest) =>
  unwrapModelResponse(
    apiClient.apiPost<
      ModelApiResponse<{ provider_id: string; cache_refreshed: boolean }>,
      CreateModelProviderRequest
    >("/api/models/providers", body, modelRequestOptions())
  )

/**
 * 保存指定模型供应商的配置与模型清单。
 * @param id 模型供应商标识。
 * @param body 供应商接入地址、密钥、启用状态及模型配置。
 * @returns 供应商标识及模型目录缓存是否已刷新。
 */
export const saveModelProvider = (id: ModelProviderId, body: ModelSettingsRequest) =>
  unwrapModelResponse(
    apiClient.apiPost<
      ModelApiResponse<{ provider_id: string; cache_refreshed: boolean }>,
      ModelSettingsRequest
    >(`/api/models/providers/${id}`, body, modelRequestOptions())
  )

/**
 * 删除指定模型供应商。
 * @param id 模型供应商标识。
 * @returns 供应商标识及模型目录缓存是否已刷新。
 */
export const deleteModelProvider = (id: ModelProviderId) =>
  unwrapModelResponse(
    apiClient.apiDelete<
      ModelApiResponse<{ provider_id: string; cache_refreshed: boolean }>
    >(`/api/models/providers/${id}`, modelRequestOptions())
  )

/**
 * 从指定模型供应商远端发现可用模型列表。
 * @param id 模型供应商标识。
 * @param body 用于拉取模型目录的接入配置。
 * @returns 发现的模型配置列表。
 */
export const discoverProviderModels = (id: ModelProviderId, body: ModelSettingsRequest) =>
  unwrapModelResponse(
    apiClient.apiPost<ModelApiResponse<SettingsModel[]>, ModelSettingsRequest>(
      `/api/models/providers/${id}/discover`,
      body,
      modelRequestOptions()
    )
  )

/**
 * 测试与指定模型供应商的连通性。
 * @param id 模型供应商标识。
 * @param body 用于测试连接的接入配置。
 * @returns 测试结果、耗时、状态码及错误信息。
 */
export const testProviderConnection = (id: ModelProviderId, body: ModelSettingsRequest) =>
  unwrapModelResponse(
    apiClient.apiPost<ModelApiResponse<ConnectionTestResult>, ModelSettingsRequest>(
      `/api/models/providers/${id}/test`,
      body,
      modelRequestOptions()
    )
  )

/**
 * 构建模型相关接口的默认鉴权请求选项。
 * @returns 包含 requiresAuth: true 的请求选项。
 */
function modelRequestOptions() {
  return { requiresAuth: true }
}
