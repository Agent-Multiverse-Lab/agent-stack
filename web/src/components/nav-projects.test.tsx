import { afterEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"

import { listThreads, renameThread } from "@/api/agent"
import { NavProjects } from "@/components/nav-projects"
import { AppSidebar } from "@/components/app-sidebar"
import {
  Sidebar,
  SidebarContent,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { installBrowserStubs } from "@/test/browserStubs"
import type { ThreadSummaryResponse } from "@/types/chat"

vi.mock("@/api/agent", () => ({
  listThreads: vi.fn(),
  renameThread: vi.fn(),
  deleteThread: vi.fn(),
}))

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: null, logout: vi.fn() }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

const thread: ThreadSummaryResponse = {
  thread_id: "thread-1",
  title: "Old title",
  summary: null,
  agent_id: "agent",
  metadata: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  last_message_at: null,
}

function mockThreads() {
  vi.mocked(listThreads).mockResolvedValue({
    items: [thread],
    has_more: false,
    next_cursor: null,
  })
  vi.mocked(renameThread).mockResolvedValue({ ...thread, title: "New title" })
}

it("renames a conversation from the shadcn sidebar", async () => {
  installBrowserStubs()
  mockThreads()

  render(
    <MemoryRouter initialEntries={["/c/thread-1"]}>
      <SidebarProvider>
        <Routes>
          <Route
            path="/c/:threadId"
            element={<NavProjects onSearch={vi.fn()} />}
          />
        </Routes>
      </SidebarProvider>
    </MemoryRouter>,
  )

  expect(await screen.findByRole("link", { name: "Old title" })).toBeTruthy()
  fireEvent.click(
    screen.getByRole("button", {
      name: "Conversation actions: Old title",
    }),
  )
  fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))
  fireEvent.change(screen.getByRole("textbox", { name: "Conversation title" }), {
    target: { value: "New title" },
  })
  fireEvent.click(screen.getByRole("button", { name: "Save" }))

  expect(await screen.findByRole("link", { name: "New title" })).toBeTruthy()
  expect(renameThread).toHaveBeenCalledWith("thread-1", "New title")
})

it("opens a conversation action dialog inside the mobile sidebar", async () => {
  installBrowserStubs()
  vi.stubGlobal("innerWidth", 375)
  mockThreads()

  render(
    <MemoryRouter initialEntries={["/c/thread-1"]}>
      <SidebarProvider>
        <Sidebar collapsible="icon">
          <SidebarContent>
            <Routes>
              <Route
                path="/c/:threadId"
                element={<NavProjects onSearch={vi.fn()} />}
              />
            </Routes>
          </SidebarContent>
        </Sidebar>
        <SidebarTrigger />
      </SidebarProvider>
    </MemoryRouter>,
  )

  fireEvent.click(screen.getByRole("button", { name: "Toggle Sidebar" }))
  expect(await screen.findByRole("link", { name: "Old title" })).toBeTruthy()
  fireEvent.click(
    screen.getByRole("button", {
      name: "Conversation actions: Old title",
    }),
  )
  fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))
  expect(
    screen.getByRole("dialog", { name: "Rename conversation" }),
  ).toBeTruthy()
})

it("opens conversation search dialog from the sidebar header search button", async () => {
  installBrowserStubs()
  vi.mocked(listThreads).mockResolvedValue({
    items: [thread, { ...thread, thread_id: "thread-2", title: "Release plan" }],
    has_more: false,
    next_cursor: null,
  })
  const onSearch = vi.fn()

  render(
    <MemoryRouter initialEntries={["/"]}>
      <SidebarProvider>
        <AppSidebar onSearch={onSearch} onProfile={vi.fn()} onSettings={vi.fn()} />
      </SidebarProvider>
    </MemoryRouter>,
  )

  expect(await screen.findByRole("link", { name: "Old title" })).toBeTruthy()
  expect(screen.getByRole("link", { name: "Release plan" })).toBeTruthy()

  const searchButton = screen.getByRole("button", { name: "Search conversations" })
  const sidebarTrigger = screen.getAllByRole("button", { name: "Toggle Sidebar" })[0]
  expect(
    searchButton.compareDocumentPosition(sidebarTrigger) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()

  fireEvent.click(searchButton)
  expect(onSearch).toHaveBeenCalledTimes(1)
})
