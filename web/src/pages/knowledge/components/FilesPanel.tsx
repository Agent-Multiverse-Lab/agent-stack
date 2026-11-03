import { Label } from "@/components/ui/label"
import { useEffect, useRef, useState } from "react"
import { ArrowUpRight, Check, Download, FileText, Filter, FolderUp, MoreHorizontal, Pencil, Rows3, Search, Sparkles, Trash2, Upload, X } from "lucide-react"
import { toast } from "sonner"

import { deleteKnowledgeFile, downloadKnowledgeFile, getKnowledgeFileMarkdown, listKnowledgeFiles, listKnowledgeTasks, saveKnowledgeFolder, startKnowledgeTask, updateKnowledgeFile, uploadKnowledgeFile } from "@/api/knowledge"
import { FileContentViewer } from "@/components/common/file-content-viewer"
import { Checkbox } from "@/components/ui/checkbox"
import { ALL_KNOWLEDGE_FILES, FolderSelect, KnowledgeFolderSidebar } from "./KnowledgeFolderSidebar"
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
import { FileChunksDialog } from "@/pages/knowledge/components/FileChunksDialog"
import { formatDateTime, formatFileSize } from "@/pages/knowledge/lib/format"
import type { KnowledgeFile, KnowledgeFileStatus, KnowledgeFolder, KnowledgeOperation } from "@/api/knowledge"

const supported = new Set(["pdf", "doc", "docx", "txt", "md", "markdown", "csv", "xls", "xlsx", "ppt", "pptx", "png", "jpg", "jpeg", "webp"])
const PROCESSING: KnowledgeFileStatus[] = ["parsing", "indexing", "extracting"]
const canParse = (file: KnowledgeFile) => file.status === "uploaded" || file.status === "failed"
const canExtract = (file: KnowledgeFile) => file.status === "indexed" || file.status === "extracted"


