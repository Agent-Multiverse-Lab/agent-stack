import { ref } from "vue"
import { defineStore } from "pinia"

import { listModels } from "@/api/model"
import type { ChatModelOption } from "@/types/model"

export const useModelStore = defineStore("model", () => {
  const models = ref<ChatModelOption[]>([])
  const selectedModelId = ref("")
  const loading = ref(false)

  const selectModel = (modelId: string) => {
    const model = models.value.find(
      (item) => item.id === modelId && item.is_available
    )
    if (model) selectedModelId.value = model.id
  }

  const loadModels = async () => {
    if (models.value.length > 0 || loading.value) return

    loading.value = true
    try {
      const catalog = await listModels()
      models.value = catalog.models

      const defaultModel = catalog.models.find(
        (model) => model.id === catalog.default_model && model.is_available
      ) ?? catalog.models.find(
        (model) => model.is_default && model.is_available
      ) ?? catalog.models.find((model) => model.is_available)

      selectedModelId.value = defaultModel?.id ?? ""
    } catch {
      models.value = []
      selectedModelId.value = ""
    } finally {
      loading.value = false
    }
  }

  void loadModels()

  return {
    models,
    selectedModelId,
    loading,
    loadModels,
    selectModel
  }
})
