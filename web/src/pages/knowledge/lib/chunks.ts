import type { KnowledgeChunkHit } from "@/api/knowledge"

export interface ChunkFileGroup {
  key: string
  fileId: string
  fileName: string
  chunks: KnowledgeChunkHit[]
}

export function groupChunksByFile(hits: KnowledgeChunkHit[]): ChunkFileGroup[] {
  const groups = new Map<string, ChunkFileGroup>()
  for (const hit of hits) {
    const key = `${hit.file_id}\u0000${hit.file_name}`
    const group = groups.get(key)
    if (group) {
      group.chunks.push(hit)
    } else {
      groups.set(key, {
        key,
        fileId: hit.file_id,
        fileName: hit.file_name || hit.file_id || "Unknown file",
        chunks: [hit]
      })
    }
  }
  return Array.from(groups.values()).sort((a, b) =>
    a.fileName.localeCompare(b.fileName)
  )
}
