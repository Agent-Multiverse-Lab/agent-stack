import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"

import { createKnowledgeBase, listKnowledgeBases } from "@/api/knowledge"
import KnowledgePage from "@/pages/knowledge/KnowledgePage"
import { installBrowserStubs } from "@/test/browserStubs"

vi.mock("@/api/knowledge", () => ({ listKnowledgeBases: vi.fn(), createKnowledgeBase: vi.fn() }))
const base = { kb_id: "kb-1", name: "Docs", description: "Project documentation", status: "active" }
function renderPage() {
  return render(<MemoryRouter initialEntries={["/knowledge"]}><Routes><Route path="/knowledge" element={<KnowledgePage />} /><Route path="/knowledge/:kbId" element={<h1>Collection detail</h1>} /></Routes></MemoryRouter>)
}
beforeEach(() => {
  vi.resetAllMocks()
  installBrowserStubs()
  vi.mocked(listKnowledgeBases).mockResolvedValue([base])
})
afterEach(cleanup)

it("shows real collections with accessible navigation, search, sort and views", async () => {
  vi.mocked(listKnowledgeBases).mockResolvedValue([base, { ...base, kb_id: "kb-2", name: "Atlas", description: "Earth observation" }])
  renderPage()
  expect((await screen.findByRole("link", { name: /Docs/ })).getAttribute("href")).toBe("/knowledge/kb-1")
  expect(screen.getByText("2 collections")).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Sort by name" }))
  expect(screen.getAllByRole("link")[0]?.textContent).toContain("Atlas")
  fireEvent.click(screen.getByRole("button", { name: "List view" }))
  expect(screen.getByRole("button", { name: "List view" }).getAttribute("aria-pressed")).toBe("true")
  fireEvent.change(screen.getByRole("textbox", { name: "Search knowledge bases" }), { target: { value: "EARTH" } })
  expect(screen.queryByRole("link", { name: /Docs/ })).toBeNull()
  expect(screen.getByRole("link", { name: /Atlas/ })).toBeTruthy()
  fireEvent.change(screen.getByRole("textbox", { name: "Search knowledge bases" }), { target: { value: "missing" } })
  expect(screen.getByText("No matching knowledge bases")).toBeTruthy()
  fireEvent.click(screen.getAllByRole("button", { name: "Clear search" })[0]!)
  expect(screen.getAllByRole("link")).toHaveLength(2)
  fireEvent.click(screen.getByRole("link", { name: /Docs/ }))
  expect(screen.getByRole("heading", { name: "Collection detail" })).toBeTruthy()
})

it("creates a collection with trimmed input and opens it", async () => {
  vi.mocked(createKnowledgeBase).mockResolvedValue({ ...base, kb_id: "kb-2", name: "New Base" })
  renderPage()
  await screen.findByText("Docs")
  fireEvent.click(screen.getByRole("button", { name: "Create knowledge base" }))
  const dialog = await screen.findByRole("dialog")
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Knowledge base name" }), { target: { value: "  New Base  " } })
  fireEvent.click(within(dialog).getByRole("button", { name: "Create knowledge base" }))
  await waitFor(() => expect(createKnowledgeBase).toHaveBeenCalledWith({ name: "New Base", description: "" }))
  expect(await screen.findByRole("heading", { name: "Collection detail" })).toBeTruthy()
})

it("keeps the whole card as the only collection entry without numbers or action menus", async () => {
  renderPage()
  const link = await screen.findByRole("link", { name: /Docs/ })
  const card = link.closest("li")!
  expect(within(card).queryByText("01")).toBeNull()
  expect(within(card).queryByRole("button")).toBeNull()
  expect(within(card).getAllByRole("link")).toEqual([link])
  expect(link.getAttribute("href")).toBe("/knowledge/kb-1")
  link.focus()
  expect(document.activeElement).toBe(link)

  fireEvent.click(screen.getByRole("button", { name: "List view" }))
  const listLink = screen.getByRole("link", { name: /Docs/ })
  expect(within(listLink.closest("li")!).queryByRole("button")).toBeNull()
  fireEvent.click(listLink)
  expect(screen.getByRole("heading", { name: "Collection detail" })).toBeTruthy()
})

it("offers retry after a failed collection request", async () => {
  vi.mocked(listKnowledgeBases).mockRejectedValueOnce(new Error("Network unavailable"))
  renderPage()
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Network unavailable")
  fireEvent.click(screen.getByRole("button", { name: "Retry" }))
  expect(await screen.findByText("Docs")).toBeTruthy()
  expect(listKnowledgeBases).toHaveBeenCalledTimes(2)
})

it("keeps the create form accessible without repeating promotional helper copy", async () => {
  render(<MemoryRouter><KnowledgePage /></MemoryRouter>)
  await screen.findByText("Docs")
  expect(screen.queryByText("Your workspace")).toBeNull()
  fireEvent.click(screen.getByRole("button", { name: "Create knowledge base" }))
  expect(screen.getByRole("dialog", { name: "Create knowledge base" })).toBeTruthy()
  expect(screen.queryByText("Bring your documents together in a collection.")).toBeNull()
  expect(screen.getByRole("textbox", { name: "Knowledge base name" })).toBeTruthy()
})

it("uses the collection toolbar without a separate page title row", async () => {
  const { container } = renderPage()
  await screen.findByRole("link", { name: /Docs/ })
  expect(screen.queryByRole("heading", { name: "Knowledge Bases" })).toBeNull()
  expect(screen.getByRole("region", { name: "Knowledge Bases" })).toBeTruthy()
  expect(container.querySelector("header")).toBeNull()
  expect(screen.getByRole("heading", { name: "All collections" })).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Create knowledge base" }))
  expect(await screen.findByRole("dialog")).toBeTruthy()
})
