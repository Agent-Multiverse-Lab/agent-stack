import { useEffect, useRef, useState } from "react"
import { Link, useNavigate } from "react-router"
import { ArrowDownAZ, ArrowUpRight, BookOpen, FolderOpen, LayoutGrid, List, MoreHorizontal, Plus, Search, Trash2, X } from "lucide-react"
import { toast } from "sonner"

import { createKnowledgeBase, deleteKnowledgeBase, listKnowledgeBases } from "@/api/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Empty, EmptyDescription, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { useTranslation } from "@/i18n"
import type { KnowledgeBase } from "@/types/knowledge"

export default function KnowledgePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [bases, setBases] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)
  const [query, setQuery] = useState("")
  const [view, setView] = useState<"grid" | "list">("grid")
  const [sortByName, setSortByName] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<KnowledgeBase | null>(null)
  const mutationRef = useRef(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError("")
    listKnowledgeBases()
      .then((items) => { if (active) setBases(items) })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : t("Request failed"))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [t, reload])

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!name.trim() || mutationRef.current) return
    mutationRef.current = true
    setCreating(true)
    try {
      const base = await createKnowledgeBase({ name: name.trim(), description: description.trim() })
      setCreateOpen(false)
      setName("")
      setDescription("")
      navigate(`/knowledge/${base.kb_id}`)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : t("Request failed"))
    } finally {
      mutationRef.current = false
      setCreating(false)
    }
  }

  async function handleDelete() {
    if (!confirmDelete || mutationRef.current) return
    mutationRef.current = true
    setDeleting(true)
    try {
      await deleteKnowledgeBase(confirmDelete.kb_id)
      setBases((items) => items.filter((item) => item.kb_id !== confirmDelete.kb_id))
      toast.success(t("Knowledge base deleted"))
      setConfirmDelete(null)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : t("Request failed"))
    } finally {
      mutationRef.current = false
      setDeleting(false)
    }
  }

  const search = query.trim().toLocaleLowerCase()
  const visibleBases = bases.filter((base) => `${base.name} ${base.description}`.toLocaleLowerCase().includes(search))
  if (sortByName) visibleBases.sort((a, b) => a.name.localeCompare(b.name))

  return (
    <div role="region" aria-label={t("Knowledge Bases")} className="flex h-full min-w-0 flex-col overflow-y-auto bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col px-6 pb-6 pt-10 lg:px-12 lg:pt-14">
        <div className="mb-7 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
          <div className="flex items-center gap-2.5">
            <h2 className="text-sm font-medium">{t("All collections")}</h2>
            {!loading && !error && <Badge variant="secondary" className="rounded-md tabular-nums">{bases.length}</Badge>}
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Button type="button" className="h-9 gap-2" onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" />{t("Create knowledge base")}
            </Button>
            <div role="search" className="relative w-56 max-w-full">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("Search knowledge bases")} aria-label={t("Search knowledge bases")} className="h-9 pl-9 pr-8" />
              {query && <Button variant="ghost" size="icon-xs" aria-label={t("Clear search")} className="absolute right-1.5 top-1/2 -translate-y-1/2" onClick={() => setQuery("")}><X /></Button>}
            </div>
            <Button variant={sortByName ? "secondary" : "ghost"} size="icon" aria-label={t("Sort by name")} title={t("Sort by name")} aria-pressed={sortByName} onClick={() => setSortByName((value) => !value)}><ArrowDownAZ /></Button>
            <div className="flex items-center gap-0.5 border-l border-border pl-2" role="group" aria-label={t("Collection view")}>
              <Button variant={view === "grid" ? "secondary" : "ghost"} size="icon" aria-label={t("Grid view")} title={t("Grid view")} aria-pressed={view === "grid"} onClick={() => setView("grid")}><LayoutGrid /></Button>
              <Button variant={view === "list" ? "secondary" : "ghost"} size="icon" aria-label={t("List view")} title={t("List view")} aria-pressed={view === "list"} onClick={() => setView("list")}><List /></Button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="grid min-h-72 place-items-center text-muted-foreground" role="status" aria-label={t("Loading knowledge bases")}><Spinner className="size-6" /></div>
        ) : error ? (
          <Empty className="min-h-72"><EmptyMedia><BookOpen /></EmptyMedia><EmptyTitle>{t("Unable to load knowledge bases")}</EmptyTitle><EmptyDescription role="alert">{error}</EmptyDescription><Button variant="outline" onClick={() => setReload((value) => value + 1)}>{t("Retry")}</Button></Empty>
        ) : visibleBases.length ? (
          <ul className={view === "grid" ? "grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(min(100%,265px),1fr))]" : "grid gap-2"}>
            {visibleBases.map((base) => {
              const index = bases.indexOf(base) + 1
              return (
                <li key={base.kb_id} className={`group relative min-w-0 rounded-xl border border-border bg-card ${view === "grid" ? "" : "pr-10"}`}>
                  <Link to={`/knowledge/${base.kb_id}`} className={`block rounded-xl outline-none transition-colors duration-(--hover-transition-duration) ease-in-out hover:bg-accent/40 focus-visible:bg-accent ${view === "grid" ? "p-5" : "flex min-h-24 items-center gap-5 p-4"}`}>
                    <div aria-hidden="true" className={view === "grid" ? "relative mb-6 flex h-36 items-center justify-center overflow-hidden rounded-lg bg-muted/55" : "grid size-14 shrink-0 place-items-center rounded-lg bg-muted"}>
                      {view === "grid" ? <>
                        <span className="absolute left-3.5 top-3 font-mono text-[10px] text-muted-foreground">{String(index).padStart(2, "0")}</span>
                        <div className="relative h-24 w-32 text-primary">
                          <div className="absolute left-5 top-1 h-20 w-24 -rotate-12 rounded-md border border-primary/15 bg-background" />
                          <div className="absolute left-5 top-1 h-20 w-24 rotate-6 rounded-md border border-primary/20 bg-card px-4 pt-4">
                            <span className="mb-2 block h-1 w-7 rounded-full bg-primary/25" /><span className="mb-1.5 block h-0.5 w-full bg-border" /><span className="mb-1.5 block h-0.5 w-full bg-border" /><span className="block h-0.5 w-8 bg-border" />
                          </div>
                          <div className="absolute bottom-0 left-0 flex h-14 w-32 items-center rounded-md border border-primary/15 bg-selection px-4 text-selection-foreground"><BookOpen className="size-6" strokeWidth={1.35} /></div>
                        </div>
                      </> : <FolderOpen className="size-6 text-primary" strokeWidth={1.5} />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-[17px] font-medium tracking-tight">{base.name}</h3>
                      {base.description && <p className={`mt-2 text-[13px] leading-6 text-muted-foreground ${view === "grid" ? "line-clamp-2 min-h-12" : "truncate"}`}>{base.description}</p>}
                      {view === "grid" && !base.description && <div className="h-14" />}
                      <div className={`flex items-center justify-between gap-2 ${view === "grid" ? "mt-5 border-t border-border/70 pt-3" : "mt-2"}`}>
                        <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground"><span className={`size-1.5 rounded-full ${base.status === "active" ? "bg-success" : "bg-muted-foreground"}`} />{base.status === "active" ? t("Active") : base.status}</span>
                        {view === "grid" && <ArrowUpRight className="size-4 text-muted-foreground" />}
                      </div>
                    </div>
                    {view === "list" && <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" />}
                  </Link>
                  <DropdownMenu>
                    <DropdownMenuTrigger render={<Button variant="ghost" size="icon" />} aria-label={t("Collection actions for {{name}}", { name: base.name })} className="absolute right-3 top-3"><MoreHorizontal /></DropdownMenuTrigger>
                    <DropdownMenuContent align="end"><DropdownMenuItem variant="destructive" onClick={() => setConfirmDelete(base)}><Trash2 />{t("Delete knowledge base")}</DropdownMenuItem></DropdownMenuContent>
                  </DropdownMenu>
                </li>
              )
            })}
          </ul>
        ) : (
          <Empty className="min-h-80">
            <EmptyMedia className="mb-2 grid size-16 place-items-center rounded-2xl bg-muted text-primary">{search ? <Search className="size-7" /> : <BookOpen className="size-7" strokeWidth={1.4} />}</EmptyMedia>
            <EmptyTitle>{search ? t("No matching knowledge bases") : t("No knowledge bases yet")}</EmptyTitle>
            {search && <EmptyDescription>{t("Try a different name or keyword.")}</EmptyDescription>}
            <Button variant="outline" onClick={() => search ? setQuery("") : setCreateOpen(true)}>{search ? t("Clear search") : t("Create your first collection")}</Button>
          </Empty>
        )}
        {!loading && !error && <footer className="mt-auto flex items-center justify-between gap-4 pt-12 text-[11px] text-muted-foreground"><span>{t("{{count}} collections", { count: bases.length })}</span><span className="flex items-center gap-1.5"><BookOpen className="size-3" />{t("Your knowledge, connected")}</span></footer>}
      </div>

      <Dialog open={createOpen} onOpenChange={(open) => { if (!creating) setCreateOpen(open) }}>
        <DialogContent>
          <form onSubmit={handleCreate}>
            <DialogHeader><DialogTitle>{t("Create knowledge base")}</DialogTitle><DialogDescription className="sr-only">{t("Create knowledge base")}</DialogDescription></DialogHeader>
            <div className="grid gap-4 py-5">
              <div className="grid gap-2"><Label htmlFor="knowledge-name">{t("Knowledge base name")}</Label><Input id="knowledge-name" value={name} onChange={(event) => setName(event.target.value)} placeholder={t("Knowledge base name")} autoFocus disabled={creating} /></div>
              <div className="grid gap-2"><Label htmlFor="knowledge-description">{t("Description (optional)")}</Label><Textarea id="knowledge-description" value={description} onChange={(event) => setDescription(event.target.value)} rows={3} disabled={creating} /></div>
            </div>
            <DialogFooter><Button variant="ghost" type="button" disabled={creating} onClick={() => setCreateOpen(false)}>{t("Cancel")}</Button><Button type="submit" disabled={!name.trim() || creating}>{creating && <Spinner />}{t("Create knowledge base")}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog open={confirmDelete !== null} onOpenChange={(open) => { if (!open && !deleting) setConfirmDelete(null) }}>
        <DialogContent>
          <DialogHeader><DialogTitle>{t("Delete this knowledge base?")}</DialogTitle><DialogDescription>{t("This will permanently delete {{name}} and all of its files.", { name: confirmDelete?.name })}</DialogDescription></DialogHeader>
          <DialogFooter><Button variant="ghost" disabled={deleting} onClick={() => setConfirmDelete(null)}>{t("Cancel")}</Button><Button variant="destructive" disabled={deleting} onClick={handleDelete}>{deleting && <Spinner />}{t("Delete knowledge base")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
