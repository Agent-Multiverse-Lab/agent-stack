import { apiClient } from "@/api/client"
import type { ModelCatalogResponse } from "@/types/model"
import type { ConnectionTestResult, ModelProvider, ModelProviderSummary, ModelProviderId, ModelSettingsRequest, SettingsModel } from "@/types/model"

export const listModels = () =>
  apiClient.apiGet<ModelCatalogResponse>("/api/models", {
    requiresAuth: true
  })

export const listModelProviders = () =>
  apiClient.apiGet<ModelProviderSummary[]>("/api/models/providers", modelRequestOptions())

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
