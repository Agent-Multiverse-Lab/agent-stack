import { useCallback, useMemo, useRef, useState, type FormEvent } from "react"
import { ArrowDownLeft, ArrowUp, ArrowUpRight, Check, ChevronDown, Compass, Layers2, MapPin, MapPinned, Minus, Plus, RotateCcw, Search, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { useTranslation } from "@/i18n"
import { cn } from "@/lib/utils"
import { MapCanvas, type MapCanvasHandle, type MapStatus } from "./components/MapCanvas"
import { examplePlaces, formatCoordinate, parseCoordinate, type MapPlace } from "./map-places"
import "./map-page.css"

export default function MapPage() {
  const { t } = useTranslation()
  const apiKey = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN?.trim()
  const canvas = useRef<MapCanvasHandle>(null)
  const search = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState<MapStatus>(apiKey ? "loading" : "unconfigured")
  const [isExample, setIsExample] = useState(false)
  const [query, setQuery] = useState("")
  const [submittedQuery, setSubmittedQuery] = useState("")
  const [filter, setFilter] = useState<"all" | "Waterfront" | "Landscape">("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [coordinatePlace, setCoordinatePlace] = useState<MapPlace | null>(null)
  const [queryError, setQueryError] = useState("")
  const [layer, setLayer] = useState<"vec" | "img">("vec")
  const [showLabels, setShowLabels] = useState(true)
  const [layersOpen, setLayersOpen] = useState(false)
  const [reload, setReload] = useState(0)
  const [panelOpen, setPanelOpen] = useState(true)
  const onStatus = useCallback((value: MapStatus) => setStatus(value), [])
  const places = useMemo(() => {
    if (coordinatePlace) return [coordinatePlace]
    if (!isExample) return []
    const keyword = submittedQuery.trim().toLocaleLowerCase()
    return examplePlaces.filter((place) => (filter === "all" || place.category === filter) && (!keyword || `${t(place.name)} ${t(place.category)} ${t(place.description)}`.toLocaleLowerCase().includes(keyword)))
  }, [coordinatePlace, isExample, submittedQuery, filter, t])
  const selectedPlace = places.find((place) => place.id === selectedId)
  const canUseMap = isExample || Boolean(apiKey)

  function selectPlace(id: string | null) {
    setSelectedId(id)
    const place = places.find((item) => item.id === id)
    if (place) canvas.current?.focus(place.coordinate)
  }
  function reset() {
    setQuery(""); setSubmittedQuery(""); setQueryError(""); setCoordinatePlace(null); setSelectedId(null); setFilter("all")
    canvas.current?.reset()
  }
  function startExample() {
    reset(); setIsExample(true); setLayer("vec"); setLayersOpen(false)
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return
    setSelectedId(null); setQueryError("")
    const coordinate = parseCoordinate(query)
    if (coordinate) {
      if (!apiKey || isExample) { setQueryError(t("Coordinate search is unavailable in this view")); return }
      const place: MapPlace = { id: "coordinate", name: "Coordinate location", description: "Location entered by you", category: "Coordinates", coordinate }
      setCoordinatePlace(place); setSubmittedQuery(query.trim()); setSelectedId(place.id)
      canvas.current?.focus(coordinate)
    } else if (isExample) {
      setCoordinatePlace(null); setSubmittedQuery(query.trim()); setFilter("all")
    } else { setQueryError(t("Enter longitude, latitude. Place search is unavailable.")) }
  }

  return (
    <main className="map-workspace flex h-full min-h-0 flex-col overflow-hidden bg-background text-foreground" aria-label={t("Map")}>
      <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-(--page-padding)">
        <h1 className="truncate text-sm font-medium">{t("Map")}</h1>
        <Button variant="ghost" size="sm" className="gap-2" onClick={() => { reset(); setPanelOpen(true) }}><RotateCcw className="size-3.5" />{t("New exploration")}</Button>
      </header>
      <div className="relative min-h-0 flex-1">
        {panelOpen && <aside className="map-explorer map-float absolute top-5 left-5 z-20 flex max-h-[calc(100%_-_40px)] w-[352px] flex-col overflow-hidden rounded-2xl">
          <div className="flex items-center justify-between px-5 pt-4 pb-3"><div className="flex items-center gap-2 text-xs font-medium text-muted-foreground"><Compass className="size-3.5" />{t("Explore")}</div><div className="flex items-center gap-1"><Button variant="ghost" size="icon-xs" aria-label={t("Collapse exploration panel")} onClick={() => setPanelOpen(false)}><ArrowDownLeft className="size-4" /></Button></div></div>
          <div className="px-4 pb-3"><form onSubmit={submit} className="rounded-xl border border-input bg-background p-2 focus-within:border-primary focus-within:ring-2 focus-within:ring-ring/30">
            <Input ref={search} value={query} onChange={(event) => setQuery(event.target.value)} aria-label={t("Search map")} placeholder={t(isExample ? "Search example locations…" : "Enter longitude, latitude…")} className="h-10 border-0 bg-transparent px-2 shadow-none focus-visible:ring-0" />
            <div className="flex items-center justify-between px-1 pb-1 pt-2"><span className="flex items-center gap-1.5 text-[10px] text-muted-foreground"><MapPin className="size-3" />{t(isExample ? "Local examples" : "Coordinate search")}</span><Button type="submit" size="icon-sm" disabled={!query.trim()} aria-label={t("Search map")} className="rounded-full"><ArrowUp className="size-4" /></Button></div>
          </form>{queryError && <p role="alert" className="mt-2 px-1 text-xs text-destructive">{queryError}</p>}</div>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5">
            {!submittedQuery && <h2 className="pt-2 text-lg font-semibold">{t("Start with a location")}</h2>}
            {isExample && <p className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-selection px-2 py-1 text-[11px] text-selection-foreground"><span className="size-1.5 rounded-full bg-primary" />{t("Local example · No live results")}</p>}
            {submittedQuery && <div className="mt-6 flex justify-end"><p className="max-w-full rounded-xl rounded-tr-sm bg-secondary px-3 py-2 text-sm break-words">{submittedQuery}</p></div>}
            {canUseMap && (isExample || places.length > 0) ? <>
              <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground"><span>{t("Locations in view")}</span><span className="tabular-nums">{places.length.toString().padStart(2, "0")}</span></div>
              {isExample && <div className="mt-3 flex gap-1.5" aria-label={t("Filter locations")}>{(["all", "Waterfront", "Landscape"] as const).map((value) => <Button key={value} variant={filter === value ? "secondary" : "ghost"} size="sm" className="rounded-full px-3" aria-pressed={filter === value} onClick={() => { setFilter(value); setSelectedId(null) }}>{t(value === "all" ? "All locations" : value)}</Button>)}</div>}
              <ol className="mt-4 grid gap-2" aria-label={t("Location results")}>{places.map((place, index) => <li key={place.id}>
                <Button variant="ghost" className={cn("map-place h-auto w-full items-start justify-start gap-3 rounded-xl border px-3 py-4 text-left whitespace-normal", selectedId === place.id ? "border-primary/30 bg-selection" : "border-transparent")} onClick={() => selectPlace(place.id)} aria-pressed={selectedId === place.id} aria-label={t("Select {{name}}", { name: t(place.name) })}>
                  <span className={cn("mt-0.5 grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold", selectedId === place.id ? "bg-primary text-primary-foreground" : "bg-secondary text-foreground")}>{index + 1}</span>
                  <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">{t(place.name)}</span><span className="mt-1 block text-xs text-muted-foreground">{t(place.category)} · {t(isExample ? "Example location" : "Coordinates")}</span><span className="mt-2.5 block font-mono text-[10px] tracking-tight text-muted-foreground">{formatCoordinate(place.coordinate)}</span></span><ArrowUpRight className="mt-1 size-3.5 text-muted-foreground" />
                </Button>
              </li>)}</ol>
              {places.length === 0 && <div className="py-10 text-center"><Search className="mx-auto size-6 text-muted-foreground" /><p className="mt-3 text-sm">{t("No matching locations")}</p><Button variant="link" className="mt-2" onClick={reset}>{t("Clear search")}</Button></div>}
              {selectedPlace && <div className="mt-5 border-t border-border pt-5" aria-live="polite"><div className="mb-3 flex items-center justify-between"><span className="text-xs font-medium text-muted-foreground">{t("About this location")}</span><Button size="icon-xs" variant="ghost" aria-label={t("Close location details")} onClick={() => setSelectedId(null)}><X className="size-3.5" /></Button></div><p className="text-sm leading-6">{t(selectedPlace.description)}</p></div>}
            </> : <div className="mt-3 space-y-3">
              <div><p className="text-xs leading-5 text-muted-foreground">{t("Use longitude, latitude to focus your map.")}</p><Button variant="ghost" className="mt-3 h-7 p-0 text-xs" onClick={() => { setQuery("120.148, 30.247"); search.current?.focus() }}>120.148, 30.247 <ArrowUpRight className="size-3" /></Button></div>
              <Button variant="outline" className="h-auto w-full justify-between rounded-xl px-4 py-3 text-sm" onClick={startExample}><span className="flex items-center gap-2"><Compass className="size-4" />{t("Explore a local example")}</span><ArrowUpRight className="size-4" /></Button>
            </div>}
          </div>

        </aside>}
        <section className="map-stage absolute inset-0 overflow-hidden" aria-label={t("Map canvas")}>
          <MapCanvas ref={canvas} apiKey={apiKey} isExample={isExample} layer={layer} showLabels={showLabels} places={places} selectedId={selectedId} reload={reload} onSelect={selectPlace} onStatus={onStatus} />
          <div className="pointer-events-none absolute top-5 right-5 left-5 z-10 flex items-start justify-between gap-3"><div className="pointer-events-auto flex items-center gap-2">
            {!panelOpen && <Button variant="outline" size="icon-lg" className="map-float" aria-label={t("Open exploration panel")} onClick={() => setPanelOpen(true)}><Search /></Button>}

          </div>{isExample && <Button variant="outline" className="map-float pointer-events-auto h-10 text-xs" onClick={() => { reset(); setIsExample(false); setLayersOpen(false) }}><X className="size-3.5" />{t("Exit example")}</Button>}</div>
          {status !== "ready" && <div className="map-status pointer-events-none absolute inset-0 z-[5] grid place-items-center p-8"><div className="pointer-events-auto max-w-xs rounded-2xl bg-card/95 px-6 py-6 text-center shadow-sm">
            <span className="mx-auto mb-5 grid size-14 place-items-center rounded-2xl bg-selection text-primary"><MapPinned className="size-7" /></span><h2 className="text-lg font-semibold">{t(status === "unconfigured" ? "Map workspace" : status === "loading" ? "Loading map" : "Map tiles could not be loaded")}</h2>
            <p role={status === "error" ? "alert" : "status"} className="mt-3 text-sm text-muted-foreground">{t(status === "unconfigured" ? "Map unavailable" : status === "error" ? "Map could not load. Please retry." : "Preparing your map canvas…")}</p>
            {status === "unconfigured" && <Button className="mt-6" onClick={startExample}>{t("Explore a local example")}<ArrowUpRight /></Button>}
            {status === "error" && <Button variant="outline" className="mt-5" onClick={() => setReload((value) => value + 1)}><RotateCcw />{t("Retry")}</Button>}
          </div></div>}
          {selectedPlace && status === "ready" && <div className="map-selection map-float absolute right-20 bottom-12 z-10 flex w-[300px] max-w-[calc(100%_-_100px)] items-center gap-3 rounded-xl p-4"><span className="grid size-10 shrink-0 place-items-center rounded-lg bg-selection text-primary"><MapPin className="size-5" /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{t(selectedPlace.name)}</p><p className="mt-0.5 text-xs text-muted-foreground">{t(selectedPlace.category)} · {t(isExample ? "Example location" : "Coordinates")}</p></div><Button variant="ghost" size="icon-sm" aria-label={t("Dismiss map selection")} onClick={() => setSelectedId(null)}><X className="size-4" /></Button></div>}
          <div className="absolute right-5 bottom-12 z-10 flex flex-col gap-2"><Button variant="outline" size="icon-lg" className="map-float" aria-label={t("Reset map view")} disabled={!canUseMap} onClick={() => canvas.current?.reset()}><Compass className="size-4" /></Button><div className="map-float overflow-hidden rounded-lg"><Button variant="ghost" size="icon-lg" className="block rounded-none" aria-label={t("Zoom in")} disabled={!canUseMap} onClick={() => canvas.current?.zoom(1)}><Plus className="mx-auto size-4" /></Button><div className="mx-2 border-t border-border" /><Button variant="ghost" size="icon-lg" className="block rounded-none" aria-label={t("Zoom out")} disabled={!canUseMap} onClick={() => canvas.current?.zoom(-1)}><Minus className="mx-auto size-4" /></Button></div></div>
          <div className="map-layer-control absolute top-20 right-5 z-20 flex flex-col items-end">{layersOpen && <div className="map-float order-2 mt-2 w-60 rounded-xl p-4"><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium">{t("Map layers")}</h3><Button variant="ghost" size="icon-xs" aria-label={t("Close map layers")} onClick={() => setLayersOpen(false)}><X className="size-3.5" /></Button></div><div className="grid grid-cols-2 gap-2">{(["vec", "img"] as const).map((value) => <Button key={value} variant="outline" disabled={isExample && value === "img"} className={cn("h-auto flex-col gap-2 p-3 text-xs", layer === value && "bg-selection")} aria-pressed={layer === value} onClick={() => setLayer(value)}>{value === "vec" ? <MapPinned /> : <Layers2 />}{t(value === "vec" ? "Street map" : "Satellite map")}{layer === value && <Check className="size-3" />}</Button>)}</div><div className="mt-4 flex items-center justify-between text-xs"><span>{t("Place labels")}</span><Switch checked={showLabels} onCheckedChange={setShowLabels} disabled={isExample} aria-label={t("Place labels")} /></div>{isExample && <p className="mt-3 text-[10px] leading-4 text-muted-foreground">{t("Example map uses a fixed illustrative basemap.")}</p>}</div>}<Button variant="outline" className="map-float h-10" aria-expanded={layersOpen} onClick={() => setLayersOpen(!layersOpen)}><Layers2 className="size-4" />{t("Layers")}<ChevronDown className={cn("size-3 transition-transform", layersOpen && "rotate-180")} /></Button></div>
          {isExample && <div className="pointer-events-none absolute right-5 bottom-2 z-10 rounded bg-background/85 px-1.5 py-0.5 text-[10px] text-muted-foreground">{t("Illustrative basemap · Not for navigation")}</div>}
        </section>
      </div>
    </main>
  )
}
