import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"

import { createProject, deleteProject, listProjects, updateProject, type ProjectResponse } from "@/api/project"
import { listThreads, updateThread, type ThreadMetadataResponse } from "@/api/thread"
import { AppSidebar } from "@/components/app-sidebar"
import { SidebarProvider } from "@/components/ui/sidebar"
import { installBrowserStubs } from "@/test/browserStubs"

vi.mock("@/api/project", () => ({ createProject: vi.fn(), deleteProject: vi.fn(), listProjects: vi.fn(), updateProject: vi.fn() }))
vi.mock("@/api/thread", () => ({ listThreads: vi.fn(), updateThread: vi.fn(), renameThread: vi.fn(), deleteThread: vi.fn() }))
vi.mock("@/context/AuthContext", () => ({ useAuth: () => ({ accessToken: "test-token", user: null, logout: vi.fn() }) }))

let projects: ProjectResponse[]
let threads: ThreadMetadataResponse[]
const now = "2026-11-13T00:00:00Z"

beforeEach(() => {
  installBrowserStubs()
  projects = [{ project_id: "proj-1", name: "Research", pinned: false, pinned_at: null, created_at: now, updated_at: now }]
  threads = [{ thread_id: "thread-1", title: "Analysis", summary: null, agent_id: "leader", metadata: {}, project_id: null, pinned: false, pinned_at: null, created_at: now, updated_at: now }]
  vi.mocked(listProjects).mockImplementation(async () => [...projects])
  vi.mocked(listThreads).mockImplementation(async (options) => ({
    items: threads.filter((thread) => (!options?.pinned || thread.pinned) && (!options?.unassigned || thread.project_id === null) && (options?.project_id === undefined || thread.project_id === options.project_id)),
    has_more: false, next_cursor: null,
  }))
  vi.mocked(updateThread).mockImplementation(async (id, fields) => {
    threads = threads.map((thread) => thread.thread_id === id ? { ...thread, ...fields, pinned_at: fields.pinned === undefined ? thread.pinned_at : fields.pinned ? now : null } : thread)
    return threads.find((thread) => thread.thread_id === id)!
  })
  vi.mocked(createProject).mockImplementation(async (name) => {
    const project = { ...projects[0], project_id: "proj-2", name }
    projects = [...projects, project]
    return project
  })
  vi.mocked(updateProject).mockImplementation(async (projectId, fields) => {
    projects = projects.map((project) => project.project_id === projectId ? { ...project, ...fields, pinned_at: fields.pinned ? now : null } : project)
    return projects.find((project) => project.project_id === projectId)!
  })
  vi.mocked(deleteProject).mockImplementation(async (projectId) => {
    projects = projects.filter((project) => project.project_id !== projectId)
    threads = threads.map((thread) => thread.project_id === projectId ? { ...thread, project_id: null } : thread)
  })
})

afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals() })

function mount() {
  return render(<MemoryRouter><SidebarProvider><AppSidebar onSearch={vi.fn()} onProfile={vi.fn()} onSettings={vi.fn()} /></SidebarProvider></MemoryRouter>)
}

async function menu(name: string) {
  fireEvent.click(await screen.findByRole("button", { name }))
}

it("creates and renames projects, then deletes a project without deleting its conversations", async () => {
  threads[0].project_id = "proj-1"
  mount()
  await menu("New project")
  fireEvent.change(screen.getByRole("textbox", { name: "Project name" }), { target: { value: "Release" } })
  fireEvent.click(screen.getByRole("button", { name: "Save" }))
  expect(await screen.findByRole("button", { name: "Release", expanded: true })).toBeTruthy()
  await menu("Project actions: Release")
  fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))
  fireEvent.change(screen.getByRole("textbox", { name: "Project name" }), { target: { value: "Delivery" } })
  fireEvent.click(screen.getByRole("button", { name: "Save" }))
  expect(await screen.findByRole("button", { name: "Delivery", expanded: true })).toBeTruthy()
  await menu("Project actions: Research")
  fireEvent.click(await screen.findByRole("menuitem", { name: "Delete project" }))
  expect(deleteProject).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Delete" }))
  expect(await screen.findByRole("link", { name: "Analysis" })).toBeTruthy()
  await waitFor(() => expect(screen.queryByRole("button", { name: "Research" })).toBeNull())
})

it("synchronizes project and conversation pins and keeps them after remount", async () => {
  const view = mount()
  expect(await screen.findByRole("link", { name: "Analysis" })).toBeTruthy()
  await menu("Conversation actions: Analysis")
  fireEvent.click(await screen.findByRole("menuitem", { name: "Pin" }))
  expect(await screen.findByRole("button", { name: "Unpin Analysis" })).toBeTruthy()
  await menu("Project actions: Research")
  fireEvent.click(await screen.findByRole("menuitem", { name: "Pin" }))
  expect(await screen.findByRole("button", { name: "Unpin Research" })).toBeTruthy()
  view.unmount()
  mount()
  expect(await screen.findByRole("button", { name: "Unpin Analysis" })).toBeTruthy()
  expect(await screen.findByRole("button", { name: "Unpin Research" })).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Unpin Analysis" }))
  await waitFor(() => expect(screen.queryByRole("button", { name: "Unpin Analysis" })).toBeNull())
  expect(screen.getByRole("link", { name: "Analysis" })).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Unpin Research" }))
  await waitFor(() => expect(screen.queryByRole("button", { name: "Pinned" })).toBeNull())
})

it("moves conversations between the unassigned list and project list", async () => {
  mount()
  await menu("Conversation actions: Analysis")
  fireEvent.click(await screen.findByRole("menuitem", { name: "Add to project" }))
  fireEvent.click(await screen.findByRole("menuitem", { name: "Research" }))
  await waitFor(() => expect(screen.queryByRole("link", { name: "Analysis" })).toBeNull())
  await menu("Research")
  expect(await screen.findByRole("link", { name: "Analysis" })).toBeTruthy()
  expect(listThreads).toHaveBeenCalledWith(expect.objectContaining({ project_id: "proj-1", unassigned: false }))
  await menu("Conversation actions: Analysis")
  fireEvent.click(await screen.findByRole("menuitem", { name: "Remove from project" }))
  await waitFor(() => {
    const history = screen.getByRole("button", { name: "Conversations" }).closest('[aria-label="Conversation history"]') as HTMLElement
    expect(within(history).getByRole("link", { name: "Analysis" })).toBeTruthy()
  })
})

it("shows a failed pin in place and keeps the original conversation", async () => {
  vi.mocked(updateThread).mockRejectedValueOnce(new Error("Save failed"))
  mount()
  await menu("Conversation actions: Analysis")
  fireEvent.click(await screen.findByRole("menuitem", { name: "Pin" }))
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Save failed")
  expect(screen.getByRole("link", { name: "Analysis" })).toBeTruthy()
  expect(screen.queryByRole("button", { name: "Unpin Analysis" })).toBeNull()
})
