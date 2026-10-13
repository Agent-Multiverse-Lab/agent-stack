export interface ChatModelOption {
  id: string
  name: string
  display_name: string
  version: string
  provider: string
  icon: string
  is_available: boolean
  is_default: boolean
  is_fallback: boolean
  is_flash: boolean
}

export interface ModelCatalogResponse {
  default_model: string
  fallback_model: string
  flash_model: string
  image_model: string
  models: ChatModelOption[]
}

export type ModelProviderId = "deepseek" | "qwen"
export type ChatCapability = "chat" | "vision" | "reasoning" | "tools" | "code" | "audio" | "video"

export interface SettingsModel {
  model_id: string
  capabilities: ChatCapability[]
}

export interface ModelProviderSummary {
  provider_id: string
  name: string
  is_enabled: boolean
  has_api_key: boolean
}

export interface ModelProvider extends ModelProviderSummary {
  base_url: string
  enabled_models: SettingsModel[]
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
