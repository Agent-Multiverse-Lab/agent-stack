import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"

import {
  getKnowledgeBase,
  getKnowledgeFileMarkdown,
  getKnowledgeGraph,
  listKnowledgeFiles,
  parseKnowledgeFile,
  uploadKnowledgeFile,
  indexKnowledgeFile,
  extractKnowledgeFile,
  deleteKnowledgeFile,
  chatWithKnowledgeBase,
  searchKnowledgeEntities,
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
  vi.resetAllMocks()
  installBrowserStubs()
  HTMLElement.prototype.scrollTo = vi.fn()
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

  expect(await screen.findByRole("heading", { name: "Docs", level: 1 })).toBeTruthy()
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
  const { container } = renderPage();
  await screen.findAllByText("manual.pdf");

  fireEvent.click(screen.getByRole("tab", { name: "Knowledge Graph" }));

  await waitFor(() =>
    expect(container.querySelectorAll("svg g circle").length).toBe(2)
  );
});


it("filters documents without losing the selected preview", async () => {
  renderPage()
  await screen.findAllByText("manual.pdf")
  fireEvent.change(screen.getByRole("textbox", { name: "Search files" }), { target: { value: "missing" } })
  expect(screen.getByText("No matching documents")).toBeTruthy()
  expect(within(screen.getByRole("region", { name: "Document preview" })).getByText("manual.pdf")).toBeTruthy()
})

it("retries a failed file list", async () => {
  vi.mocked(listKnowledgeFiles).mockRejectedValueOnce(new Error("Files unavailable"))
  renderPage()
  expect(await screen.findByText("Files unavailable")).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Retry" }))
  expect((await screen.findAllByText("manual.pdf"))[0]).toBeTruthy()
})

it("uploads supported files and skips unsupported files", async () => {
  renderPage()
  await screen.findAllByText("manual.pdf")
  const file = new File(["document"], "guide.pdf", { type: "application/pdf" })
  const unsupported = new File(["binary"], "program.exe")
  fireEvent.change(screen.getByLabelText("Choose files to upload"), { target: { files: [file, unsupported] } })
  await waitFor(() => expect(uploadKnowledgeFile).toHaveBeenCalledTimes(1))
  expect(uploadKnowledgeFile).toHaveBeenCalledWith("kb-1", file)
})

it("respects the parse, index and graph extraction status contract", async () => {
  const uploaded = (await vi.mocked(listKnowledgeFiles)("kb-1"))[0]!
  vi.mocked(listKnowledgeFiles).mockResolvedValue([{ ...uploaded, status: "parsed" }])
  vi.mocked(indexKnowledgeFile).mockResolvedValue({ kb_id: "kb-1", file_id: "file-1", status: "indexed", chunk_count: 4, collection_name: "collection", embedding_model_spec: "embedding", embedding_dimension: 3 })
  renderPage()
  await screen.findAllByText("manual.pdf")
  fireEvent.click(screen.getByRole("button", { name: "Open file actions" }))
  expect((await screen.findByRole("menuitem", { name: "Parse file" })).getAttribute("aria-disabled")).toBe("true")
  expect(screen.getByRole("menuitem", { name: "Extract graph" }).getAttribute("aria-disabled")).toBe("true")
  vi.mocked(listKnowledgeFiles).mockResolvedValue([{ ...uploaded, status: "indexed" }])
  fireEvent.click(screen.getByRole("menuitem", { name: "Build index" }))
  await waitFor(() => expect(indexKnowledgeFile).toHaveBeenCalledWith("kb-1", "file-1"))
  vi.mocked(extractKnowledgeFile).mockResolvedValue({ kb_id: "kb-1", file_id: "file-1", status: "extracted", entity_count: 3, relation_count: 2 })
  fireEvent.click(await screen.findByRole("button", { name: "Extract graph" }))
  await waitFor(() => expect(extractKnowledgeFile).toHaveBeenCalledWith("kb-1", "file-1"))
})

it("guards parse and delete while a file operation is running", async () => {
  let finishParse: (value: Awaited<ReturnType<typeof parseKnowledgeFile>>) => void = () => {}
  const uploaded = (await vi.mocked(listKnowledgeFiles)("kb-1"))[0]!
  vi.mocked(parseKnowledgeFile).mockImplementation(() => new Promise((resolve) => { finishParse = resolve }))
  renderPage()
  await screen.findAllByText("manual.pdf")
  fireEvent.click(screen.getByRole("button", { name: "Parse file" }))
  fireEvent.click(screen.getByRole("button", { name: "Parse file" }))
  expect(parseKnowledgeFile).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole("button", { name: "Open file actions" }))
  expect((await screen.findByRole("menuitem", { name: "Delete file" })).getAttribute("aria-disabled")).toBe("true")
  expect(deleteKnowledgeFile).not.toHaveBeenCalled()
  finishParse({ ...uploaded, status: "parsed" })
  await waitFor(() => expect(screen.queryAllByText("Parsing…")).toHaveLength(0))
})

