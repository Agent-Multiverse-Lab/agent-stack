import { afterEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import { AskUser } from "@/pages/chat/components/AskUser"
import type { InteractionRequired } from "@/types/chat"

afterEach(cleanup)

it("keeps changed answers when navigating between agent questions", () => {
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
          { label: "Beta", value: "b" }
        ]
      },
      {
        question_id: "second",
        question: "Second question",
        options: [
          { label: "Yes", value: "yes" },
          { label: "No", value: "no" }
        ]
      }
    ]
  }
  render(<AskUser interaction={interaction} disabled={false} submit={submit} />)

  fireEvent.click(screen.getByRole("radio", { name: "Alpha" }))
  expect(screen.getByText("Second question")).toBeTruthy()
  fireEvent.click(screen.getByRole("radio", { name: "Yes" }))
  fireEvent.click(screen.getByRole("button", { name: "上一题" }))
  fireEvent.click(screen.getByRole("radio", { name: "Beta" }))
  fireEvent.click(screen.getByRole("button", { name: "Continue" }))

  expect(submit).toHaveBeenCalledWith({ first: "b", second: "yes" })
})
