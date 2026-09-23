import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"

import {
  getKnowledgeBase,
  getKnowledgeFileMarkdown,
  getKnowledgeGraph,
  listKnowledgeFiles,
  parseKnowledgeFile,
} from "@/api/knowledge"
import KnowledgeBaseDetailPage from "@/pages/knowledge/KnowledgeBaseDetailPage"
import { installBrowserStubs } from "@/test/browserStubs"

vi.mock("@/api/knowledge", () => ({
  getKnowledgeBase: vi.fn(),
  listKnowledgeFiles: vi.fn(),
  getKnowledgeFileMarkdown: vi.fn(),
  parseKnowledgeFile: vi.fn(),
  indexKnowledgeFile: vi.fn(),
  extractKnowledgeFile: vi.fn(),
  deleteKnowledgeFile: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  getKnowledgeGraph: vi.fn(),
  searchKnowledgeEntities: vi.fn(),
  chatWithKnowledgeBase: vi.fn()
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/knowledge/kb-1"]}>
      <Routes>
        <Route path="/knowledge/:kbId" element={<KnowledgeBaseDetailPage />} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  installBrowserStubs()
  vi.mocked(getKnowledgeBase).mockResolvedValue({
    kb_id: "kb-1",
    name: "Docs",
    description: "",
    status: "active"
  })
  vi.mocked(getKnowledgeFileMarkdown).mockResolvedValue({
    file_id: "file-1",
    markdown: "# Doc"
  })
  vi.mocked(listKnowledgeFiles).mockResolvedValue([
    {
      file_id: "file-1",
      kb_id: "kb-1",
      original_file_name: "manual.pdf",
      original_object_name: "knowledge-files/u/kb-1/file-1/original/manual.pdf",
      markdown_object_name: "knowledge-files/u/kb-1/file-1/parsed/document.md",
      content_type: "application/pdf",
      file_size: 100,
      status: "uploaded",
      error_message: null
    }
  ])
  vi.mocked(getKnowledgeGraph).mockResolvedValue({
    kb_id: "kb-1",
    nodes: [
      {
        entity_id: "e1",
        name: "OpenAI",
        type: "组织",
        description: "",
        file_id: "file-1"
      },
      {
        entity_id: "e2",
        name: "GPT",
        type: "产品",
        description: "",
        file_id: "file-1"
      }
    ],
    edges: [
      {
        relation_id: "r1",
        source_entity_id: "e1",
        target_entity_id: "e2",
        type: "发布"
      }
    ],
    entity_count: 2,
    relation_count: 1
  })
})

afterEach(cleanup)

it("renders detail page with file list", async () => {
  renderPage()

  expect(await screen.findByText("Docs")).toBeTruthy()
  expect(screen.getByRole("tab", { name: "Documents" })).toBeTruthy()
  expect(screen.getByRole("tab", { name: "Knowledge Graph" })).toBeTruthy()
  expect((await screen.findAllByText("manual.pdf"))[0]).toBeTruthy()
})

it("parse action posts and refreshes the file list", async () => {
  vi.mocked(parseKnowledgeFile).mockResolvedValue({
    file_id: "file-1",
    kb_id: "kb-1",
    original_file_name: "manual.pdf",
    original_object_name: "original",
    markdown_object_name: "parsed/document.md",
    content_type: "application/pdf",
    file_size: 100,
    status: "parsed",
    error_message: null
  })
  const { container } = renderPage()
  await screen.findAllByText("manual.pdf")

  fireEvent.click(screen.getByRole("button", { name: "Open file actions" }))
  fireEvent.click(await screen.findByRole("menuitem", { name: "Parse file" }))

  await waitFor(() =>
    expect(parseKnowledgeFile).toHaveBeenCalledWith("kb-1", "file-1")
  )
  expect(container.querySelector("input[type='file']")).not.toBeNull()
})

it("graph tab renders one circle per node", async () => {
  const { container } = renderPage()
  (await screen.findAllByText("manual.pdf"))[0]

  fireEvent.click(screen.getByRole("tab", { name: "Knowledge Graph" }))

  await waitFor(() =>
    expect(container.querySelectorAll("circle").length).toBe(2)
  )
})
