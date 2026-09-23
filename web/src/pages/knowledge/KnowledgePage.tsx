import { useEffect, useState } from "react"
import { useNavigate } from "react-router"
import { BookOpen, MoreHorizontal, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
} from "@/api/knowledge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
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
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<KnowledgeBase | null>(null)

  useEffect(() => {
    let active = true
    loadBases()
    async function loadBases() {
      setLoading(true)
      setError("")
      try {
        const items = await listKnowledgeBases()
        if (active) setBases(items)
      } catch (caught) {
        if (active)
          setError(
            caught instanceof Error ? caught.message : t("Request failed")
          )
      } finally {
        if (active) setLoading(false)
      }
    }
    return () => {
      active = false
    }
  }, [t])

  async function refresh() {
    setError("")
    try {
      setBases(await listKnowledgeBases())
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : t("Request failed")
      )
    }
  }

  async function handleCreate() {
    setCreating(true)
    try {
      const base = await createKnowledgeBase({ name, description })
      setCreateOpen(false)
      setName("")
      setDescription("")
      await refresh()
      navigate(`/knowledge/${base.kb_id}`)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : t("Request failed"))
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return
    try {
      await deleteKnowledgeBase(confirmDelete.kb_id)
      toast.success(t("{{name}} will be permanently deleted.", { name: confirmDelete.name }))
      setConfirmDelete(null)
      await refresh()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : t("Request failed"))
    }
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background font-sans text-foreground">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-6">
        <h1 className="text-base font-semibold">{t("Knowledge Bases")}</h1>
        <Button
          type="button"
          variant="default"
          className="gap-2"
          onClick={() => setCreateOpen(true)}
        >
          <Plus size={16} />
          {t("Create knowledge base")}
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="grid min-h-48 place-items-center text-muted-foreground">
            <Spinner className="size-6" />
          </div>
        ) : error ? (
          <div className="grid min-h-48 place-items-center text-sm text-muted-foreground">
            {error}
          </div>
        ) : bases.length ? (
          <ul className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
            {bases.map((base) => (
              <li key={base.kb_id}>
                <Card
                  className="cursor-pointer hover:border-border"
                  onClick={() => navigate(`/knowledge/${base.kb_id}`)}
                >
                  <CardHeader className="pr-2">
                    <div className="flex min-w-0 items-start justify-between gap-2">
                      <div className="grid min-w-0 gap-1">
                        <CardTitle className="truncate">{base.name}</CardTitle>
                        <CardDescription className="line-clamp-2 min-h-8">
                          {base.description || t("Description (optional)")}
                        </CardDescription>
                      </div>
                      <CardAction>
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            aria-label={t("Open file actions")}
                            title={t("Open file actions")}
                            className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-accent"
                          >
                            <MoreHorizontal size={16} />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={(event) => {
                                event.stopPropagation()
                                setConfirmDelete(base)
                              }}
                            >
                              <Trash2 />
                              {t("Delete knowledge base")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </CardAction>
                    </div>
                  </CardHeader>
                </Card>
              </li>
            ))}
          </ul>
        ) : (
          <div className="grid min-h-48 place-items-center">
            <Empty>
              <EmptyMedia>
                <BookOpen />
              </EmptyMedia>
              <EmptyTitle>{t("No knowledge bases yet")}</EmptyTitle>
              <EmptyDescription>{t("Create knowledge base")}</EmptyDescription>
            </Empty>
          </div>
        )}
      </div>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          if (!open) setCreateOpen(false)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("Create knowledge base")}</DialogTitle>
            <DialogDescription>
              {t("Description (optional)")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("Knowledge base name")}
              aria-label={t("Knowledge base name")}
            />
            <Textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t("Description (optional)")}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              type="button"
              onClick={() => setCreateOpen(false)}
            >
              {t("Cancel")}
            </Button>
            <Button
              type="button"
              disabled={!name.trim() || creating}
              onClick={handleCreate}
            >
              {t("Create knowledge base")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={confirmDelete !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDelete(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("Delete this knowledge base?")}</DialogTitle>
            <DialogDescription>
              {t("This will permanently delete {{name}} and all of its files.", {
                name: confirmDelete?.name,
              })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              type="button"
              onClick={() => setConfirmDelete(null)}
            >
              {t("Cancel")}
            </Button>
            <Button
              variant="destructive"
              type="button"
              onClick={handleDelete}
            >
              {t("Delete knowledge base")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
