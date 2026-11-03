import { Label } from "@/components/ui/label"
import { useState } from "react"
import { startKnowledgeEvaluation } from "@/api/knowledge"
import type { KnowledgeEvaluationInput } from "@/api/knowledge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { KnowledgeTasksPanel } from "./KnowledgeTasksPanel"

export function KnowledgeEvaluationPanel({ kbId }: { kbId: string }) {
  const [dataset, setDataset] = useState<KnowledgeEvaluationInput | null>(null)
  const [text, setText] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)
  async function start(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    setError(""); setBusy(true)
    try {
      const payload: KnowledgeEvaluationInput = text.trim() ? JSON.parse(text) : dataset
      if (!payload) throw new Error("请上传或粘贴评估集")
      await startKnowledgeEvaluation(kbId, payload)
      setVersion(v => v + 1)
    } catch (e) { setError(e instanceof Error ? e.message : "评估提交失败") }
    finally { setBusy(false) }
  }
  return <div className="flex h-full min-h-0 flex-col overflow-auto">
    <form className="grid gap-4 border-b border-border p-(--page-padding)" onSubmit={start}>
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">检索评估</h2><Button type="submit" disabled={busy || (!dataset && !text.trim())}>{busy ? "正在提交…" : "运行评估"}</Button></div>
      <p className="text-sm text-muted-foreground">导入带问题与相关 Chunk ID 的评估集，使用当前知识库检索配置计算质量指标。</p>
      <Label className="grid gap-2 text-sm">评估集 JSON<Input type="file" accept=".json,application/json" onChange={async e => {
        const file = e.target.files?.[0]
        if (!file) return
        setDataset(null); setError("")
        try { const parsed = JSON.parse(await file.text()) as KnowledgeEvaluationInput; setDataset(parsed); setText("") }
        catch (caught) { setError(caught instanceof Error ? caught.message : "文件不是有效 JSON") }
      }} /></Label>
      {dataset && <p className="text-xs text-muted-foreground">{dataset.dataset_id} · {dataset.samples?.length ?? 0} 个问题</p>}
      <Textarea aria-label="粘贴评估集 JSON" value={text} rows={5} onChange={e => setText(e.target.value)} placeholder={'{"dataset_id":"资料检索", "dataset_version":"1", "corpus_version":"1", "ks":[3,5,8], "samples":[{"query_id":"q1", "query":"问题", "split":"validation", "relevant_chunk_ids":["文件ID:0"]}]}'} />
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </form>
    <KnowledgeTasksPanel kbId={kbId} evaluationsOnly version={version} />
  </div>
}
