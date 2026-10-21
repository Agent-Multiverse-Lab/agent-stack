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

export const listModels = () =>
  apiClient.apiGet<ChatModelListResponse>("/api/models", {
    requiresAuth: true
  })

export const listModelProviders = () =>
  apiClient.apiGet<ModelProviderMetadata[]>("/api/models/providers", modelRequestOptions())

export const getModelProvider = (id: ModelProviderId) =>
  apiClient.apiGet<ModelProvider>(`/api/models/providers/${id}`, modelRequestOptions())

export const saveModelProvider = (id: ModelProviderId, body: ModelSettingsRequest) =>
  apiClient.apiPost<{ provider_id: string; cache_refreshed: boolean }, ModelSettingsRequest>(
    `/api/models/providers/${id}`, body, modelRequestOptions()
  )

export const discoverProviderModels = (id: ModelProviderId, body: ModelSettingsRequest) =>
  apiClient.apiPost<SettingsModel[], ModelSettingsRequest>(
    `/api/models/providers/${id}/discover`, body, modelRequestOptions()
  )

export const testProviderConnection = (id: ModelProviderId, body: ModelSettingsRequest) =>
  apiClient.apiPost<ConnectionTestResult, ModelSettingsRequest>(
    `/api/models/providers/${id}/test`, body, modelRequestOptions()
  )

function modelRequestOptions() {
  return { requiresAuth: true }
}
