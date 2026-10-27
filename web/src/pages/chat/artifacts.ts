import type { ChatMessage } from "@/pages/chat/types"

export const PRESENT_ARTIFACTS_TOOL = "present_artifacts"

export type ArtifactStatus = "generating" | "generated" | "failed"

export interface PresentedArtifact {
  path: string
  name: string
  status: ArtifactStatus
  error?: string
}

const record = (value: unknown): Record<string, unknown> =>
  typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {}

const IMAGE_EXTENSIONS = new Set(["avif", "bmp", "gif", "jpeg", "jpg", "png", "svg", "webp"])
const MARKDOWN_EXTENSIONS = new Set(["md", "markdown", "mdx"])

export function normalizeArtifacts(paths: unknown[]): string[] {
  const seen = new Set<string>()
  const normalized: string[] = []
  for (const value of paths) {
    if (typeof value !== "string") continue
    const path = value.trim()
    if (!path || seen.has(path)) continue
    seen.add(path)
    normalized.push(path)
  }
  return normalized
}

export function artifactName(path: string): string {
  return path.split("/").pop() || path
}

export function artifactExtension(path: string): string | null {
  const name = artifactName(path)
  const dot = name.lastIndexOf(".")
  if (dot <= 0 || dot === name.length - 1) return null
  return name.slice(dot + 1).toLowerCase()
}

export function isImageArtifact(path: string): boolean {
  const extension = artifactExtension(path)
  return extension !== null && IMAGE_EXTENSIONS.has(extension)
}

export function isMarkdownArtifact(path: string): boolean {
  const extension = artifactExtension(path)
  return extension !== null && MARKDOWN_EXTENSIONS.has(extension)
}

/** 与 Yuxi 一致：展示交付文件类型，没有扩展名时退回“交付文件”。 */
export function artifactMetaLabel(path: string): string {
  const extension = artifactExtension(path)
  return extension ? `交付文件 · ${extension.toUpperCase()}` : "交付文件"
}

export function formatArtifactSize(size: number | null | undefined): string | null {
  if (typeof size !== "number" || !Number.isFinite(size) || size < 0) return null
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

/** present_artifacts 的 args 可能来自流式字符串或对象，统一取出 filepaths。 */
export function parseArtifactArguments(args: unknown): string[] {
  let value = args
  for (let pass = 0; pass < 2 && typeof value === "string"; pass += 1) {
    try {
      value = JSON.parse(value) as unknown
    } catch {
      return []
    }
  }
  const argsRecord = record(value)
  return Array.isArray(argsRecord.filepaths) ? normalizeArtifacts(argsRecord.filepaths) : []
}

export function artifactStatus(status: unknown): ArtifactStatus {
  if (status === "completed") return "generated"
  if (status === "error") return "failed"
  if (status === "cancelled" || status === "interrupted" || status === "stopped") return "failed"
  return "generating"
}

export function artifactErrorMessage(event: Record<string, unknown>): string {
  const candidates = [event.error, record(event.output).error, record(event.output).content, event.output]
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) return candidate.trim()
    const content = record(candidate).content
    if (typeof content === "string" && content.trim()) return content.trim()
  }
  return "交付物登记失败"
}

/** 从运行分组中提取 present_artifacts 调用；同一路径以最后一次状态为准。 */
export function extractArtifactsFromMessages(
  messages: ChatMessage[],
  threadId?: string | null,
): PresentedArtifact[] {
  const byPath = new Map<string, PresentedArtifact>()
  for (const message of messages) {
    if (message.type !== "ai" || message.payload.type !== "tool") continue
    const event = record(message.payload.event)
    if (event.type !== "tool_call" || event.name !== PRESENT_ARTIFACTS_TOOL) continue
    const eventThread = typeof event.thread_id === "string" ? event.thread_id : null
    if (threadId && eventThread && eventThread !== threadId) continue

    const paths = parseArtifactArguments(event.args)
    if (!paths.length) continue
    const status = artifactStatus(event.status)
    const error = status === "failed" ? artifactErrorMessage(event) : undefined
    for (const path of paths) {
      byPath.set(path, { path, name: artifactName(path), status, ...(error ? { error } : {}) })
    }
  }
  return [...byPath.values()]
}

/** 与 Yuxi 一致：最新的交付物排在最前。 */
export function buildArtifactItems(artifacts: PresentedArtifact[]): PresentedArtifact[] {
  const seen = new Set<string>()
  const items: PresentedArtifact[] = []
  for (let index = artifacts.length - 1; index >= 0; index -= 1) {
    const artifact = artifacts[index]
    if (seen.has(artifact.path)) continue
    seen.add(artifact.path)
    items.push(artifact)
  }
  return items
}

/** 折叠时只展示前三项，展开时展示全部。 */
export function visibleArtifactItems<T>(items: T[], expanded: boolean): T[] {
  return expanded ? items : items.slice(0, 3)
}
