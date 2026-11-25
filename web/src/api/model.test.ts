import { afterEach, describe, expect, it, vi } from "vitest"

import { apiClient } from "@/api/client"
import { createModelProvider, listModelProviders, listModels } from "@/api/model"

describe("model API envelope unwrapping", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("requests grouped catalog by category and unwraps data", async () => {
    const catalog = {
      openai: {
        provider_id: "openai",
        display_name: "OpenAI",
        models: [
          {
            model_id: "gpt-5.6-sol",
            category: "chat" as const,
            capabilities: ["chat" as const, "tools" as const],
          },
        ],
      },
    }
    const apiGet = vi.spyOn(apiClient, "apiGet").mockResolvedValue({
      status: "success",
      data: catalog,
    })

    const result = await listModels("chat")
    expect(apiGet).toHaveBeenCalledWith("/api/models?category=chat", {
      requiresAuth: true,
    })
    expect(result).toEqual(catalog)
  })

  it("unwraps providers list and create response", async () => {
    const providers = [
      {
        provider_id: "openai",
        name: "OpenAI",
        protocol: "openai_compatible" as const,
        base_url: "https://api.openai.com/v1",
        embedding_base_url: "",
        rerank_base_url: "",
        is_enabled: true,
        has_api_key: true,
        models: [],
      },
    ]
    const apiGet = vi.spyOn(apiClient, "apiGet").mockResolvedValue({
      status: "success",
      data: providers,
    })
    const apiPost = vi.spyOn(apiClient, "apiPost").mockResolvedValue({
      status: "success",
      data: { provider_id: "openai", cache_refreshed: true },
    })

    expect(await listModelProviders()).toEqual(providers)
    expect(apiGet).toHaveBeenCalledWith("/api/models/providers", {
      requiresAuth: true,
    })

    expect(
      await createModelProvider({
        provider_id: "openai",
        name: "OpenAI",
        protocol: "openai_compatible",
        base_url: "https://api.openai.com/v1",
        embedding_base_url: "",
        rerank_base_url: "",
        api_key: "sk-test",
        is_enabled: true,
        models: [],
      })
    ).toEqual({ provider_id: "openai", cache_refreshed: true })
    expect(apiPost).toHaveBeenCalledWith(
      "/api/models/providers",
      expect.objectContaining({ provider_id: "openai", name: "OpenAI" }),
      { requiresAuth: true }
    )
  })
})