export function FilesPanel({ kbId, initialFileId }: { kbId: string; initialFileId?: string | null }) {
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
  const [chunksFile, setChunksFile] = useState<KnowledgeFile | null>(null)
  const [statusFilter, setStatusFilter] = useState("all")
  const [previewOpen, setPreviewOpen] = useState(false)
  const [folderId, setFolderId] = useState<string | null>(ALL_KNOWLEDGE_FILES)
  const [folders, setFolders] = useState<KnowledgeFolder[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [taskPending, setTaskPending] = useState(false)
  const [editFile, setEditFile] = useState<{ file: KnowledgeFile; name: string; folder: string | null } | null>(null)
  const [bulkDelete, setBulkDelete] = useState(false)
  const [metadataBusy, setMetadataBusy] = useState(false)
  const folderInput = useRef<HTMLInputElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const mutationRef = useRef(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError("")
    Promise.all([listKnowledgeFiles(kbId), listKnowledgeTasks(kbId)])
      .then(([items, tasks]) => {
        if (!active) return
        setFiles(items)
        setTaskPending(tasks.some(task => ["pending", "running"].includes(task.status)))
        setSelectedId((current) => items.some((file) => file.file_id === current) ? current : items[0]?.file_id ?? null)
      })
      .catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : t("Request failed")) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [kbId, t, reload])

  const hasProcessing = taskPending || files.some((file) => PROCESSING.includes(file.status))
  useEffect(() => {
    if (!hasProcessing) return
    let active = true
    let inFlight = false
    const timer = window.setInterval(async () => {
      if (inFlight) return
      inFlight = true
      try {
        const [items, tasks] = await Promise.all([listKnowledgeFiles(kbId), listKnowledgeTasks(kbId)])
        if (active) { setFiles(items); setTaskPending(tasks.some(task => ["pending", "running"].includes(task.status))); setError("") }
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : t("Request failed"))
      } finally { inFlight = false }
    }, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [hasProcessing, kbId, t])

  useEffect(() => {
    if (initialFileId && files.some((file) => file.file_id === initialFileId)) {
      setSelectedId(initialFileId)
      setPreviewOpen(true)
    }
  }, [initialFileId, files])

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
      setSelectedIds(ids => ids.filter(id => items.some(file => file.file_id === id)))
      setError("")
      setSelectedId((current) => items.some((file) => file.file_id === current) ? current : items[0]?.file_id ?? null)
    } catch (caught) { setError(caught instanceof Error ? caught.message : t("Request failed")) }
  }

  async function handleUpload(selected: File[]) {
    if (!selected.length || mutationRef.current) return
    mutationRef.current = true
    setUploading(true)
    try {
      const knownFolders = [...folders]
      for (const file of selected) {
        const extension = file.name.split(".").pop()?.toLowerCase() ?? ""
        if (!supported.has(extension)) { toast.warning(t("{{file}} is not a supported source type.", { file: file.name })); continue }
        try {
          let target = folderId === ALL_KNOWLEDGE_FILES ? null : folderId
          const segments = file.webkitRelativePath.split("/").slice(0, -1)
          for (const name of segments) {
            let folder = knownFolders.find(item => item.name === name && item.parent_id === target)
            if (!folder) { folder = await saveKnowledgeFolder(kbId, { name, parent_id: target }); knownFolders.push(folder) }
            target = folder.folder_id
          }
          await uploadKnowledgeFile(kbId, file, target)
        }
        catch (caught) { toast.error(caught instanceof Error ? caught.message : t("Request failed")) }
      }
      await refresh()
      setReload(value => value + 1)
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
      await startKnowledgeTask(kbId, status === "parsing" ? "parse" : status === "indexing" ? "index" : "extract", [file.file_id])
      setTaskPending(true)
      toast.success("处理任务已提交，可在任务页查看结果")
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

  async function runBatch(operation: KnowledgeOperation) {
    if (!selectedIds.length || metadataBusy) return
    setMetadataBusy(true)
    try {
      await startKnowledgeTask(kbId, operation, selectedIds)
      setTaskPending(true); setSelectedIds([]); setBulkDelete(false)
      toast.success("批处理任务已提交")
    } catch (caught) { toast.error(caught instanceof Error ? caught.message : "任务提交失败") }
    finally { setMetadataBusy(false) }
  }
  async function saveFile(event: React.FormEvent) {
    event.preventDefault()
    if (!editFile || metadataBusy) return
    setMetadataBusy(true)
    try {
      await updateKnowledgeFile(kbId, editFile.file.file_id, { name: editFile.name, folder_id: editFile.folder })
      setEditFile(null); await refresh()
    } catch (caught) { toast.error(caught instanceof Error ? caught.message : "文件更新失败") }
    finally { setMetadataBusy(false) }
  }
  async function download(file: KnowledgeFile) {
    try { await downloadKnowledgeFile(kbId, file) }
    catch (caught) { toast.error(caught instanceof Error ? caught.message : "下载失败") }
  }

  const isBusy = (file: KnowledgeFile) => uploading || busyId !== null || deleting || PROCESSING.includes(file.status)
  const fileStatus = (file: KnowledgeFile) => busyId === file.file_id && busyStatus ? { ...file, status: busyStatus } : file
  const statusMatches = (file: KnowledgeFile) => {
    if (statusFilter === "all") return true
    if (statusFilter === "processing") return PROCESSING.includes(file.status)
    if (statusFilter === "indexed") return ["indexed", "extracted"].includes(file.status)
    return file.status === statusFilter
  }
  const visibleFiles = files.filter((file) => (folderId === ALL_KNOWLEDGE_FILES || (file.folder_id ?? null) === folderId) && file.original_file_name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()) && statusMatches(file))
  const indexedCount = files.filter((file) => ["indexed", "extracting", "extracted"].includes(file.status)).length

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-(--page-padding) py-2.5">
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <span className="font-medium text-foreground">{t("All documents")}</span>
            {!loading && <Badge variant="secondary" className="rounded-md tabular-nums">{files.length}</Badge>}
          </div>
          <span aria-hidden="true" className="text-border">|</span>
          <span>{t("{{count}} indexed", { count: indexedCount })}</span>
          <span aria-hidden="true" className="text-border">|</span>
          <span>{t("Size")}: {formatFileSize(files.reduce((sum, file) => sum + file.file_size, 0))}</span>
        </div>
        <div className="flex items-center gap-2.5">
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant={statusFilter === "all" ? "ghost" : "secondary"} size="icon" />}
              aria-label={t("Filter by status")}
              title={t("Filter by status")}
              aria-pressed={statusFilter !== "all"}
            >
              <Filter />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {[
                ["all", t("All statuses")],
                ["uploaded", t("Uploaded")],
                ["parsed", t("Parsed")],
                ["indexed", t("Indexed")],
                ["processing", t("Processing")],
                ["failed", t("Failed")]
              ].map(([value, label]) => (
                <DropdownMenuItem key={value} onClick={() => setStatusFilter(value)}>
                  {statusFilter === value ? <Check /> : <span className="size-3.5" />}
                  {label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <div role="search" className="relative w-48 xl:w-56">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("Search files")}
              aria-label={t("Search files")}
              className="h-8 pl-9 pr-8"
            />
            {query && (
              <Button
                variant="ghost"
                size="icon-xs"
                className="absolute right-1.5 top-1/2 -translate-y-1/2"
                aria-label={t("Clear search")}
                onClick={() => setQuery("")}
              >
                <X />
              </Button>
            )}
          </div>
          <Button
            className="h-8 gap-1.5"
            onClick={() => fileInput.current?.click()}
            disabled={uploading || busyId !== null || deleting}
          >
            {uploading ? <Spinner /> : <Upload />}
            {t("Upload files")}
          </Button>
          <Button variant="outline" size="sm" disabled={uploading} onClick={() => folderInput.current?.click()}><FolderUp />上传文件夹</Button>
          <Input ref={folderInput} type="file" multiple {...{ webkitdirectory: "" }} className="hidden" aria-label="选择上传文件夹" onChange={event => { void handleUpload(Array.from(event.target.files ?? [])); event.target.value = "" }} />
          <Input
            ref={fileInput}
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp"
            aria-label={t("Choose files to upload")}
            className="hidden"
            onChange={(event) => {
              handleUpload(Array.from(event.target.files ?? []))
              event.target.value = ""
            }}
          />
        </div>
      </div>
      {selectedIds.length > 0 && <div className="flex items-center gap-2 border-b border-border px-(--page-padding) py-2"><span className="mr-2 text-xs">已选择 {selectedIds.length} 个文件</span>{([['parse', '批量解析'], ['index', '批量索引'], ['extract', '批量抽取']] as const).map(([operation, label]) => <Button key={operation} variant="outline" size="sm" disabled={metadataBusy} onClick={() => runBatch(operation)}>{label}</Button>)}<Button variant="destructive" size="sm" disabled={metadataBusy} onClick={() => setBulkDelete(true)}>批量删除</Button><Button variant="ghost" size="sm" onClick={() => setSelectedIds([])}>取消选择</Button></div>}
      <div className="flex min-h-0 flex-1">
      <KnowledgeFolderSidebar kbId={kbId} selected={folderId} onSelect={setFolderId} onLoaded={setFolders} version={reload} />
      {loading ? (
        <div className="grid flex-1 place-items-center text-muted-foreground" role="status" aria-label={t("Loading files")}>
          <Spinner className="size-6" />
        </div>
      ) : error && !files.length ? (
        <Empty className="flex-1">
          <EmptyTitle>{t("Unable to load files")}</EmptyTitle>
          <EmptyDescription role="alert">{error}</EmptyDescription>
          <Button variant="outline" onClick={() => setReload((value) => value + 1)}>{t("Retry")}</Button>
        </Empty>
      ) : (
        <div className={`grid min-h-0 flex-1 overflow-hidden ${previewOpen && selectedFile ? "lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]" : "grid-cols-1"}`}>
          <section className="flex min-h-64 min-w-0 flex-col lg:min-h-0" aria-label={t("Documents")}>
            {error && (
              <div role="alert" className="flex items-center justify-between gap-3 border-b border-border px-4 py-2 text-xs text-destructive">
                <span>{error}</span>
                <Button variant="ghost" size="sm" onClick={refresh}>{t("Retry")}</Button>
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-9 px-2"><Checkbox aria-label="选择当前列表全部文件" checked={visibleFiles.length > 0 && visibleFiles.every(file => selectedIds.includes(file.file_id))} onCheckedChange={value => setSelectedIds(value === true ? visibleFiles.map(file => file.file_id) : [])} /></TableHead>
                    <TableHead className="h-11 px-4 text-[11px] font-normal text-muted-foreground">{t("Document")}</TableHead>
                    <TableHead className="h-11 w-24 px-2 text-[11px] font-normal text-muted-foreground">{t("Size")}</TableHead>
                    <TableHead className="h-11 w-24 px-2 text-[11px] font-normal text-muted-foreground">{t("Status")}</TableHead>
                    <TableHead className="h-11 w-36 px-2 text-[11px] font-normal text-muted-foreground">{t("Updated")}</TableHead>
                    <TableHead className="w-10 px-2"><span className="sr-only">{t("Actions")}</span></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleFiles.length ? (
                    visibleFiles.map((file) => (
                      <TableRow key={file.file_id} className={previewOpen && selectedId === file.file_id ? "bg-selection/60 hover:bg-selection" : ""}>
                        <TableCell className="px-2"><Checkbox aria-label={`选择 ${file.original_file_name}`} checked={selectedIds.includes(file.file_id)} onCheckedChange={value => setSelectedIds(ids => value === true ? [...ids, file.file_id] : ids.filter(id => id !== file.file_id))} /></TableCell>
                        <TableCell className="max-w-0 py-3 pl-4 pr-1">
                          <Button
                            variant="ghost"
                            className="h-auto w-full justify-start gap-3 px-1 py-1 text-left"
                            aria-current={previewOpen && selectedId === file.file_id ? "true" : undefined}
                            onClick={() => {
                              setSelectedId(file.file_id)
                              setPreviewOpen(true)
                            }}
                          >
                            <span className="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-card text-primary">
                              <FileText className="size-4" strokeWidth={1.5} />
                            </span>
                            <span className="min-w-0">
                              <span className="block truncate text-[13px] font-medium" title={file.original_file_name}>
                                {file.original_file_name}
                              </span>
                              <span className="mt-1 block text-[10px] text-muted-foreground">
                                {file.original_file_name.split(".").pop()?.toUpperCase()}
                              </span>
                            </span>
                          </Button>
                        </TableCell>
                        <TableCell className="w-24 px-2 text-[11px] text-muted-foreground tabular-nums">
                          {formatFileSize(file.file_size)}
                        </TableCell>
                        <TableCell className="w-24 px-2">
                          <StatusBadge file={fileStatus(file)} />
                        </TableCell>
                        <TableCell className="w-36 px-2 text-[11px] text-muted-foreground">
                          {formatDateTime(file.updated_at ?? file.created_at)}
                        </TableCell>
                        <TableCell className="px-2">
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={<Button variant="ghost" size="icon-sm" />}
                              aria-label={t("Open file actions")}
                              title={file.original_file_name}
                            >
                              <MoreHorizontal />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => { setSelectedId(file.file_id); setPreviewOpen(true) }}>
                                <FileText />{t("File preview")}
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => download(file)}><Download />下载原文件</DropdownMenuItem>
                              <DropdownMenuItem disabled={isBusy(file)} onClick={() => setEditFile({ file, name: file.original_file_name, folder: file.folder_id ?? null })}><Pencil />重命名或移动</DropdownMenuItem>
                              <DropdownMenuItem disabled={isBusy(file) || !canParse(file)} onClick={() => runOperation(file, "parsing")}>
                                <FileText />{t("Parse file")}
                              </DropdownMenuItem>
                              <DropdownMenuItem disabled={isBusy(file) || file.status !== "parsed"} onClick={() => runOperation(file, "indexing")}>
                                <Search />{t("Build index")}
                              </DropdownMenuItem>
                              <DropdownMenuItem disabled={isBusy(file) || !canExtract(file)} onClick={() => runOperation(file, "extracting")}>
                                <Sparkles />{t("Extract graph")}
                              </DropdownMenuItem>
                              <DropdownMenuItem disabled={!canExtract(file)} onClick={() => setChunksFile(file)}>
                                <Rows3 />{t("View chunks")}
                              </DropdownMenuItem>
                              <DropdownMenuItem variant="destructive" disabled={isBusy(file)} onClick={() => setConfirmDelete(file)}>
                                <Trash2 />{t("Delete file")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : files.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-48 text-center text-xs text-muted-foreground">
                        {t("No documents yet")}
                      </TableCell>
                    </TableRow>
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="h-48 text-center text-xs text-muted-foreground">
                        <div className="flex flex-col items-center justify-center gap-2">
                          <p>{t("No matching documents")}</p>
                          <Button variant="ghost" size="sm" onClick={() => setQuery("")}>{t("Clear search")}</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </section>
          {previewOpen && selectedFile && (
            <section className="flex min-h-80 min-w-0 flex-col border-t border-border bg-background/50 lg:min-h-0 lg:border-l lg:border-t-0" aria-label={t("Document preview")}>
              <header className="shrink-0 border-b border-border px-5 py-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-[10px] font-medium tracking-[0.12em] text-muted-foreground uppercase">
                    <FileText className="size-3.5" />{t("Document preview")}
                  </div>
                  <Button variant="ghost" size="icon-xs" aria-label={t("Close preview")} onClick={() => setPreviewOpen(false)}>
                    <X className="size-3.5" />
                  </Button>
                </div>
                <h3 className="truncate text-sm font-medium" title={selectedFile.original_file_name}>{selectedFile.original_file_name}</h3>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <StatusBadge file={fileStatus(selectedFile)} />
                  {canParse(selectedFile) && (
                    <Button variant="outline" size="sm" disabled={isBusy(selectedFile)} onClick={() => runOperation(selectedFile, "parsing")}>
                      {t("Parse file")}<ArrowUpRight />
                    </Button>
                  )}
                  {selectedFile.status === "parsed" && (
                    <Button variant="outline" size="sm" disabled={isBusy(selectedFile)} onClick={() => runOperation(selectedFile, "indexing")}>
                      {t("Build index")}<ArrowUpRight />
                    </Button>
                  )}
                  {selectedFile.status === "indexed" && (
                    <Button variant="outline" size="sm" disabled={isBusy(selectedFile)} onClick={() => runOperation(selectedFile, "extracting")}>
                      <Sparkles />{t("Extract graph")}
                    </Button>
                  )}
                  {canExtract(selectedFile) && (
                    <Button variant="outline" size="sm" onClick={() => setChunksFile(selectedFile)}>
                      <Rows3 />{t("View chunks")}
                    </Button>
                  )}
                </div>
                {selectedFile.error_message && <p className="mt-3 text-xs leading-5 text-destructive" role="alert">{selectedFile.error_message}</p>}
              </header>
              <div className="flex min-h-0 flex-1 flex-col overflow-auto">
                {selectedFile.markdown_object_name ? (
                  <>
                    <FileContentViewer path="document.md" content={markdown} loading={previewLoading} error={previewError} />
                    {previewError && <Button variant="outline" className="mx-auto mb-5" onClick={() => setPreviewReload((value) => value + 1)}>{t("Retry")}</Button>}
                  </>
                ) : (
                  <Empty className="min-h-60 flex-1">
                    <EmptyMedia><FileText className="size-7" strokeWidth={1.3} /></EmptyMedia>
                    <EmptyTitle className="text-sm font-medium">{t("No parsed content")}</EmptyTitle>
                    <EmptyDescription className="text-xs">{t("Parse this document to read its content here.")}</EmptyDescription>
                  </Empty>
                )}
              </div>
            </section>
          )}
        </div>
      )}
      </div>
      <Dialog open={!!editFile} onOpenChange={open => { if (!open && !metadataBusy) setEditFile(null) }}><DialogContent><DialogHeader><DialogTitle>编辑文件</DialogTitle></DialogHeader>{editFile && <form onSubmit={saveFile} className="grid gap-4"><Label className="grid gap-2 text-sm">文件名<Input required value={editFile.name} onChange={e => setEditFile({ ...editFile, name: e.target.value })} /></Label><Label className="grid gap-2 text-sm">文件夹<FolderSelect folders={folders} value={editFile.folder} onChange={folder => setEditFile({ ...editFile, folder })} /></Label><DialogFooter><Button type="button" variant="outline" onClick={() => setEditFile(null)}>取消</Button><Button disabled={metadataBusy}>保存</Button></DialogFooter></form>}</DialogContent></Dialog>
      <Dialog open={bulkDelete} onOpenChange={setBulkDelete}><DialogContent><DialogHeader><DialogTitle>删除选中的 {selectedIds.length} 个文件？</DialogTitle><DialogDescription>原文件、解析内容和索引会被永久删除。逐文件结果保存在任务记录中。</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setBulkDelete(false)}>取消</Button><Button variant="destructive" disabled={metadataBusy} onClick={() => runBatch("delete")}>删除选中文件</Button></DialogFooter></DialogContent></Dialog>
      <FileChunksDialog
        kbId={kbId}
        fileId={chunksFile?.file_id ?? null}
        fileName={chunksFile?.original_file_name}
        open={chunksFile !== null}
        onOpenChange={(open) => { if (!open) setChunksFile(null) }}
      />
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
