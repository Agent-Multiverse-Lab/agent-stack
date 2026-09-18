import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"

import App from "@/app/App"
import { AuthProvider } from "@/context/AuthContext"
import { ModelProvider } from "@/context/ModelContext"
import { getCurrentUser } from "@/api/auth"
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
})
