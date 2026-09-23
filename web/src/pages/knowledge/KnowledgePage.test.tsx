import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"

import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
} from "@/api/knowledge"
import KnowledgePage from "@/pages/knowledge/KnowledgePage"
import { installBrowserStubs } from "@/test/browserStubs"

vi.mock("@/api/knowledge", () => ({
  listKnowledgeBases: vi.fn(),
  createKnowledgeBase: vi.fn(),
  deleteKnowledgeBase: vi.fn()
}))

beforeEach(() => {
  installBrowserStubs()
  vi.mocked(listKnowledgeBases).mockResolvedValue([
    {
      kb_id: "kb-1",
      name: "Docs",
      description: "项目文档",
      status: "active"
    }
  ])
})

afterEach(cleanup)

it("lists knowledge bases with create and delete flows", async () => {
  vi.mocked(createKnowledgeBase).mockResolvedValue({
    kb_id: "kb-2",
    name: "New Base",
    description: "",
    status: "active"
  })
  vi.mocked(deleteKnowledgeBase).mockResolvedValue({
    kb_id: "kb-1",
    deleted_file_count: 0
  })
  render(
    <MemoryRouter>
      <Routes>
        <Route path="*" element={<KnowledgePage />} />
      </Routes>
    </MemoryRouter>
  )

  expect(await screen.findByText("Docs")).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Create knowledge base" }))
  fireEvent.change(screen.getByRole("textbox", { name: "Knowledge base name" }), {
    target: { value: "New Base" }
  })
  const buttons = screen.getAllByRole("button", { name: "Create knowledge base" })
  fireEvent.click(buttons[buttons.length - 1]!)
  await waitFor(() =>
    expect(createKnowledgeBase).toHaveBeenCalledWith({
      name: "New Base",
      description: ""
    })
  )

  fireEvent.click(screen.getByRole("button", { name: "Open file actions" }))
  fireEvent.click(
    await screen.findByRole("menuitem", { name: "Delete knowledge base" })
  )
  fireEvent.click(
    screen.getByRole("button", { name: "Delete knowledge base" })
  )
  await waitFor(() =>
    expect(deleteKnowledgeBase).toHaveBeenCalledWith("kb-1")
  )
})
