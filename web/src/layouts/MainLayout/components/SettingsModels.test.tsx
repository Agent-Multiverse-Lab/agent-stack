import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import {
  discoverProviderModels,
  getModelProvider,
  listModelProviders,
  saveModelProvider,
  testProviderConnection,
} from "@/api/model";
import SettingsModels from "@/layouts/MainLayout/components/SettingsModels";
import { installBrowserStubs } from "@/test/browserStubs";

vi.mock("@/api/model", () => ({
  discoverProviderModels: vi.fn(),
  getModelProvider: vi.fn(),
  listModelProviders: vi.fn(),
  saveModelProvider: vi.fn(),
  testProviderConnection: vi.fn(),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token" }),
}));

beforeEach(() => {
  installBrowserStubs();
  vi.mocked(listModelProviders).mockResolvedValue([
    {
      provider_id: "deepseek",
      name: "DeepSeek",
      is_enabled: false,
      has_api_key: false,
    },
    {
      provider_id: "dashscope",
      name: "Qwen",
      is_enabled: false,
      has_api_key: false,
    },
  ]);
  vi.mocked(getModelProvider).mockResolvedValue({
    provider_id: "deepseek",
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    protocol: "openai_compatible",
    is_enabled: false,
    has_api_key: false,
    enabled_models: [],
  });
  vi.mocked(testProviderConnection).mockResolvedValue({
    success: true,
    elapsed_ms: 12,
    error: null,
    status_code: null,
  });
  vi.mocked(saveModelProvider).mockResolvedValue({
    provider_id: "deepseek",
    cache_refreshed: true,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

it("sends the unsaved API key to the backend test without requiring a model", async () => {
  render(<SettingsModels />);

  const apiKey = await screen.findByLabelText("API Key");
  await waitFor(() =>
    expect((apiKey as HTMLInputElement).disabled).toBe(false),
  );
  fireEvent.change(apiKey, { target: { value: "test-api-key" } });
  fireEvent.click(
    screen.getByRole("button", { name: "Test model connection" }),
  );

  await waitFor(() =>
    expect(testProviderConnection).toHaveBeenCalledWith("deepseek", {
      base_url: "https://api.deepseek.com/v1",
      api_key: "test-api-key",
      is_enabled: false,
      models: [],
    }),
  );
  expect(discoverProviderModels).not.toHaveBeenCalled();
  expect(saveModelProvider).not.toHaveBeenCalled();
});

it("renders the provider navigation from the backend list", async () => {
  vi.mocked(listModelProviders).mockResolvedValue([
    {
      provider_id: "deepseek",
      name: "DeepSeek",
      is_enabled: false,
      has_api_key: false,
    },
    {
      provider_id: "custom",
      name: "Custom Gateway",
      is_enabled: true,
      has_api_key: true,
    },
  ]);
  render(<SettingsModels />);

  await screen.findByRole("button", { name: "DeepSeek" });
  expect(screen.getByRole("button", { name: "Custom Gateway" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Qwen" })).toBeNull();
});

it("reloads the redacted provider after saving a new key", async () => {
  vi.mocked(getModelProvider)
    .mockResolvedValueOnce({
      provider_id: "deepseek",
      name: "DeepSeek",
      base_url: "https://api.deepseek.com/v1",
      protocol: "openai_compatible",
      is_enabled: false,
      has_api_key: false,
      enabled_models: [],
    })
    .mockResolvedValueOnce({
      provider_id: "deepseek",
      name: "DeepSeek",
      base_url: "https://api.deepseek.com/v1",
      protocol: "openai_compatible",
      is_enabled: false,
      has_api_key: true,
      enabled_models: [],
    });
  render(<SettingsModels />);

  const apiKey = await screen.findByLabelText("API Key");
  await waitFor(() =>
    expect((apiKey as HTMLInputElement).disabled).toBe(false),
  );
  fireEvent.change(apiKey, { target: { value: "new-secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() =>
    expect(saveModelProvider).toHaveBeenCalledWith("deepseek", {
      base_url: "https://api.deepseek.com/v1",
      api_key: "new-secret",
      is_enabled: false,
      models: [],
    }),
  );
  await waitFor(() => expect(getModelProvider).toHaveBeenCalledTimes(2));
  await waitFor(() =>
    expect((apiKey as HTMLInputElement).value).toBe(""),
  );
  expect((apiKey as HTMLInputElement).placeholder).toBe("••••••••••••••••");
});
