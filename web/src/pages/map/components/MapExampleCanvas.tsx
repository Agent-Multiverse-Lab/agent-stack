import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { useTranslation } from "@/i18n"
import exampleMapUrl from "../assets/example-map.svg"
import type { MapCanvasHandle, MapCanvasProps } from "./MapCanvas"

const width = 1400
const height = 1100
const initialCenter: [number, number] = [width / 2, height / 2]
function clampCenter(center: [number, number], scale: number): [number, number] {
  const halfWidth = width / (2 * scale)
  const halfHeight = height / (2 * scale)
  return [Math.min(width - halfWidth, Math.max(halfWidth, center[0])), Math.min(height - halfHeight, Math.max(halfHeight, center[1]))]
}
function project([longitude, latitude]: [number, number]): [number, number] {
  const mercator = (value: number) => Math.log(Math.tan(Math.PI / 4 + value * Math.PI / 360))
  return [(longitude - 120.08) / 0.14 * width, (mercator(30.30) - mercator(latitude)) / (mercator(30.30) - mercator(30.18)) * height]
}

export const MapExampleCanvas = forwardRef<MapCanvasHandle, MapCanvasProps>(function MapExampleCanvas(
  { places, selectedId, reload, onSelect, onStatus }, ref,
) {
  const { t } = useTranslation()
  const [view, setView] = useState({ center: initialCenter, scale: 1 })
  const container = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; center: [number, number]; moved: boolean } | null>(null)
  useImperativeHandle(ref, () => ({
    zoom: (amount) => setView((previous) => {
      const scale = Math.min(4, Math.max(1, previous.scale * 2 ** (amount / 2)))
      return { center: clampCenter(previous.center, scale), scale }
    }),
    reset: () => setView({ center: initialCenter, scale: 1 }),
    focus: (coordinate) => setView({ center: clampCenter(project(coordinate), 2), scale: 2 }),
  }), [])
  useEffect(() => { onStatus("loading") }, [onStatus, reload])
  const left = 50 - view.center[0] / width * view.scale * 100
  const top = 50 - view.center[1] / height * view.scale * 100
  return <div ref={container} className="absolute inset-0 touch-none overflow-hidden cursor-grab active:cursor-grabbing"
    onPointerDown={(event) => {
      if ((event.target as HTMLElement).closest("button")) return
      drag.current = { x: event.clientX, y: event.clientY, center: view.center, moved: false }
      event.currentTarget.setPointerCapture(event.pointerId)
    }}
    onPointerMove={(event) => {
      const start = drag.current
      const bounds = container.current?.getBoundingClientRect()
      if (!start || !bounds) return
      const dx = event.clientX - start.x
      const dy = event.clientY - start.y
      if (Math.abs(dx) + Math.abs(dy) > 4) start.moved = true
      setView((previous) => ({ ...previous, center: clampCenter([start.center[0] - dx / bounds.width * width / previous.scale, start.center[1] - dy / bounds.height * height / previous.scale], previous.scale) }))
    }}
    onPointerUp={(event) => {
      if (drag.current && !drag.current.moved) onSelect(null)
      drag.current = null
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    }}
    onPointerCancel={() => { drag.current = null }}
  >
    <div className="absolute" style={{ width: `${view.scale * 100}%`, height: `${view.scale * 100}%`, left: `${left}%`, top: `${top}%` }}>
      <img key={reload} src={exampleMapUrl} alt="" draggable={false} className="pointer-events-none absolute inset-0 h-full w-full object-fill" onLoad={() => onStatus("ready")} onError={() => onStatus("error")} />
      {places.map((place, index) => {
        const [x, y] = project(place.coordinate)
        return <Button key={place.id} variant="outline" size="icon" className="map-marker absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x / width * 100}%`, top: `${y / height * 100}%` }} aria-label={t("Select {{name}}", { name: t(place.name) })} aria-pressed={selectedId === place.id} onClick={(event) => { event.stopPropagation(); onSelect(place.id) }}>{index + 1}</Button>
      })}
    </div>
  </div>
})
