import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import {
  discoverProviderModels,
  getModelProvider,
  saveModelProvider,
  testProviderConnection,
} from "@/api/model";
import SettingsModels from "@/layouts/MainLayout/components/SettingsModels";
import { installBrowserStubs } from "@/test/browserStubs";

vi.mock("@/api/model", () => ({
  discoverProviderModels: vi.fn(),
  getModelProvider: vi.fn(),
  saveModelProvider: vi.fn(),
  testProviderConnection: vi.fn(),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token" }),
}));

beforeEach(() => {
  installBrowserStubs();
  vi.mocked(getModelProvider).mockResolvedValue({
    provider_id: "deepseek",
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
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
