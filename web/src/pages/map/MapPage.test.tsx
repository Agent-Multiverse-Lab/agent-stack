import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import i18n from "@/i18n";
import MapPage from "@/pages/map/MapPage";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

it("shows a clear setup state when the TianDiTu key is missing", async () => {
  vi.stubEnv("VITE_TIANDITU_TK", "");
  await i18n.changeLanguage("en");
  render(<MapPage />);

  expect(screen.getByRole("main", { name: "Map" })).toBeTruthy();
  expect(screen.getByText("TianDiTu key is not configured")).toBeTruthy();
  expect(screen.getByText("Catalog search is not connected")).toBeTruthy();
  expect(screen.getByText("Map conversation is not connected")).toBeTruthy();
});
