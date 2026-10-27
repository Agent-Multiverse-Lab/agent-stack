import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  AlertCircle,
  ChevronDown,
  Download,
  FileCode2,
  FileImage,
  FileText,
  LoaderCircle,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  downloadSandboxFile,
  listSandboxWorkspace,
  readSandboxFile,
  type SandboxWorkspaceResponse,
} from "@/api/sandbox"
import { cn } from "@/lib/utils"
import {
  artifactMetaLabel,
  buildArtifactItems,
  formatArtifactSize,
  isImageArtifact,
  isMarkdownArtifact,
  visibleArtifactItems,
  type ArtifactStatus,
  type PresentedArtifact,
} from "@/pages/chat/artifacts"

const directoryListings = new Map<
  string,
  Promise<SandboxWorkspaceResponse | null>
>()

function listDirectory(threadId: string, path: string) {
  const key = `${threadId}\u0000${path}`
  const cached = directoryListings.get(key)
  if (cached) return cached
  const request = listSandboxWorkspace(threadId, path).catch(() => null)
  directoryListings.set(key, request)
  return request
}

function parentDirectory(path: string): string {
  const index = path.lastIndexOf("/")
  return index <= 0 ? "/workspace" : path.slice(0, index)
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  const message = typeof error === "string" ? error.trim() : ""
  return message || fallback
}

function ArtifactIcon({ path }: { path: string }) {
  const extension = path.split(".").pop()?.toLowerCase() ?? ""
  const Icon =
    isImageArtifact(path)
      ? FileImage
      : ["ts", "tsx", "js", "jsx", "py", "json", "sh", "sql", "css", "html"].includes(extension)
        ? FileCode2
        : FileText
  return <Icon className="size-4.5 shrink-0 text-muted-foreground" aria-hidden="true" />
}

function StatusBadge({ status }: { status: ArtifactStatus }) {
  if (status === "generating") {
    return (
      <Badge variant="default" className="gap-1">
        <LoaderCircle className="size-3 motion-safe:animate-spin" aria-hidden="true" />
        生成中
      </Badge>
    )
  }
  if (status === "failed") {
    return <Badge variant="destructive">失败</Badge>
  }
  return <Badge variant="success">已生成</Badge>
}

type PreviewState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "text"; content: string; truncated: boolean }
  | { kind: "image"; url: string }
  | { kind: "error"; message: string }

