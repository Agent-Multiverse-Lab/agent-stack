import { apiClient } from "@/api/client"
import i18n from "@/i18n"
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
  if (window.location.protocol !== "https:") throw new Error(i18n.t("Model settings require HTTPS"))
  return { requiresAuth: true }
}