it("opens graph entities using the keyboard and reports search failure", async () => {
  vi.mocked(searchKnowledgeEntities).mockRejectedValue(new Error("Search unavailable"))
  renderPage()
  await screen.findAllByText("manual.pdf")
  fireEvent.click(screen.getByRole("tab", { name: "Knowledge Graph" }))
  const entity = await screen.findByRole("button", { name: "OpenAI" })
  fireEvent.keyDown(entity, { key: "Enter" })
  expect(screen.getByRole("heading", { name: "OpenAI" })).toBeTruthy()
  fireEvent.change(screen.getByRole("textbox", { name: "Search entities" }), { target: { value: "OpenAI" } })
  fireEvent.click(screen.getByRole("button", { name: "Search" }))
  expect(await screen.findByText("Search unavailable")).toBeTruthy()
})

it("sends knowledge questions with citations and retries failed requests", async () => {
  vi.mocked(chatWithKnowledgeBase).mockRejectedValueOnce(new Error("Answer unavailable")).mockResolvedValue({ kb_id: "kb-1", answer: "Answer from the document [1]", citations: [{ file_id: "file-1", file_name: "manual.pdf", chunk_id: "chunk-1", excerpt: "Supporting passage" }] })
  renderPage()
  await screen.findAllByText("manual.pdf")
  fireEvent.click(screen.getByRole("tab", { name: "Knowledge Chat" }))
  fireEvent.click(await screen.findByRole("button", { name: "Summarize the main topics" }))
  expect(chatWithKnowledgeBase).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Send question" }))
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Answer unavailableRetry")
  fireEvent.click(screen.getByRole("button", { name: "Retry" }))
  expect(await screen.findByText("Supporting passage")).toBeTruthy()
  expect(chatWithKnowledgeBase).toHaveBeenNthCalledWith(2, "kb-1", "Summarize the main topics")
  expect(screen.getAllByText("Summarize the main topics")).toHaveLength(1)
})


it.each(["resolve", "reject"])("ignores a cleared graph search that later %ss without interrupting a new search", async (outcome) => {
  type SearchResponse = Awaited<ReturnType<typeof searchKnowledgeEntities>>
  let resolveFirst: (value: SearchResponse) => void = () => {}
  let rejectFirst: (error: Error) => void = () => {}
  let resolveSecond: (value: SearchResponse) => void = () => {}
  const first = new Promise<SearchResponse>((resolve, reject) => { resolveFirst = resolve; rejectFirst = reject })
  const second = new Promise<SearchResponse>((resolve) => { resolveSecond = resolve })
  vi.mocked(searchKnowledgeEntities).mockReturnValueOnce(first).mockReturnValueOnce(second)
  const { container } = renderPage()
  await screen.findAllByText("manual.pdf")
  fireEvent.click(screen.getByRole("tab", { name: "Knowledge Graph" }))
  const input = await screen.findByRole("textbox", { name: "Search entities" })
  fireEvent.change(input, { target: { value: "Old query" } })
  fireEvent.click(screen.getByRole("button", { name: "Search" }))
  fireEvent.click(screen.getByRole("button", { name: "Clear" }))
  expect(input).toHaveProperty("value", "")
  fireEvent.change(input, { target: { value: "New query" } })
  fireEvent.click(screen.getByRole("button", { name: "Search" }))
  expect(searchKnowledgeEntities).toHaveBeenCalledTimes(2)
  await act(async () => {
    if (outcome === "resolve") resolveFirst({ kb_id: "kb-1", hits: [{ entity_id: "e1", name: "OpenAI", type: "organization", description: "", file_id: "file-1", similarity: 1 }] })
    else rejectFirst(new Error("Stale search failure"))
  })
  expect(screen.queryByText("1 matching entities")).toBeNull()
  expect(screen.queryByText("Stale search failure")).toBeNull()
  expect(container.querySelectorAll("svg g circle")).toHaveLength(2)
  expect(screen.getByRole("button", { name: "Search" })).toHaveProperty("disabled", true)
  await act(async () => { resolveSecond({ kb_id: "kb-1", hits: [] }) })
  expect(screen.getByText("0 matching entities")).toBeTruthy()
  expect(screen.getByRole("button", { name: "Search" })).toHaveProperty("disabled", false)
})
