import { forwardRef, useEffect, useImperativeHandle, useRef } from "react"
import Feature from "ol/Feature.js"
import Map from "ol/Map.js"
import View from "ol/View.js"
import Point from "ol/geom/Point.js"
import ImageLayer from "ol/layer/Image.js"
import TileLayer from "ol/layer/Tile.js"
import VectorLayer from "ol/layer/Vector.js"
import { unByKey } from "ol/Observable.js"
import { fromLonLat, transformExtent } from "ol/proj.js"
import ImageStatic from "ol/source/ImageStatic.js"
import ImageTile from "ol/source/ImageTile.js"
import VectorSource from "ol/source/Vector.js"
import { Circle, Fill, Stroke, Style, Text } from "ol/style.js"
import "ol/ol.css"

import exampleMapUrl from "../assets/example-map.svg"
import type { MapPlace } from "../map-places"

export type MapStatus = "unconfigured" | "loading" | "ready" | "error"
export interface MapCanvasHandle {
  zoom: (amount: number) => void
  reset: () => void
  focus: (coordinate: [number, number]) => void
}
interface MapCanvasProps {
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

function tileUrl(layer: "img" | "cia" | "vec" | "cva", key: string) {
  return `https://t0.tianditu.gov.cn/${layer}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${layer}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${encodeURIComponent(key)}`
}

export const MapCanvas = forwardRef<MapCanvasHandle, MapCanvasProps>(function MapCanvas(
  { apiKey, isExample, layer, showLabels, places, selectedId, reload, onSelect, onStatus }, ref,
) {
  const element = useRef<HTMLDivElement>(null)
  const mapRef = useRef<Map | null>(null)
  const mode = useRef(isExample)
  mode.current = isExample
  const retainedView = useRef<{ example: boolean; center: number[]; zoom: number; rotation: number } | null>(null)
  const duration = (ms: number) => window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : ms
  const markerSource = useRef(new VectorSource<Feature<Point>>())
  const selected = useRef(selectedId)
  const selectHandler = useRef(onSelect)
  selected.current = selectedId
  selectHandler.current = onSelect

  useImperativeHandle(ref, () => ({
    zoom: (amount) => {
      const view = mapRef.current?.getView()
      if (view) view.animate({ zoom: (view.getZoom() ?? 13) + amount, duration: duration(220) })
    },
    reset: () => mapRef.current?.getView().animate({ center: fromLonLat([120.148, 30.247]), zoom: mode.current ? 13.3 : 14, rotation: 0, duration: duration(350) }),
    focus: (coordinate) => mapRef.current?.getView().animate({ center: fromLonLat(coordinate), zoom: mode.current ? 14 : 15, duration: duration(350) }),
  }), [])

  useEffect(() => {
    if (!element.current || (!apiKey && !isExample)) {
      onStatus("unconfigured")
      return
    }
    onStatus("loading")
    const source = markerSource.current
    const colors = getComputedStyle(element.current)
    const primary = colors.color
    const markers = new VectorLayer({
      source,
      style: (feature) => {
        const active = feature.get("placeId") === selected.current
        return new Style({
          image: new Circle({ radius: active ? 19 : 15, fill: new Fill({ color: active ? primary : "#fff" }), stroke: new Stroke({ color: active ? "#fff" : primary, width: active ? 4 : 2 }) }),
          text: new Text({ text: String(feature.get("number")), font: "600 13px sans-serif", fill: new Fill({ color: active ? "#fff" : primary }) }),
          zIndex: active ? 2 : 1,
        })
      },
    })
    const imagery = apiKey && !isExample ? new ImageTile({ url: tileUrl(layer, apiKey), attributions: '<a href="https://www.tianditu.gov.cn/" target="_blank" rel="noreferrer">© 天地图</a>' }) : null
    const example = isExample ? new ImageStatic({ url: exampleMapUrl, imageExtent: transformExtent([120.08, 30.18, 120.22, 30.30], "EPSG:4326", "EPSG:3857") }) : null
    const previous = retainedView.current?.example === isExample ? retainedView.current : null
    const map = new Map({
      target: element.current,
      controls: [],
      layers: [
        ...(example ? [new ImageLayer({ source: example })] : []),
        ...(imagery ? [new TileLayer({ source: imagery }), new TileLayer({ source: new ImageTile({ url: tileUrl(layer === "img" ? "cia" : "cva", apiKey!) }), visible: showLabels })] : []),
        markers,
      ],
      view: new View({ center: previous?.center ?? fromLonLat([120.148, 30.247]), zoom: previous?.zoom ?? (isExample ? 13.3 : 14), rotation: previous?.rotation ?? 0, minZoom: isExample ? 13 : 3, maxZoom: 18, ...(isExample ? { extent: transformExtent([120.08, 30.18, 120.22, 30.30], "EPSG:4326", "EPSG:3857") } : {}) }),
    })
    mapRef.current = map
    let hasLoaded = false
    const ready = () => { hasLoaded = true; onStatus("ready") }
    const failed = () => { if (!hasLoaded) onStatus("error") }
    const keys = [
      ...(imagery ? [imagery.on("tileloadend", ready), imagery.on("tileloaderror", failed)] : []),
      ...(example ? [example.on("imageloadend", ready), example.on("imageloaderror", failed)] : []),
      map.on("singleclick", (event) => {
        const feature = map.forEachFeatureAtPixel(event.pixel, (hit) => hit, { hitTolerance: 8 })
        selectHandler.current(feature?.get("placeId") ?? null)
      }),
      map.on("pointermove", (event) => {
        if (element.current) element.current.style.cursor = map.hasFeatureAtPixel(event.pixel, { hitTolerance: 8 }) ? "pointer" : "grab"
      }),
    ]
    const timeout = window.setTimeout(failed, 12000)
    const resize = new ResizeObserver(() => map.updateSize())
    resize.observe(element.current)
    return () => {
      window.clearTimeout(timeout)
      resize.disconnect()
      unByKey(keys)
      const view = map.getView()
      retainedView.current = { example: isExample, center: view.getCenter() ?? fromLonLat([120.148, 30.247]), zoom: view.getZoom() ?? 14, rotation: view.getRotation() }
      mapRef.current = null
      map.setTarget(undefined)
      // Map disposal does not dispose its layers. Detach them so retained
      // marker sources cannot keep old maps and renderers alive on rebuild.
      for (const oldLayer of [...map.getLayers().getArray()]) {
        map.removeLayer(oldLayer)
        oldLayer.dispose()
      }
      imagery?.dispose()
      example?.dispose()
      map.dispose()
    }
  }, [apiKey, isExample, layer, showLabels, reload, onStatus])

  useEffect(() => {
    markerSource.current.clear()
    markerSource.current.addFeatures(places.map((place, index) => new Feature({ geometry: new Point(fromLonLat(place.coordinate)), placeId: place.id, number: index + 1 })))
  }, [places])

  useEffect(() => { markerSource.current.changed() }, [selectedId])

  return <div ref={element} className="absolute inset-0 text-primary" aria-hidden="true" />
})
