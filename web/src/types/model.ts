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

export type ModelProviderId = string
export type ChatCapability = "chat" | "vision" | "reasoning" | "tools" | "code" | "audio" | "video"

export interface SettingsModel {
  model_id: string
  capabilities: ChatCapability[]
}

export interface ModelProviderMetadata {
  provider_id: string
  name: string
  is_enabled: boolean
  has_api_key: boolean
}

export interface ModelProvider extends ModelProviderMetadata {
  base_url: string
  protocol: "openai_compatible"
  enabled_models: SettingsModel[]
}
