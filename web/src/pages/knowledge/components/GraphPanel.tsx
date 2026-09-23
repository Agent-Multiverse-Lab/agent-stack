import { useEffect, useMemo, useRef, useState } from "react"
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from "d3-force"
import type { SimulationNodeDatum } from "d3-force"
import { select } from "d3-selection"
import { zoom } from "d3-zoom"
import { Search, X } from "lucide-react"
import { getKnowledgeGraph, searchKnowledgeEntities } from "@/api/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { useTranslation } from "@/i18n"
import type { KnowledgeGraphResponse } from "@/types/knowledge"

const DEFAULT_SIZE = { width: 800, height: 600 }

interface PositionedNode extends SimulationNodeDatum {
  entity_id: string
  name: string
  type: string
  description: string
  file_id: string
}

export function GraphPanel({ kbId }: { kbId: string }) {
  const { t } = useTranslation()
  const [graph, setGraph] = useState<KnowledgeGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [size, setSize] = useState(DEFAULT_SIZE)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [matchedIds, setMatchedIds] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState("")
  const [searching, setSearching] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const gRef = useRef<SVGGElement>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError("")
    getKnowledgeGraph(kbId)
      .then((result) => {
        if (active) setGraph(result)
      })
      .catch((caught: unknown) => {
        if (active)
          setError(
            caught instanceof Error ? caught.message : t("Request failed")
          )
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [kbId, t])

  useEffect(() => {
    const container = containerRef.current
    if (!container || typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) setSize({ width, height })
      }
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!svgRef.current || !gRef.current) return
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 4])
      .on("zoom", (event) => {
        select(gRef.current).attr("transform", event.transform.toString())
      })
    select(svgRef.current).call(behavior)
    return () => {
      select(svgRef.current).on(".zoom", null)
    }
  }, [graph])

  const layout = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>()
    const nodes = graph?.nodes ?? []
    if (!nodes.length) return positions
    const positioned: PositionedNode[] = nodes.map((node) => ({ ...node }))
    const links = (graph?.edges ?? []).map((edge) => ({
      source: edge.source_entity_id,
      target: edge.target_entity_id,
    }))
    const simulation = forceSimulation(positioned)
      .force(
        "link",
        forceLink(links)
          .id((datum) => (datum as PositionedNode).entity_id)
          .distance(90)
      )
      .force("charge", forceManyBody().strength(-280))
      .force("center", forceCenter(size.width / 2, size.height / 2))
      .force("collide", forceCollide(28))
      .stop()
    for (let tick = 0; tick < 300; tick += 1) simulation.tick()
    for (const node of positioned) {
      positions.set(node.entity_id, {
        x: node.x ?? size.width / 2,
        y: node.y ?? size.height / 2,
      })
    }
    return positions
  }, [graph, size])

  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>()
    for (const edge of graph?.edges ?? []) {
      const source = map.get(edge.source_entity_id) ?? new Set<string>()
      const target = map.get(edge.target_entity_id) ?? new Set<string>()
      source.add(edge.target_entity_id)
      target.add(edge.source_entity_id)
      map.set(edge.source_entity_id, source)
      map.set(edge.target_entity_id, target)
    }
    return map
  }, [graph])

  const focus = useMemo(() => {
    if (!selectedId) return null
    const ids = new Set<string>([selectedId])
    for (const neighbor of adjacency.get(selectedId) ?? []) ids.add(neighbor)
    return ids
  }, [selectedId, adjacency])

  const selectedNode = graph?.nodes.find(
    (node) => node.entity_id === selectedId
  )

  async function handleSearch() {
    const text = query.trim()
    if (!text || searching) return
    setSearching(true)
    try {
      const result = await searchKnowledgeEntities(kbId, text)
      setMatchedIds(new Set(result.hits.map((hit) => hit.entity_id)))
    } catch (caught) {
      setMatchedIds(new Set())
    } finally {
      setSearching(false)
    }
  }

  function labelVisible(node: { entity_id: string }): boolean {
    return (
      focus?.has(node.entity_id) === true || matchedIds.has(node.entity_id)
    )
  }

  if (loading) {
    return (
      <div className="grid h-full place-items-center text-muted-foreground">
        <Spinner className="size-6" />
      </div>
    )
  }
  if (error) {
    return (
      <div className="grid h-full place-items-center text-sm text-muted-foreground">
        {error}
      </div>
    )
  }
  if (!graph?.nodes.length) {
    return (
      <div className="grid h-full place-items-center">
        <Empty>
          <EmptyTitle>{t("No entities yet")}</EmptyTitle>
          <EmptyDescription>{t("Extract graph")}</EmptyDescription>
        </Empty>
      </div>
    )
  }

  return (
    <div className="grid h-full min-h-0 [grid-template-columns:minmax(0,1fr)_auto]">
      <div
        ref={containerRef}
        className="relative min-h-0 min-w-0 overflow-hidden bg-background"
      >
        <form
          role="search"
          className="absolute left-4 top-4 z-10 flex w-64 items-center gap-1 rounded-lg border border-border bg-background p-1"
          onSubmit={(event) => {
            event.preventDefault()
            handleSearch()
          }}
        >
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("Search entities")}
            aria-label={t("Search entities")}
            className="min-w-0 border-0 bg-transparent px-2 py-1 focus-visible:ring-0"
          />
          {matchedIds.size > 0 && (
            <Button
              variant="ghost"
              type="button"
              size="sm"
              aria-label={t("Clear")}
              className="grid size-7 shrink-0 place-items-center rounded-full p-0 text-muted-foreground"
              onClick={() => {
                setMatchedIds(new Set())
                setQuery("")
              }}
            >
              <X size={14} />
            </Button>
          )}
          <Button
            variant="default"
            type="submit"
            aria-label={t("Search")}
            disabled={!query.trim() || searching}
            className="grid size-7 shrink-0 place-items-center rounded-full p-0"
          >
            {searching ? <Spinner className="size-3.5" /> : <Search size={14} />}
          </Button>
        </form>

        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          className="cursor-grab active:cursor-grabbing"
          onClick={() => setSelectedId(null)}
        >
          <g ref={gRef}>
            {graph.edges.map((edge) => {
              const source = layout.get(edge.source_entity_id)
              const target = layout.get(edge.target_entity_id)
              if (!source || !target) return null
              const highlighted =
                focus?.has(edge.source_entity_id) === true &&
                focus?.has(edge.target_entity_id) === true
              return (
                <line
                  key={edge.relation_id}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  className={
                    highlighted ? "stroke-primary" : "stroke-border"
                  }
                  strokeWidth={highlighted ? 1.5 : 1}
                />
              )
            })}
            {graph.nodes.map((node) => {
              const position = layout.get(node.entity_id)
              if (!position) return null
              const dimmed =
                focus !== null && !focus.has(node.entity_id)
              const matched = matchedIds.has(node.entity_id)
              return (
                <g
                  key={node.entity_id}
                  className="cursor-pointer"
                  style={{ opacity: dimmed ? 0.15 : 1 }}
                  onClick={(event) => {
                    event.stopPropagation()
                    setSelectedId(
                      node.entity_id === selectedId ? null : node.entity_id
                    )
                  }}
                >
                  <title>{node.name}</title>
                  <circle
                    cx={position.x}
                    cy={position.y}
                    r={10}
                    className={
                      matched
                        ? "fill-amber-500"
                        : node.entity_id === selectedId
                          ? "fill-primary"
                          : "fill-muted-foreground"
                    }
                  />
                  {matched && (
                    <circle
                      cx={position.x}
                      cy={position.y}
                      r={14}
                      className="fill-none stroke-amber-500"
                      strokeWidth={2}
                    />
                  )}
                  {labelVisible(node) && (
                    <text
                      x={position.x + 15}
                      y={position.y + 4}
                      className="fill-foreground text-[11px]"
                    >
                      {node.name}
                    </text>
                  )}
                </g>
              )
            })}
          </g>
        </svg>
      </div>

      {selectedNode && (
        <aside className="w-72 overflow-y-auto border-l border-border p-4 text-sm">
          <div className="flex items-start justify-between gap-2">
            <h2 className="min-w-0 break-words text-base font-semibold">
              {selectedNode.name}
            </h2>
            <Button
              variant="ghost"
              type="button"
              aria-label={t("Close")}
              className="grid size-7 shrink-0 place-items-center rounded-full p-0 text-muted-foreground"
              onClick={() => setSelectedId(null)}
            >
              <X size={14} />
            </Button>
          </div>
          {selectedNode.type && (
            <Badge variant="outline" className="mt-2">
              {selectedNode.type}
            </Badge>
          )}
          {selectedNode.description && (
            <p className="mt-3 whitespace-pre-wrap text-muted-foreground">
              {selectedNode.description}
            </p>
          )}
          <div className="mt-4 grid gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
            <div>
              {t("Relations")}: {adjacency.get(selectedNode.entity_id)?.size ?? 0}
            </div>
            <div className="truncate" title={selectedNode.file_id}>
              file: {selectedNode.file_id}
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}
