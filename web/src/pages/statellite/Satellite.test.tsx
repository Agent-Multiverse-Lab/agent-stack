import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import i18n from "@/i18n";
import Satellite from "./Satellite";

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

it.each([
  ["en", "Satellite unavailable"],
  ["zh-CN", "卫星功能暂不可用"],
])("shows one concise unavailable state in %s", async (language, message) => {
  await i18n.changeLanguage(language);
  render(<Satellite />);
  expect(screen.getByRole("heading", { name: message })).toBeTruthy();
  expect(screen.queryByText(/backend|后端|接入后/i)).toBeNull();
});
