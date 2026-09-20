import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"

import App from "@/app/App"
import { AuthProvider } from "@/context/AuthContext"
import { ModelProvider } from "@/context/ModelContext"
import { getCurrentUser, loginUser, registerUser } from "@/api/auth"
import { listModels } from "@/api/model"
import { installBrowserStubs } from "@/test/browserStubs"

vi.mock("@/api/auth", () => ({
  getCurrentUser: vi.fn(),
  loginUser: vi.fn(),
  registerUser: vi.fn()
}))
vi.mock("@/api/model", () => ({
  listModels: vi.fn()
}))

const user = {
  id: 1,
  uid: "test-user",
  email: "test@example.com",
  is_active: true
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ModelProvider>
          <App />
        </ModelProvider>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe("authentication routes", () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(getCurrentUser).mockResolvedValue(user)
    vi.mocked(listModels).mockResolvedValue({
      models: [],
      default_model: "",
      fallback_model: "",
      flash_model: "",
      image_model: ""
    })
    installBrowserStubs()
  })
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it("redirects a guest from a protected page to login", async () => {
    renderRoute("/library")
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeTruthy()
    expect(getCurrentUser).not.toHaveBeenCalled()
  })

  it("restores a session before rendering a protected page", async () => {
    localStorage.setItem("au.access_token", "test-token")
    renderRoute("/library")
    expect(await screen.findByRole("heading", { name: "Library" })).toBeTruthy()
    expect(getCurrentUser).toHaveBeenCalledOnce()
  })

  it("validates registration passwords before calling the API", async () => {
    renderRoute("/login")
    fireEvent.click(await screen.findByRole("button", { name: "Create one" }))
    fireEvent.change(screen.getByRole("textbox", { name: "Email" }), {
      target: { value: "test@example.com" }
    })
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" }
    })
    fireEvent.change(screen.getByLabelText("Ensure your password"), {
      target: { value: "different123" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }))
    expect((await screen.findByRole("alert")).textContent).toContain("Passwords do not match")
    expect(registerUser).not.toHaveBeenCalled()
  })

  it("signs in with the shadcn login form", async () => {
    vi.mocked(loginUser).mockResolvedValue({
      access_token: "test-token",
      token_type: "bearer",
      user
    })
    renderRoute("/login")
    fireEvent.change(await screen.findByRole("textbox", { name: "Email" }), {
      target: { value: " Test@Example.com " }
    })
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }))

    await waitFor(() => expect(loginUser).toHaveBeenCalledWith({
      email: "test@example.com",
      password: "password123"
    }))
    expect(localStorage.getItem("au.access_token")).toBe("test-token")
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Welcome back" })).toBeNull())
  })

  it("registers an account and returns to sign in", async () => {
    vi.mocked(registerUser).mockResolvedValue(user)
    renderRoute("/login")
    fireEvent.click(await screen.findByRole("button", { name: "Create one" }))
    fireEvent.change(screen.getByRole("textbox", { name: "Email" }), {
      target: { value: "Test@Example.com" }
    })
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" }
    })
    fireEvent.change(screen.getByLabelText("Ensure your password"), {
      target: { value: "password123" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }))

    await waitFor(() => expect(registerUser).toHaveBeenCalledWith({
      email: "test@example.com",
      password: "password123"
    }))
    expect((await screen.findByRole("alert")).textContent).toContain("Account created successfully")
    expect(screen.getByRole("button", { name: "Sign In" })).toBeTruthy()
  })

  it("uses the shadcn sidebar for navigation and account actions", async () => {
    localStorage.setItem("au.access_token", "test-token")
    const { container } = renderRoute("/library")
    expect(await screen.findByRole("heading", { name: "Library" })).toBeTruthy()
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeTruthy()
    expect(screen.getByRole("link", { name: "Agent" }).getAttribute("href")).toBe("/agent")

    const sidebar = container.querySelector('[data-slot="sidebar"][data-state]')
    expect(sidebar?.getAttribute("data-state")).toBe("expanded")
    const sidebarTrigger = container.querySelector(
      '[data-sidebar="trigger"]',
    ) as HTMLButtonElement
    fireEvent.click(sidebarTrigger)
    expect(sidebar?.getAttribute("data-state")).toBe("collapsed")
    fireEvent.click(sidebarTrigger)
    expect(sidebar?.getAttribute("data-state")).toBe("expanded")

    fireEvent.click(screen.getByRole("button", { name: "Open AM User account menu" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Settings" }))
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Account" }))
    expect(
      within(screen.getByRole("dialog", { name: "Settings" })).getByText(
        "test@example.com",
      ),
    ).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "General" }))
    fireEvent.click(screen.getByRole("combobox", { name: "Theme" }))
    expect(screen.getByRole("option", { name: "Dark" })).toBeTruthy()
  })

  it("opens the mobile sidebar and closes it after navigation", async () => {
    vi.stubGlobal("innerWidth", 375)
    localStorage.setItem("au.access_token", "test-token")
    renderRoute("/library")
    expect(await screen.findByRole("heading", { name: "Library" })).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "Toggle Sidebar" }))
    const sidebar = await screen.findByRole("dialog")
    fireEvent.click(within(sidebar).getByRole("link", { name: "Agent" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("shows the shared sidebar on the knowledge route", async () => {
    localStorage.setItem("au.access_token", "test-token")
    renderRoute("/knowledge")
    expect(await screen.findByRole("heading", { name: "Knowledge Chat" })).toBeTruthy()
    expect(screen.getAllByRole("navigation", { name: "Primary navigation" })).toHaveLength(1)
  })
})
