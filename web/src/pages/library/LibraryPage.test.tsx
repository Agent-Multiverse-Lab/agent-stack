import { afterEach, expect, it } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import LibraryPage from "@/pages/library/LibraryPage"
import { installBrowserStubs } from "@/test/browserStubs"

afterEach(cleanup)

it("combines category and text filters for library items", () => {
  installBrowserStubs()
  render(<LibraryPage />)
  fireEvent.click(screen.getByRole("button", { name: "Images" }))
  expect(screen.getByText("Hero_Banner_v2.png")).toBeTruthy()
  expect(screen.queryByText("Product_Architecture_Spec.pdf")).toBeNull()

  fireEvent.change(screen.getByPlaceholderText("Search..."), {
    target: { value: "not-present" }
  })
  expect(screen.getByText("No items found")).toBeTruthy()
})

it("filters items from the type menu", async () => {
  installBrowserStubs()
  render(<LibraryPage />)
  fireEvent.click(screen.getByRole("button", { name: /All Types/ }))
  fireEvent.click(await screen.findByRole("menuitemradio", { name: "Image" }))
  expect(screen.getByText("Hero_Banner_v2.png")).toBeTruthy()
  expect(screen.queryByText("Product_Architecture_Spec.pdf")).toBeNull()
})

it("creates a folder through the library dialog", async () => {
  installBrowserStubs()
  render(<LibraryPage />)
  fireEvent.click(screen.getByRole("button", { name: "New" }))
  fireEvent.click(await screen.findByRole("menuitem", { name: "New folder" }))
  expect(screen.getByRole("dialog", { name: "Create New Folder" })).toBeTruthy()
  fireEvent.change(screen.getByPlaceholderText("e.g. Project Assets"), {
    target: { value: "Research" },
  })
  fireEvent.click(screen.getByRole("button", { name: "Create" }))
  expect(screen.queryByRole("dialog", { name: "Create New Folder" })).toBeNull()
  expect(screen.getByText("Research")).toBeTruthy()
})
