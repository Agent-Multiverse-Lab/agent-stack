import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"

import { listModels } from "@/api/model"
import { useAuth } from "@/context/AuthContext"
import type { ChatModelOption } from "@/types/model"

interface ModelState {
  models: ChatModelOption[]
  selectedModelId: string
  loading: boolean
  selectModel: (modelId: string) => void
}

const ModelContext = createContext<ModelState | null>(null)

export function ModelProvider({ children }: { children: ReactNode }) {
  const { accessToken } = useAuth()
  const [models, setModels] = useState<ChatModelOption[]>([])
  const [selectedModelId, setSelectedModelId] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!accessToken) {
      setModels([])
      setSelectedModelId("")
      setLoading(false)
      return
    }
    let cancelled = false
    setModels([])
    setSelectedModelId("")
    setLoading(true)
    void listModels()
      .then((catalog) => {
        if (cancelled) return
        setModels(catalog.models)
        const selected = catalog.models.find(
          (model) => model.id === catalog.default_model && model.is_available
        ) ?? catalog.models.find(
          (model) => model.is_default && model.is_available
        ) ?? catalog.models.find(
          (model) => model.is_available
        )
        setSelectedModelId(selected?.id ?? "")
      })
      .catch(() => {
        if (!cancelled) {
          setModels([])
          setSelectedModelId("")
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [accessToken])

  const selectModel = useCallback((modelId: string) => {
    if (models.some((model) => model.id === modelId && model.is_available)) {
      setSelectedModelId(modelId)
    }
  }, [models])

  const value = useMemo(
    () => ({ models, selectedModelId, loading, selectModel }),
    [models, selectedModelId, loading, selectModel]
  )
  return <ModelContext.Provider value={value}>{children}</ModelContext.Provider>
}

export function useModel() {
  const context = useContext(ModelContext)
  if (!context) throw new Error("ModelProvider is missing")
  return context
}
