import { forwardRef, useEffect, useImperativeHandle } from "react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import i18n from "@/i18n"
import MapPage from "./MapPage"
import { parseCoordinate, formatCoordinate } from "./map-places"
import { installBrowserStubs } from "@/test/browserStubs"
import type { MapCanvasHandle, MapStatus } from "./components/MapCanvas"

const controls = vi.hoisted(() => ({ zoom: vi.fn(), reset: vi.fn(), focus: vi.fn() }))
vi.mock("./components/MapCanvas", () => ({
  MapCanvas: forwardRef<MapCanvasHandle, {isExample: boolean; onStatus: (status: MapStatus) => void}>(function Canvas({isExample,onStatus},ref) {
    useImperativeHandle(ref, () => controls, [])
    useEffect(() => onStatus(isExample ? "ready" : "unconfigured"), [isExample,onStatus])
    return <div data-testid="map-canvas" />
  }),
}))
beforeEach(async () => { installBrowserStubs(); vi.stubEnv("VITE_MAPBOX_ACCESS_TOKEN", ""); vi.clearAllMocks(); await i18n.changeLanguage("en") })
afterEach(() => { cleanup(); vi.unstubAllEnvs() })
function startExample() { fireEvent.click(screen.getAllByRole("button", { name: "Explore a local example" })[0]) }
it("shows honest live-map and service setup boundaries", () => {
  render(<MapPage />)
  expect(screen.getByRole("main", {name: "Map"})).toBeTruthy()
  expect(screen.getByText("Map unavailable")).toBeTruthy()
  expect(screen.queryByText("Catalog search is not connected")).toBeNull()
  expect(screen.queryByText("Map conversation is not connected")).toBeNull()
  expect(screen.queryByText(/VITE_MAPBOX_ACCESS_TOKEN/)).toBeNull()
  expect(screen.getByRole("button", {name: "Zoom in"}).hasAttribute("disabled")).toBe(true)
})
it("selects repeatedly, dismisses and resets local sample locations", () => {
  render(<MapPage />); startExample()
  expect(screen.getByText("Local example · No live results")).toBeTruthy()
  const select = screen.getByRole("button", {name: "Select Lakeside observation point"})
  fireEvent.click(select); fireEvent.click(select)
  expect(select.getAttribute("aria-pressed")).toBe("true")
  expect(controls.focus).toHaveBeenCalledTimes(2)
  fireEvent.click(screen.getByRole("button", {name: "Dismiss map selection"}))
  expect(select.getAttribute("aria-pressed")).toBe("false")
  fireEvent.click(screen.getByRole("button", {name: "Select Gushan observation point"}))
  fireEvent.click(screen.getByRole("button", {name: "New exploration"}))
  expect(screen.queryByRole("button", {name: "Dismiss map selection"})).toBeNull()
  expect(within(screen.getByRole("list", {name:"Location results"})).getAllByRole("listitem")).toHaveLength(3)
})
it("filters sample places and clears empty searches", () => {
  render(<MapPage />); startExample()
  fireEvent.click(screen.getByRole("button", {name:"Waterfront"}))
  expect(within(screen.getByRole("list", {name:"Location results"})).getAllByRole("listitem")).toHaveLength(1)
  fireEvent.change(screen.getByRole("textbox", {name:"Search map"}), {target:{value:"unmatched"}})
  fireEvent.click(screen.getByRole("button", {name:"Search map"}))
  expect(screen.getByText("No matching locations")).toBeTruthy()
  fireEvent.click(screen.getByRole("button", {name:"Clear search"}))
  expect(within(screen.getByRole("list", {name:"Location results"})).getAllByRole("listitem")).toHaveLength(3)
})
it("supports panel/layers dismissal and clears sample data on exit", () => {
  render(<MapPage />); startExample()
  fireEvent.click(screen.getByRole("button", {name:"Collapse exploration panel"}))
  expect(screen.queryByRole("textbox", {name:"Search map"})).toBeNull()
  fireEvent.click(screen.getByRole("button", {name:"Open exploration panel"}))
  fireEvent.click(screen.getByRole("button", {name:"Layers"}))
  expect(screen.getByRole("button", {name:"Satellite map"}).hasAttribute("disabled")).toBe(true)
  fireEvent.click(screen.getByRole("button", {name:"Close map layers"}))
  fireEvent.click(screen.getByRole("button", {name:"Exit example"}))
  expect(screen.getByText("Map unavailable")).toBeTruthy()
  expect(screen.queryByRole("list", {name:"Location results"})).toBeNull()
})
it("does not claim free-form or sample coordinate searches are live", () => {
  render(<MapPage />)
  fireEvent.change(screen.getByRole("textbox", {name:"Search map"}), {target:{value:"London"}})
  fireEvent.click(screen.getByRole("button", {name:"Search map"}))
  expect(screen.getByRole("alert").textContent).toContain("Place search is unavailable")
  startExample()
  fireEvent.change(screen.getByRole("textbox", {name:"Search map"}), {target:{value:"120.148, 30.247"}})
  fireEvent.click(screen.getByRole("button", {name:"Search map"}))
  expect(screen.getByRole("alert").textContent).toContain("Coordinate search is unavailable")
})
it("parses valid projected coordinates and rejects malformed/out-of-range input", () => {
  expect(parseCoordinate(" 120.148，30.247 ")).toEqual([120.148,30.247])
  expect(parseCoordinate("-73.9,40.7")).toEqual([-73.9,40.7])
  for (const value of ["", "a,b", "181,30", "120,90", "120,30,40", "0,Infinity"]) expect(parseCoordinate(value)).toBeNull()
  expect(formatCoordinate([-73.9,-40.7])).toBe("40.7000° S · 73.9000° W")
})

it("keeps exploration actions without a page corner title", () => {
  render(<MapPage />)
  expect(screen.queryByRole("heading", { name: "Map" })).toBeNull()
  expect(screen.getByRole("main", { name: "Map" })).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "New exploration" }))
  expect(controls.reset).toHaveBeenCalledTimes(1)
  expect(screen.getByRole("textbox", { name: "Search map" })).toBeTruthy()
})