export function ArtifactCard({
  artifact,
  threadId,
}: {
  artifact: PresentedArtifact
  threadId?: string
}) {
  const [size, setSize] = useState<number | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [preview, setPreview] = useState<PreviewState>({ kind: "idle" })
  const [actionError, setActionError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const objectUrl = useRef<string | null>(null)
  const canAct = artifact.status === "generated" && Boolean(threadId)

  useEffect(() => {
    if (!threadId) return
    let cancelled = false
    void listDirectory(threadId, parentDirectory(artifact.path)).then((response) => {
      if (cancelled || !response) return
      const entry = response.entries.find((item) => item.path === artifact.path)
      if (entry && typeof entry.size === "number") setSize(entry.size)
    })
    return () => {
      cancelled = true
    }
  }, [artifact.path, threadId])

  useEffect(() => {
    if (!previewOpen || !canAct || !threadId) return
    let cancelled = false
    setPreview({ kind: "loading" })
    if (isImageArtifact(artifact.path)) {
      void downloadSandboxFile(threadId, artifact.path)
        .then((blob) => {
          if (cancelled) return
          if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
          const url = URL.createObjectURL(blob)
          objectUrl.current = url
          setPreview({ kind: "image", url })
        })
        .catch((error: unknown) => {
          if (!cancelled) setPreview({ kind: "error", message: errorMessage(error, "预览失败") })
        })
    } else {
      void readSandboxFile(threadId, artifact.path)
        .then((response) => {
          if (!cancelled) {
            setPreview({ kind: "text", content: response.content, truncated: response.truncated })
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) setPreview({ kind: "error", message: errorMessage(error, "预览失败，请下载查看") })
        })
    }
    return () => {
      cancelled = true
    }
  }, [artifact.path, canAct, previewOpen, threadId])

  useEffect(
    () => () => {
      if (objectUrl.current) {
        URL.revokeObjectURL(objectUrl.current)
        objectUrl.current = null
      }
    },
    [],
  )

  const togglePreview = () => {
    if (!canAct) return
    setPreviewOpen((open) => !open)
  }

  const download = async () => {
    if (!canAct || !threadId || downloading) return
    setDownloading(true)
    setActionError(null)
    try {
      const blob = await downloadSandboxFile(threadId, artifact.path)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = artifact.name
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      setActionError(errorMessage(error, "下载失败"))
    } finally {
      setDownloading(false)
    }
  }

  const meta = [artifactMetaLabel(artifact.path), formatArtifactSize(size)]
    .filter((value): value is string => Boolean(value))
    .join(" · ")

  return (
    <div
      className="min-w-0 overflow-hidden rounded-xl border border-border bg-card"
      data-artifact-path={artifact.path}
      data-artifact-status={artifact.status}
    >
      <div className="flex min-w-0 items-center gap-1.5 pr-2">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-accent/50 disabled:cursor-default disabled:hover:bg-transparent"
          title={canAct ? `预览 ${artifact.name}` : artifact.name}
          aria-label={`预览 ${artifact.name}`}
          aria-expanded={previewOpen}
          disabled={!canAct}
          onClick={togglePreview}
        >
          <ArtifactIcon path={artifact.path} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold text-foreground">
              {artifact.name}
            </span>
            <span className="mt-0.5 block truncate text-[11.5px] text-muted-foreground">
              {meta}
            </span>
          </span>
        </button>
        <StatusBadge status={artifact.status} />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7 shrink-0 text-muted-foreground"
          title="下载"
          aria-label={`下载 ${artifact.name}`}
          disabled={!canAct || downloading}
          onClick={() => void download()}
        >
          {downloading ? (
            <LoaderCircle className="size-3.5 motion-safe:animate-spin" aria-hidden="true" />
          ) : (
            <Download className="size-3.5" aria-hidden="true" />
          )}
        </Button>
      </div>

      {artifact.error && (
        <p
          role="alert"
          className="m-0 flex items-start gap-1.5 border-t border-destructive-border bg-destructive-muted/40 px-3 py-2 text-[11.5px] leading-5 text-destructive"
        >
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span className="min-w-0 break-words">{artifact.error}</span>
        </p>
      )}
      {actionError && (
        <p role="alert" className="m-0 border-t border-destructive-border px-3 py-2 text-[11.5px] text-destructive">
          {actionError}
        </p>
      )}

      {previewOpen && canAct && (
        <div className="border-t border-border bg-muted/30 p-2.5" data-artifact-preview={artifact.path}>
          {preview.kind === "loading" && (
            <div className="flex items-center gap-2 py-2 text-[12px] text-muted-foreground" role="status">
              <LoaderCircle className="size-3.5 motion-safe:animate-spin" aria-hidden="true" />
              预览加载中
            </div>
          )}
          {preview.kind === "error" && (
            <p role="alert" className="m-0 py-1 text-[11.5px] leading-5 text-destructive">
              {preview.message}
            </p>
          )}
          {preview.kind === "image" && (
            <img
              src={preview.url}
              alt={artifact.name}
              className="mx-auto max-h-72 max-w-full rounded-md object-contain"
            />
          )}
          {preview.kind === "text" &&
            (isMarkdownArtifact(artifact.path) ? (
              <div className="chat-markdown max-h-72 overflow-auto rounded-md bg-background p-2.5 text-[13px] leading-6">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{preview.content}</ReactMarkdown>
              </div>
            ) : (
              <pre className="m-0 max-h-72 overflow-auto rounded-md bg-background p-2.5 font-mono text-[11.5px] leading-5 whitespace-pre-wrap break-words text-muted-foreground">
                {preview.content}
              </pre>
            ))}
          {preview.kind === "text" && preview.truncated && (
            <p className="mb-0 mt-1.5 text-[11px] text-muted-foreground">
              内容过长，预览已截断，请下载查看完整文件。
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function ArtifactList({
  artifacts,
  threadId,
}: {
  artifacts: PresentedArtifact[]
  threadId?: string
}) {
  const [expanded, setExpanded] = useState(false)
  const items = buildArtifactItems(artifacts)
  if (!items.length) return null
  const visible = visibleArtifactItems(items, expanded)
  const hiddenCount = Math.max(0, items.length - 3)
  return (
    <section aria-label="交付物" className="w-full max-w-2xl min-w-0 self-start">
      <div className="overflow-hidden rounded-[14px] border border-border bg-card text-card-foreground shadow-sm">
        {hiddenCount > 0 && (
          <div className="flex items-center justify-between border-b border-border bg-muted/30 px-3 py-2">
            <span className="text-[13px] font-medium text-foreground">
              交付物
              <span className="ml-1 font-normal text-muted-foreground tabular-nums">{items.length}</span>
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 gap-1 px-1.5 text-[12px] font-normal text-muted-foreground"
              aria-expanded={expanded}
              onClick={() => setExpanded((open) => !open)}
            >
              {expanded ? "收起" : `展开其余 ${hiddenCount} 个`}
              <ChevronDown
                className={cn(
                  "size-3.5 transition-transform motion-reduce:transition-none",
                  expanded && "rotate-180",
                )}
                aria-hidden="true"
              />
            </Button>
          </div>
        )}
        <div className="grid gap-2 p-2">
          {visible.map((artifact) => (
            <ArtifactCard key={artifact.path} artifact={artifact} threadId={threadId} />
          ))}
        </div>
      </div>
    </section>
  )
}
