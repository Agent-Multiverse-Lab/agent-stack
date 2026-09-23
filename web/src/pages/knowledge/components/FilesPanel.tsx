import { useEffect, useRef, useState } from "react"
import {
  FileText,
  Files,
  MoreHorizontal,
  Plus,
  Sparkles,
} from "lucide-react"
import { toast } from "sonner"

import {
  deleteKnowledgeFile,
  extractKnowledgeFile,
  getKnowledgeFileMarkdown,
  indexKnowledgeFile,
  listKnowledgeFiles,
  parseKnowledgeFile,
  uploadKnowledgeFile,
} from "@/api/knowledge"
import { FileContentViewer } from "@/components/common/file-content-viewer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { Spinner } from "@/components/ui/spinner"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useTranslation } from "@/i18n"
import type {
  KnowledgeFile,
  KnowledgeFileStatus,
} from "@/types/knowledge"

const supported = new Set([
  "pdf",
  "doc",
  "docx",
  "txt",
  "md",
  "markdown",
  "csv",
  "xls",
  "xlsx",
  "ppt",
  "pptx",
  "png",
  "jpg",
  "jpeg",
  "webp",
])

const PROCESSING: KnowledgeFileStatus[] = ["parsing", "indexing", "extracting"]

export function FilesPanel({ kbId }: { kbId: string }) {
  const { t } = useTranslation()
  const [files, setFiles] = useState<KnowledgeFile[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [uploading, setUploading] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [markdown, setMarkdown] = useState("")
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState("")
  const [confirmDelete, setConfirmDelete] = useState<KnowledgeFile | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let active = true
    refresh()
    async function refresh() {
      setLoading(true)
      setError("")
      try {
        const items = await listKnowledgeFiles(kbId)
        if (active) {
          setFiles(items)
          setSelectedId((current) => current ?? items[0]?.file_id ?? null)
        }
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
  }, [kbId, t])

  const selectedFile = files.find((file) => file.file_id === selectedId) ?? null

  useEffect(() => {
    let active = true
    if (!selectedFile?.markdown_object_name) {
      setMarkdown("")
      setPreviewError("")
      return
    }
    setPreviewLoading(true)
    setPreviewError("")
    getKnowledgeFileMarkdown(kbId, selectedFile.file_id)
      .then((result) => {
        if (active) setMarkdown(result.markdown)
      })
      .catch((caught: unknown) => {
        if (active)
          setPreviewError(
            caught instanceof Error ? caught.message : t("Request failed")
          )
      })
      .finally(() => {
        if (active) setPreviewLoading(false)
      })
    return () => {
      active = false
    }
  }, [kbId, selectedFile?.file_id, selectedFile?.markdown_object_name, t])

  async function refresh() {
    try {
      const items = await listKnowledgeFiles(kbId)
      setFiles(items)
      setSelectedId((current) =>
        current && items.some((file) => file.file_id === current)
          ? current
          : (items[0]?.file_id ?? null)
      )
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : t("Request failed")
      )
    }
  }

  async function handleUpload(selected: File[]) {
    setUploading(true)
    try {
      for (const file of selected) {
        const extension = file.name.split(".").pop()?.toLowerCase() ?? ""
        if (!supported.has(extension)) {
          toast.warning(
            t("{{file}} is not a supported source type.", { file: file.name })
          )
          continue
        }
        try {
          await uploadKnowledgeFile(kbId, file)
        } catch (caught) {
          toast.error(
            caught instanceof Error ? caught.message : t("Request failed")
          )
        }
      }
      await refresh()
    } finally {
      setUploading(false)
    }
  }

  async function runOperation(
    file: KnowledgeFile,
    operation: (kbId: string, fileId: string) => Promise<unknown>,
    successMessage: string
  ) {
    setBusyId(file.file_id)
    try {
      await operation(kbId, file.file_id)
      toast.success(successMessage)
      await refresh()
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : t("Request failed")
      )
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return
    try {
      await deleteKnowledgeFile(kbId, confirmDelete.file_id)
      toast.success(
        t("{{name}} will be permanently deleted.", {
          name: confirmDelete.original_file_name,
        })
      )
      setConfirmDelete(null)
      await refresh()
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : t("Request failed")
      )
    }
  }

  const busy = (file: KnowledgeFile) =>
    uploading || busyId === file.file_id || PROCESSING.includes(file.status)

  return (
    <div className="grid h-full min-h-0 [grid-template-columns:minmax(0,17rem)_minmax(0,1fr)]">
      <section className="grid min-h-0 border-r border-border [grid-template-rows:auto_minmax(0,1fr)]">
        <div className="flex items-center gap-2 border-b border-border p-3">
          <Button
            variant="outline"
            type="button"
            className="h-9 flex-1 justify-start gap-2"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Spinner className="size-4" />
            ) : (
              <Plus size={16} />
            )}
            {t("Upload files")}
          </Button>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp"
            className="hidden"
            onChange={(event) => {
              handleUpload(Array.from(event.target.files ?? []))
              event.target.value = ""
            }}
          />
        </div>
        <div className="min-h-0 overflow-y-auto p-2">
          {loading ? (
            <div className="grid min-h-32 place-items-center text-muted-foreground">
              <Spinner className="size-5" />
            </div>
          ) : error ? (
            <div className="grid min-h-32 place-items-center px-2 text-center text-sm text-muted-foreground">
              {error}
            </div>
          ) : files.length ? (
            <ul className="grid gap-1">
              {files.map((file) => (
                <li
                  key={file.file_id}
                  className={`flex min-h-14 min-w-0 items-center gap-1 rounded-lg border px-2 hover:bg-accent ${
                    selectedId === file.file_id
                      ? "border-border bg-muted"
                      : "border-transparent"
                  }`}
                >
                  <Button
                    variant="ghost"
                    type="button"
                    className="h-auto min-w-0 flex-1 justify-start gap-2 text-left"
                    aria-current={
                      selectedId === file.file_id ? "true" : undefined
                    }
                    onClick={() => setSelectedId(file.file_id)}
                  >
                    <FileText size={16} className="shrink-0" />
                    <span className="min-w-0 truncate" title={file.original_file_name}>
                      {file.original_file_name}
                    </span>
                    <StatusBadge file={file} />
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      aria-label={t("Open file actions")}
                      title={t("Open file actions")}
                      className="grid size-9 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-accent"
                    >
                      <MoreHorizontal size={16} />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        disabled={busy(file)}
                        onClick={() =>
                          runOperation(file, parseKnowledgeFile, t("Parsed"))
                        }
                      >
                        {t("Parse file")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        disabled={busy(file) || file.status !== "parsed"}
                        onClick={() =>
                          runOperation(file, indexKnowledgeFile, t("Indexed"))
                        }
                      >
                        {t("Build index")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        disabled={
                          busy(file) ||
                          !["indexed", "extracted"].includes(file.status)
                        }
                        onClick={async () => {
                          setBusyId(file.file_id)
                          try {
                            const result = await extractKnowledgeFile(
                              kbId,
                              file.file_id
                            )
                            toast.success(
                              t("Extracted: {{entities}} entities, {{relations}} relations", {
                                entities: result.entity_count,
                                relations: result.relation_count,
                              })
                            )
                            await refresh()
                          } catch (caught) {
                            toast.error(
                              caught instanceof Error
                                ? caught.message
                                : t("Request failed")
                            )
                          } finally {
                            setBusyId(null)
                          }
                        }}
                      >
                        <Sparkles />
                        {t("Extract graph")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        disabled={PROCESSING.includes(file.status)}
                        onClick={() => setConfirmDelete(file)}
                      >
                        {t("Delete file")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              ))}
            </ul>
          ) : (
            <div className="grid min-h-32 place-content-center justify-items-center gap-2 text-muted-foreground">
              <Files size={22} />
              {t("No files")}
            </div>
          )}
        </div>
      </section>

      <section className="grid min-h-0 [grid-template-rows:auto_minmax(0,1fr)]">
        {selectedFile ? (
          <>
            <header className="flex h-10 items-center gap-2 border-b border-border px-4">
              <span className="min-w-0 truncate text-sm font-medium">
                {selectedFile.original_file_name}
              </span>
              <StatusBadge file={selectedFile} />
            </header>
            <div className="min-h-0 overflow-hidden">
              {selectedFile.markdown_object_name ? (
                <FileContentViewer
                  path="document.md"
                  content={markdown}
                  loading={previewLoading}
                  error={previewError}
                />
              ) : (
                <div className="grid h-full place-items-center text-sm text-muted-foreground">
                  {t("No parsed content")}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="grid place-items-center text-sm text-muted-foreground">
            {t("No files")}
          </div>
        )}
      </section>

      <Dialog
        open={confirmDelete !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDelete(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("Delete this file?")}</DialogTitle>
            <DialogDescription>
              {t("{{name}} will be permanently deleted.", {
                name: confirmDelete?.original_file_name,
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
              {t("Delete file")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function StatusBadge({ file }: { file: KnowledgeFile }) {
  const { t } = useTranslation()
  const variant =
    file.status === "failed"
      ? "destructive"
      : file.status === "extracted"
        ? "success"
        : file.status === "indexed"
          ? "default"
          : "outline"
  const label =
    file.status === "extracting"
      ? t("Extracting…")
      : file.status === "indexing"
        ? t("Indexing…")
        : file.status === "parsing"
          ? t("Parsing…")
          : t(
              file.status.charAt(0).toUpperCase() + file.status.slice(1)
            )
  const badge = (
    <Badge
      variant={variant as "default"}
      className="shrink-0 whitespace-nowrap"
    >
      {PROCESSING.includes(file.status) && (
        <Spinner className="mr-1 size-3" />
      )}
      {label}
    </Badge>
  )
  if (file.status === "failed" && file.error_message) {
    return (
      <Tooltip>
        <TooltipTrigger render={badge} />
        <TooltipContent className="max-w-80">
          {file.error_message}
        </TooltipContent>
      </Tooltip>
    )
  }
  return badge
}
