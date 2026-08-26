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
