import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

it("shows the exact declared capabilities with icons and readable labels", async () => {
  vi.mocked(getModelProvider).mockResolvedValue({
    provider_id: "deepseek",
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    protocol: "openai_compatible",
    is_enabled: true,
    has_api_key: true,
    enabled_models: [{
      model_id: "declared-model",
      capabilities: ["chat", "vision", "reasoning", "tools", "code", "audio", "video"],
    }],
  });
  render(<SettingsModels />);

  const option = await screen.findByRole("listitem", { name: "declared-model" });
  const capabilities = within(option).getByRole("list", { name: "Model capabilities" });
  expect(within(capabilities).getAllByRole("listitem")).toHaveLength(7);
  for (const label of ["Chat", "Vision", "Reasoning", "Tools", "Code", "Audio", "Video"]) {
    const badge = within(capabilities).getByText(label);
    expect(badge.querySelector('svg[aria-hidden="true"]')).toBeTruthy();
  }
  expect(within(option).queryByText("Capabilities not provided")).toBeNull();
});

it("does not infer capabilities from a model name when metadata is absent", async () => {
  vi.mocked(getModelProvider).mockResolvedValue({
    provider_id: "deepseek",
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    protocol: "openai_compatible",
    is_enabled: false,
    has_api_key: false,
    enabled_models: [{ model_id: "vision-audio-reasoning-model", capabilities: [] }],
  });
  render(<SettingsModels />);

  const option = await screen.findByRole("listitem", { name: "vision-audio-reasoning-model" });
  expect(within(option).getByText("Capabilities not provided")).toBeTruthy();
  expect(within(option).queryByRole("list", { name: "Model capabilities" })).toBeNull();
  expect(within(option).queryByText("Vision")).toBeNull();
  expect(within(option).queryByText("Audio")).toBeNull();
  expect(within(option).queryByText("Reasoning")).toBeNull();
});

it("shows discovery capabilities and saves only explicitly selected models", async () => {
  vi.mocked(discoverProviderModels).mockResolvedValue([
    { model_id: "chat-model", capabilities: ["chat", "tools"] },
    { model_id: "visual-model", capabilities: ["vision"] },
    { model_id: "unspecified-model", capabilities: [] },
  ]);
  render(<SettingsModels />);
  const discover = await screen.findByRole("button", { name: "Discover models" });
  await waitFor(() => expect((discover as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(discover);

  const dialog = await screen.findByRole("dialog", { name: "Select chat models" });
  const visualOption = within(dialog).getByRole("listitem", { name: "visual-model" });
  expect(within(visualOption).getByText("Vision")).toBeTruthy();
  expect(within(dialog).getByText("Capabilities not provided")).toBeTruthy();
  const checkbox = within(visualOption).getByRole("checkbox", { name: "visual-model" });
  expect(checkbox.getAttribute("aria-checked")).toBe("false");
  fireEvent.click(checkbox);
  expect(checkbox.getAttribute("aria-checked")).toBe("true");
  expect(visualOption.getAttribute("data-selected")).toBe("true");

  fireEvent.change(within(dialog).getByRole("textbox", { name: "Search models" }), {
    target: { value: "chat-model" },
  });
  expect(within(dialog).queryByRole("checkbox", { name: "visual-model" })).toBeNull();
  expect(within(dialog).getByRole("checkbox", { name: "chat-model" }).getAttribute("aria-checked")).toBe("false");
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));

  const configured = screen.getByRole("list", { name: "Configured models" });
  expect(within(configured).getAllByRole("listitem", { name: "visual-model" })).toHaveLength(1);
  expect(within(configured).queryByText("chat-model")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(saveModelProvider).toHaveBeenCalledWith("deepseek", {
    base_url: "https://api.deepseek.com/v1",
    is_enabled: false,
    models: [{ model_id: "visual-model", capabilities: ["vision"] }],
  }));
});

it("preserves configured models and capabilities when discovery is cancelled", async () => {
  vi.mocked(getModelProvider).mockResolvedValue({
    provider_id: "deepseek",
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    protocol: "openai_compatible",
    is_enabled: false,
    has_api_key: false,
    enabled_models: [{ model_id: "configured-model", capabilities: ["reasoning"] }],
  });
  vi.mocked(discoverProviderModels).mockResolvedValue([
    { model_id: "new-model", capabilities: ["vision"] },
  ]);
  render(<SettingsModels />);
  await screen.findByRole("listitem", { name: "configured-model" });
  fireEvent.click(screen.getByRole("button", { name: "Discover models" }));

  const dialog = await screen.findByRole("dialog", { name: "Select chat models" });
  expect(within(dialog).getByRole("checkbox", { name: "configured-model" }).getAttribute("aria-checked")).toBe("true");
  fireEvent.click(within(dialog).getByRole("checkbox", { name: "configured-model" }));
  fireEvent.click(within(dialog).getByRole("checkbox", { name: "new-model" }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

  const configured = screen.getByRole("list", { name: "Configured models" });
  expect(within(configured).getByText("configured-model")).toBeTruthy();
  expect(within(configured).getByText("Reasoning")).toBeTruthy();
  expect(within(configured).queryByText("new-model")).toBeNull();
  expect(saveModelProvider).not.toHaveBeenCalled();
});

it("keeps provider selection locked while saving and restores controls afterward", async () => {
  let completeSave!: (value: { provider_id: string; cache_refreshed: boolean }) => void;
  vi.mocked(saveModelProvider).mockReturnValue(new Promise((resolve) => {
    completeSave = resolve;
  }));
  render(<SettingsModels />);
  const save = await screen.findByRole("button", { name: "Save" });
  await waitFor(() => expect((save as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(save);

  expect((screen.getByRole("button", { name: "Qwen" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "DeepSeek" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText("API Key") as HTMLInputElement).disabled).toBe(true);
  completeSave({ provider_id: "deepseek", cache_refreshed: true });
  await waitFor(() => expect((screen.getByRole("button", { name: "Qwen" }) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.getByRole("button", { name: "DeepSeek" }).getAttribute("aria-pressed")).toBe("true");
});
