import { afterEach, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"

import i18n from "@/i18n"
import { AskUser } from "@/pages/chat/components/AskUser"
import type { InteractionRequired } from "@/types/chat"

afterEach(() => {
  cleanup()
  void i18n.changeLanguage("en")
})

it("requires an answer and keeps changed answers when navigating", () => {
  const submit = vi.fn()
  const interaction: InteractionRequired = {
    kind: "ask_user",
    parent_run_id: "run-1",
    questions: [
      {
        question_id: "first",
        question: "First question",
        options: [
          { label: "Alpha", value: "a" },
          { label: "Beta", value: "b" },
        ],
      },
      {
        question_id: "second",
        question: "Second question",
        options: [
          { label: "Yes", value: "yes" },
          { label: "No", value: "no" },
        ],
      },
    ],
  }
  render(<AskUser interaction={interaction} disabled={false} submit={submit} />)

  fireEvent.click(screen.getByRole("button", { name: "Next" }))
  expect(screen.getByText("First question")).toBeTruthy()
  expect(submit).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole("radio", { name: "Alpha" }))
  act(() => {
    void i18n.changeLanguage("zh-CN")
  })
  expect(screen.getByRole("progressbar").getAttribute("aria-valuetext")).toBe("第 1 题，共 2 题")
  expect(document.documentElement.lang).toBe("zh-CN")
  expect(window.localStorage.getItem("am-language")).toBe("zh-CN")

  expect((screen.getByRole("radio", { name: "Alpha" }) as HTMLInputElement).checked).toBe(true)
  fireEvent.click(screen.getByRole("button", { name: "下一题" }))
  expect(screen.getByText("Second question")).toBeTruthy()
  fireEvent.click(screen.getByRole("radio", { name: "Yes" }))
  fireEvent.click(screen.getByRole("button", { name: "上一题" }))
  fireEvent.click(screen.getByRole("radio", { name: "Beta" }))
  fireEvent.click(screen.getByRole("button", { name: "下一题" }))
  fireEvent.click(screen.getByRole("button", { name: "继续" }))

  expect(submit).toHaveBeenCalledWith({ first: "b", second: "yes" })
})
