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
