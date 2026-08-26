import { apiClient } from "@/api/client"
import type { ModelCatalogResponse } from "@/types/model"

export const listModels = () =>
  apiClient.apiGet<ModelCatalogResponse>("/api/models", {
    requiresAuth: true
  })
