export type ModelProviderId = string
export type ModelProtocol = "openai_compatible" | "anthropic" | "gemini"
export type ModelCategory = "chat" | "embedding" | "rerank"
export type ChatCapability = "chat" | "vision" | "reasoning" | "tools" | "code" | "audio" | "video"

export interface ModelCatalogItem {
  model_id: string
  category: ModelCategory
  capabilities: ChatCapability[]
}

export interface ProviderModelCatalogEntry {
  provider_id: string
  display_name: string
  models: ModelCatalogItem[]
}

export type ModelCatalog = Record<string, ProviderModelCatalogEntry>

export interface ModelApiResponse<T> {
  status: "success"
  data: T
}

export interface ChatModelOption {
  id: string
  model_id: string
  name: string
  provider: string
  provider_name: string
  capabilities: ChatCapability[]
  is_available: boolean
}

export interface SettingsModel {
  model_id: string
  category: ModelCategory
  capabilities: ChatCapability[]
}

export interface ModelProvider {
  provider_id: string
  name: string
  protocol?: ModelProtocol
  base_url: string
  embedding_base_url: string
  rerank_base_url: string
  is_enabled: boolean
  has_api_key: boolean
  models: SettingsModel[]
}
