import { forwardRef, useEffect, useImperativeHandle, useRef } from "react"
import mapboxgl from "mapbox-gl"
import { useTheme } from "next-themes"
import "mapbox-gl/dist/mapbox-gl.css"

import { useTranslation } from "@/i18n"
import type { MapPlace } from "../map-places"
import { MapExampleCanvas } from "./MapExampleCanvas"

export type MapStatus = "unconfigured" | "loading" | "ready" | "error"
export interface MapCanvasHandle {
  zoom: (amount: number) => void
  reset: () => void
  focus: (coordinate: [number, number]) => void
}
export interface MapCanvasProps {
  apiKey?: string
  isExample: boolean
  layer: "vec" | "img"
  showLabels: boolean
  places: MapPlace[]
  selectedId: string | null
  reload: number
  onSelect: (id: string | null) => void
  onStatus: (status: MapStatus) => void
}

const center: [number, number] = [120.148, 30.247]
function duration(ms: number) {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : ms
}
function applyLabels(map: mapboxgl.Map, visible: boolean) {
  for (const layer of map.getStyle()?.layers ?? []) {
    if (layer.type === "symbol") map.setLayoutProperty(layer.id, "visibility", visible ? "visible" : "none")
  }
}

const LiveMapCanvas = forwardRef<MapCanvasHandle, MapCanvasProps>(function LiveMapCanvas(
  { apiKey, layer, showLabels, places, selectedId, reload, onSelect, onStatus }, ref,
) {
  const { t } = useTranslation()
  const { resolvedTheme } = useTheme()
  const element = useRef<HTMLDivElement>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const markers = useRef<Map<string, mapboxgl.Marker>>(new Map())
  const callbacks = useRef({ onSelect, onStatus })
  callbacks.current = { onSelect, onStatus }
  const loading = useRef(false)
  const labels = useRef(showLabels)
  labels.current = showLabels
  const style = layer === "img" ? "mapbox://styles/mapbox/satellite-streets-v12" : resolvedTheme === "dark" ? "mapbox://styles/mapbox/dark-v11" : "mapbox://styles/mapbox/streets-v12"
  const currentStyle = useRef(style)
  currentStyle.current = style
  const retainedView = useRef<{ center: [number, number]; zoom: number; bearing: number; pitch: number } | null>(null)

  useImperativeHandle(ref, () => ({
    zoom: (amount) => { const map = mapRef.current; if (map) map.easeTo({ zoom: map.getZoom() + amount, duration: duration(220) }) },
    reset: () => { mapRef.current?.easeTo({ center, zoom: 14, bearing: 0, pitch: 0, duration: duration(350) }) },
    focus: (coordinate) => { mapRef.current?.easeTo({ center: coordinate, zoom: 15, duration: duration(350) }) },
  }), [])

  useEffect(() => {
    if (!element.current || !apiKey) { callbacks.current.onStatus("unconfigured"); return }
    loading.current = true
    callbacks.current.onStatus("loading")
    let map: mapboxgl.Map
    try {
      map = new mapboxgl.Map({
        container: element.current, accessToken: apiKey, style: currentStyle.current,
        center, zoom: 14, ...retainedView.current, minZoom: 2, maxZoom: 20,
        attributionControl: false,
      })
    } catch {
      callbacks.current.onStatus("error")
      return
    }
    mapRef.current = map
    map.addControl(new mapboxgl.AttributionControl({ compact: true }), "bottom-right")
    map.on("style.load", () => applyLabels(map, labels.current))
    const timeout = window.setTimeout(() => { if (loading.current) callbacks.current.onStatus("error") }, 15000)
    map.on("idle", () => {
      window.clearTimeout(timeout)
      if (loading.current) { loading.current = false; callbacks.current.onStatus("ready") }
    })
    map.on("error", () => { if (loading.current) callbacks.current.onStatus("error") })
    map.on("click", () => callbacks.current.onSelect(null))
    const resize = new ResizeObserver(() => map.resize())
    resize.observe(element.current)
    const activeMarkers = markers.current
    return () => {
      window.clearTimeout(timeout)
      resize.disconnect()
      retainedView.current = { center: map.getCenter().toArray(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() }
      activeMarkers.forEach((marker) => marker.remove())
      activeMarkers.clear()
      mapRef.current = null
      map.remove()
    }
  }, [apiKey, reload])

  useEffect(() => {
    const map = mapRef.current
    if (map) { loading.current = true; callbacks.current.onStatus("loading"); map.setStyle(style) }
  }, [style])

  useEffect(() => {
    const map = mapRef.current
    if (map?.isStyleLoaded()) applyLabels(map, showLabels)
  }, [showLabels])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const activeMarkers = markers.current
    activeMarkers.forEach((marker) => marker.remove())
    activeMarkers.clear()
    places.forEach((place, index) => {
      const button = document.createElement("button")
      button.type = "button"
      button.className = "map-marker"
      button.textContent = String(index + 1)
      button.setAttribute("aria-label", t("Select {{name}}", { name: t(place.name) }))
      button.addEventListener("click", (event) => { event.stopPropagation(); callbacks.current.onSelect(place.id) })
      const marker = new mapboxgl.Marker({ element: button }).setLngLat(place.coordinate).addTo(map)
      activeMarkers.set(place.id, marker)
    })
    return () => { activeMarkers.forEach((marker) => marker.remove()); activeMarkers.clear() }
  }, [places, apiKey, reload, t])

  useEffect(() => {
    markers.current.forEach((marker, id) => marker.getElement().setAttribute("aria-pressed", String(id === selectedId)))
  }, [selectedId, places, apiKey, reload, t])

  return <div ref={element} className="h-full w-full" />
})

export const MapCanvas = forwardRef<MapCanvasHandle, MapCanvasProps>(function MapCanvas(props, ref) {
  return props.isExample ? <MapExampleCanvas {...props} ref={ref} /> : <LiveMapCanvas {...props} ref={ref} />
})
