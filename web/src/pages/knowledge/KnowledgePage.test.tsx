import { afterEach, expect, it } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"

import KnowledgePage from "@/pages/knowledge/KnowledgePage"

afterEach(cleanup)

it("adds local files and filters the file list by name", () => {
  const { container } = render(
    <MemoryRouter><KnowledgePage /></MemoryRouter>
  )
  const input = container.querySelector('input[type="file"]')
  expect(input).not.toBeNull()
  fireEvent.change(input!, {
    target: {
      files: [
        new File(["alpha"], "alpha.pdf", { type: "application/pdf" }),
        new File(["beta"], "beta.txt", { type: "text/plain" })
      ]
    }
  })
  expect(screen.getByText("alpha.pdf")).toBeTruthy()
  expect(screen.getByText("beta.txt")).toBeTruthy()

  fireEvent.change(screen.getByRole("textbox", { name: "Search files" }), {
    target: { value: "alpha" }
  })
  fireEvent.click(screen.getByRole("button", { name: /^Search$/ }))
  expect(screen.getByText("alpha.pdf")).toBeTruthy()
  expect(screen.queryByText("beta.txt")).toBeNull()
})

it("keeps a file until removal is confirmed", async () => {
  const { container } = render(<MemoryRouter><KnowledgePage /></MemoryRouter>)
  fireEvent.change(container.querySelector('input[type="file"]')!, {
    target: { files: [new File(["alpha"], "alpha.pdf", { type: "application/pdf" })] }
  })

  fireEvent.click(screen.getByRole("button", { name: "Open file actions" }))
  fireEvent.click(await screen.findByRole("menuitem", { name: "Remove from list" }))
  expect(screen.getByRole("dialog", { name: "Remove this file?" })).toBeTruthy()
  expect(screen.getByText("alpha.pdf")).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Keep file" }))
  expect(screen.getByText("alpha.pdf")).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Open file actions" }))
  fireEvent.click(await screen.findByRole("menuitem", { name: "Remove from list" }))
  fireEvent.click(screen.getByRole("button", { name: "Remove" }))
  expect(screen.queryByText("alpha.pdf")).toBeNull()
})
