export interface ChatModelOption {
  id: string
  name: string
  provider: string
  is_available: boolean
}

export type ModelProviderId = string
export type ModelCategory = "chat" | "embedding" | "rerank"
export type ChatCapability = "chat" | "vision" | "reasoning" | "tools" | "code" | "audio" | "video"

export interface SettingsModel {
  model_id: string
  category: ModelCategory
  capabilities: ChatCapability[]
}

export interface ModelProvider {
  provider_id: string
  name: string
  base_url: string
  embedding_base_url: string
  rerank_base_url: string
  is_enabled: boolean
  has_api_key: boolean
  models: SettingsModel[]
}
