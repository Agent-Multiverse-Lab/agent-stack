import { useEffect, useRef, useState } from "react"
import { ArrowUpRight, Check, FileText, Files, MoreHorizontal, Search, Sparkles, Trash2, Upload, X } from "lucide-react"
import { toast } from "sonner"

import { deleteKnowledgeFile, extractKnowledgeFile, getKnowledgeFileMarkdown, indexKnowledgeFile, listKnowledgeFiles, parseKnowledgeFile, uploadKnowledgeFile } from "@/api/knowledge"
import { FileContentViewer } from "@/components/common/file-content-viewer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Empty, EmptyDescription, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useTranslation } from "@/i18n"
import type { KnowledgeFile, KnowledgeFileStatus } from "@/api/knowledge"

const supported = new Set(["pdf", "doc", "docx", "txt", "md", "markdown", "csv", "xls", "xlsx", "ppt", "pptx", "png", "jpg", "jpeg", "webp"])
const PROCESSING: KnowledgeFileStatus[] = ["parsing", "indexing", "extracting"]
const canParse = (file: KnowledgeFile) => file.status === "uploaded" || file.status === "failed"
const canExtract = (file: KnowledgeFile) => file.status === "indexed" || file.status === "extracted"

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function FilesPanel({ kbId }: { kbId: string }) {
  const { t } = useTranslation()
  const [files, setFiles] = useState<KnowledgeFile[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)
  const [query, setQuery] = useState("")
  const [uploading, setUploading] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [busyStatus, setBusyStatus] = useState<KnowledgeFileStatus | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [markdown, setMarkdown] = useState("")
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState("")
  const [previewReload, setPreviewReload] = useState(0)
  const [confirmDelete, setConfirmDelete] = useState<KnowledgeFile | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const mutationRef = useRef(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError("")
    listKnowledgeFiles(kbId)
      .then((items) => {
        if (!active) return
        setFiles(items)
        setSelectedId((current) => items.some((file) => file.file_id === current) ? current : items[0]?.file_id ?? null)
      })
      .catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : t("Request failed")) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [kbId, t, reload])

  const hasProcessing = files.some((file) => PROCESSING.includes(file.status))
  useEffect(() => {
    if (!hasProcessing) return
    let active = true
    let inFlight = false
    const timer = window.setInterval(async () => {
      if (inFlight) return
      inFlight = true
      try {
        const items = await listKnowledgeFiles(kbId)
        if (active) { setFiles(items); setError("") }
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : t("Request failed"))
      } finally { inFlight = false }
    }, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [hasProcessing, kbId, t])

  const selectedFile = files.find((file) => file.file_id === selectedId) ?? null
  useEffect(() => {
    let active = true
    setMarkdown("")
    setPreviewError("")
    setPreviewLoading(false)
    if (!selectedFile?.markdown_object_name) return
    setPreviewLoading(true)
    getKnowledgeFileMarkdown(kbId, selectedFile.file_id)
      .then((result) => { if (active) setMarkdown(result.markdown) })
      .catch((caught: unknown) => { if (active) setPreviewError(caught instanceof Error ? caught.message : t("Request failed")) })
      .finally(() => { if (active) setPreviewLoading(false) })
    return () => { active = false }
  }, [kbId, selectedFile?.file_id, selectedFile?.markdown_object_name, selectedFile?.status, previewReload, t])

  async function refresh() {
    try {
      const items = await listKnowledgeFiles(kbId)
      setFiles(items)
      setError("")
      setSelectedId((current) => items.some((file) => file.file_id === current) ? current : items[0]?.file_id ?? null)
    } catch (caught) { setError(caught instanceof Error ? caught.message : t("Request failed")) }
  }

  async function handleUpload(selected: File[]) {
    if (!selected.length || mutationRef.current) return
    mutationRef.current = true
    setUploading(true)
    try {
      for (const file of selected) {
        const extension = file.name.split(".").pop()?.toLowerCase() ?? ""
        if (!supported.has(extension)) { toast.warning(t("{{file}} is not a supported source type.", { file: file.name })); continue }
        try { await uploadKnowledgeFile(kbId, file) }
        catch (caught) { toast.error(caught instanceof Error ? caught.message : t("Request failed")) }
      }
      await refresh()
    } finally { mutationRef.current = false; setUploading(false) }
  }

  async function runOperation(file: KnowledgeFile, status: KnowledgeFileStatus) {
    if (mutationRef.current || PROCESSING.includes(file.status)) return
    if (status === "parsing" && !canParse(file)) return
    if (status === "indexing" && file.status !== "parsed") return
    if (status === "extracting" && !canExtract(file)) return
    mutationRef.current = true
    setBusyId(file.file_id)
    setBusyStatus(status)
    try {
      if (status === "parsing") { await parseKnowledgeFile(kbId, file.file_id); toast.success(t("Parsed")) }
      else if (status === "indexing") { await indexKnowledgeFile(kbId, file.file_id); toast.success(t("Indexed")) }
      else {
        const result = await extractKnowledgeFile(kbId, file.file_id)
        toast.success(t("Extracted: {{entities}} entities, {{relations}} relations", { entities: result.entity_count, relations: result.relation_count }))
      }
    } catch (caught) { toast.error(caught instanceof Error ? caught.message : t("Request failed")) }
    finally { await refresh(); mutationRef.current = false; setBusyId(null); setBusyStatus(null) }
  }

  async function handleDelete() {
    if (!confirmDelete || mutationRef.current || PROCESSING.includes(confirmDelete.status)) return
    mutationRef.current = true
    setDeleting(true)
    try {
      await deleteKnowledgeFile(kbId, confirmDelete.file_id)
      toast.success(t("File deleted"))
      setConfirmDelete(null)
      await refresh()
    } catch (caught) { toast.error(caught instanceof Error ? caught.message : t("Request failed")) }
    finally { mutationRef.current = false; setDeleting(false) }
  }

  const isBusy = (file: KnowledgeFile) => uploading || busyId !== null || deleting || PROCESSING.includes(file.status)
  const fileStatus = (file: KnowledgeFile) => busyId === file.file_id && busyStatus ? { ...file, status: busyStatus } : file
  const visibleFiles = files.filter((file) => file.original_file_name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
  const indexedCount = files.filter((file) => ["indexed", "extracting", "extracted"].includes(file.status)).length

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 px-6 py-5 lg:px-10">
        <div className="flex items-center gap-2.5"><h2 className="text-sm font-medium">{t("All documents")}</h2>{!loading && <Badge variant="secondary" className="rounded-md tabular-nums">{files.length}</Badge>}</div>
        <div className="flex items-center gap-3">
          <div role="search" className="relative w-48 xl:w-56"><Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("Search files")} aria-label={t("Search files")} className="h-9 pl-9 pr-8" />{query && <Button variant="ghost" size="icon-xs" className="absolute right-1.5 top-1/2 -translate-y-1/2" aria-label={t("Clear search")} onClick={() => setQuery("")}><X /></Button>}</div>
          <Button className="h-9" onClick={() => fileInput.current?.click()} disabled={uploading || busyId !== null || deleting}>{uploading ? <Spinner /> : <Upload />}{t("Upload files")}</Button>
          <Input ref={fileInput} type="file" multiple accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp" aria-label={t("Choose files to upload")} className="hidden" onChange={(event) => { handleUpload(Array.from(event.target.files ?? [])); event.target.value = "" }} />
        </div>
      </div>
      {loading ? <div className="grid flex-1 place-items-center text-muted-foreground" role="status" aria-label={t("Loading files")}><Spinner className="size-6" /></div> : error && !files.length ? (
        <Empty className="flex-1"><EmptyTitle>{t("Unable to load files")}</EmptyTitle><EmptyDescription role="alert">{error}</EmptyDescription><Button variant="outline" onClick={() => setReload((value) => value + 1)}>{t("Retry")}</Button></Empty>
      ) : !files.length ? (
        <Empty className="mx-6 mb-6 flex-1 rounded-xl border border-dashed border-border bg-card lg:mx-10">
          <EmptyMedia className="grid size-16 place-items-center rounded-2xl bg-muted text-primary"><Files className="size-7" strokeWidth={1.4} /></EmptyMedia><EmptyTitle>{t("Add your first documents")}</EmptyTitle><EmptyDescription>{t("Upload documents, then parse and index them to make them searchable.")}</EmptyDescription><Button variant="outline" disabled={uploading} onClick={() => fileInput.current?.click()}><Upload />{t("Choose files")}</Button><p className="mt-2 text-[11px] text-muted-foreground">{t("Documents, spreadsheets, presentations, and images")}</p>
        </Empty>
      ) : (
        <div className="mx-6 mb-5 grid min-h-0 flex-1 overflow-auto rounded-xl border border-border bg-card lg:mx-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(290px,0.85fr)] lg:overflow-hidden">
          <section className="flex min-h-64 min-w-0 flex-col lg:min-h-0" aria-label={t("Documents")}>
            {error && <div role="alert" className="flex items-center justify-between gap-3 border-b border-border px-4 py-2 text-xs text-destructive"><span>{error}</span><Button variant="ghost" size="sm" onClick={refresh}>{t("Retry")}</Button></div>}
            <div className="min-h-0 flex-1 overflow-auto">
              {visibleFiles.length ? <Table>
                <TableHeader><TableRow><TableHead className="h-11 text-[11px] font-normal text-muted-foreground">{t("Document")}</TableHead><TableHead className="h-11 text-[11px] font-normal text-muted-foreground">{t("Status")}</TableHead><TableHead className="w-10"><span className="sr-only">{t("Actions")}</span></TableHead></TableRow></TableHeader>
                <TableBody>{visibleFiles.map((file) => (
                  <TableRow key={file.file_id} className={selectedId === file.file_id ? "bg-selection/60 hover:bg-selection" : ""}>
                    <TableCell className="max-w-0 py-3 pl-3 pr-1">
                      <Button variant="ghost" className="h-auto w-full justify-start gap-3 px-1 py-1 text-left" aria-current={selectedId === file.file_id ? "true" : undefined} onClick={() => setSelectedId(file.file_id)}>
                        <span className="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-card text-primary"><FileText className="size-4" strokeWidth={1.5} /></span>
                        <span className="min-w-0"><span className="block truncate text-[13px] font-medium" title={file.original_file_name}>{file.original_file_name}</span><span className="mt-1 block text-[10px] text-muted-foreground">{file.original_file_name.split(".").pop()?.toUpperCase()} <span className="mx-1">·</span> {formatSize(file.file_size)}</span></span>
                      </Button>
                    </TableCell>
                    <TableCell className="w-24 px-2"><StatusBadge file={fileStatus(file)} /></TableCell>
                    <TableCell className="px-2"><DropdownMenu>
                      <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" />} aria-label={t("Open file actions")} title={file.original_file_name}><MoreHorizontal /></DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem disabled={isBusy(file) || !canParse(file)} onClick={() => runOperation(file, "parsing")}><FileText />{t("Parse file")}</DropdownMenuItem>
                        <DropdownMenuItem disabled={isBusy(file) || file.status !== "parsed"} onClick={() => runOperation(file, "indexing")}><Search />{t("Build index")}</DropdownMenuItem>
                        <DropdownMenuItem disabled={isBusy(file) || !canExtract(file)} onClick={() => runOperation(file, "extracting")}><Sparkles />{t("Extract graph")}</DropdownMenuItem>
                        <DropdownMenuItem variant="destructive" disabled={isBusy(file)} onClick={() => setConfirmDelete(file)}><Trash2 />{t("Delete file")}</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu></TableCell>
                  </TableRow>
                ))}</TableBody>
              </Table> : <Empty className="min-h-60"><EmptyMedia><Search /></EmptyMedia><EmptyTitle>{t("No matching documents")}</EmptyTitle><Button variant="ghost" onClick={() => setQuery("")}>{t("Clear search")}</Button></Empty>}
            </div>
            <footer className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3 text-[11px] text-muted-foreground"><span>{t("{{count}} documents", { count: files.length })} · {formatSize(files.reduce((sum, file) => sum + file.file_size, 0))}</span><span className="flex items-center gap-1"><Check className="size-3" />{t("{{count}} indexed", { count: indexedCount })}</span></footer>
          </section>
          <section className="flex min-h-80 min-w-0 flex-col border-t border-border bg-background/50 lg:min-h-0 lg:border-l lg:border-t-0" aria-label={t("Document preview")}>
            {selectedFile ? <>
              <header className="shrink-0 border-b border-border px-5 py-4">
                <div className="mb-3 flex items-center gap-2 text-[10px] font-medium tracking-[0.12em] text-muted-foreground uppercase"><FileText className="size-3.5" />{t("Document preview")}</div>
                <h3 className="truncate text-sm font-medium" title={selectedFile.original_file_name}>{selectedFile.original_file_name}</h3>
                <div className="mt-3 flex flex-wrap items-center gap-2"><StatusBadge file={fileStatus(selectedFile)} />
                  {canParse(selectedFile) && <Button variant="outline" size="sm" disabled={isBusy(selectedFile)} onClick={() => runOperation(selectedFile, "parsing")}>{t("Parse file")}<ArrowUpRight /></Button>}
                  {selectedFile.status === "parsed" && <Button variant="outline" size="sm" disabled={isBusy(selectedFile)} onClick={() => runOperation(selectedFile, "indexing")}>{t("Build index")}<ArrowUpRight /></Button>}
                  {selectedFile.status === "indexed" && <Button variant="outline" size="sm" disabled={isBusy(selectedFile)} onClick={() => runOperation(selectedFile, "extracting")}><Sparkles />{t("Extract graph")}</Button>}
                </div>
                {selectedFile.error_message && <p className="mt-3 text-xs leading-5 text-destructive" role="alert">{selectedFile.error_message}</p>}
              </header>
              <div className="flex min-h-0 flex-1 flex-col overflow-auto">
                {selectedFile.markdown_object_name ? <><FileContentViewer path="document.md" content={markdown} loading={previewLoading} error={previewError} />{previewError && <Button variant="outline" className="mx-auto mb-5" onClick={() => setPreviewReload((value) => value + 1)}>{t("Retry")}</Button>}</> : <Empty className="min-h-60 flex-1"><EmptyMedia><FileText className="size-7" strokeWidth={1.3} /></EmptyMedia><EmptyTitle className="text-sm font-medium">{t("No parsed content")}</EmptyTitle><EmptyDescription className="text-xs">{t("Parse this document to read its content here.")}</EmptyDescription></Empty>}
              </div>
            </> : <Empty className="flex-1"><EmptyMedia><FileText /></EmptyMedia><EmptyTitle>{t("Select a document to preview")}</EmptyTitle></Empty>}
          </section>
        </div>
      )}
      <Dialog open={confirmDelete !== null} onOpenChange={(open) => { if (!open && !deleting) setConfirmDelete(null) }}><DialogContent><DialogHeader><DialogTitle>{t("Delete this file?")}</DialogTitle><DialogDescription>{t("{{name}} will be permanently deleted.", { name: confirmDelete?.original_file_name })}</DialogDescription></DialogHeader><DialogFooter><Button variant="ghost" disabled={deleting} onClick={() => setConfirmDelete(null)}>{t("Cancel")}</Button><Button variant="destructive" disabled={deleting} onClick={handleDelete}>{deleting && <Spinner />}{t("Delete file")}</Button></DialogFooter></DialogContent></Dialog>
    </div>
  )
}

function StatusBadge({ file }: { file: KnowledgeFile }) {
  const { t } = useTranslation()
  const variant = file.status === "failed" ? "destructive" : ["extracted", "indexed"].includes(file.status) ? "success" : "default"
  const label = file.status === "extracting" ? t("Extracting…") : file.status === "indexing" ? t("Indexing…") : file.status === "parsing" ? t("Parsing…") : t(file.status.charAt(0).toUpperCase() + file.status.slice(1))
  const badge = <Badge variant={variant} className="h-5 rounded-md px-1.5 text-[10px] font-normal">{PROCESSING.includes(file.status) && <Spinner className="size-3" />}{label}</Badge>
  if (file.status === "failed" && file.error_message) return <Tooltip><TooltipTrigger render={badge} /><TooltipContent className="max-w-80">{file.error_message}</TooltipContent></Tooltip>
  return badge
}
