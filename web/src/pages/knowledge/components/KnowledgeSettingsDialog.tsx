import { Label } from "@/components/ui/label"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { getKnowledgeSettings, saveKnowledgeSettings } from "@/api/knowledge"
import type { KnowledgeConfiguration, KnowledgeSettings } from "@/api/knowledge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"

export function KnowledgeSettingsDialog({ kbId, open, onOpenChange, onSaved }: { kbId: string; open: boolean; onOpenChange: (open: boolean) => void; onSaved: () => void }) {
  const [value, setValue] = useState<KnowledgeConfiguration | null>(null)
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (!open) return
    let active = true
    setValue(null); setError("")
    getKnowledgeSettings(kbId).then(data => { if (active) setValue(data) }).catch((e: unknown) => { if (active) setError(e instanceof Error ? e.message : "配置读取失败") })
    return () => { active = false }
  }, [kbId, open])
  function change<K extends keyof KnowledgeSettings>(key: K, next: KnowledgeSettings[K]) {
    setValue(current => current ? { ...current, settings: { ...current.settings, [key]: next } } : current)
  }
  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!value || saving) return
    setSaving(true); setError("")
    try { await saveKnowledgeSettings(kbId, value); toast.success("知识库配置已保存"); onSaved(); onOpenChange(false) }
    catch (e) { setError(e instanceof Error ? e.message : "保存失败") }
    finally { setSaving(false) }
  }
  return <Dialog open={open} onOpenChange={next => { if (!saving) onOpenChange(next) }}><DialogContent className="max-h-[85vh] overflow-auto sm:max-w-2xl">
    <DialogHeader><DialogTitle>知识库配置</DialogTitle></DialogHeader>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {!value ? !error && <Spinner /> : <form onSubmit={save} className="grid gap-6">
      <section className="grid gap-3"><Label className="grid gap-2 text-sm">名称<Input value={value.name} required maxLength={255} onChange={e => setValue({ ...value, name: e.target.value })} /></Label><Label className="grid gap-2 text-sm">描述<Textarea value={value.description} onChange={e => setValue({ ...value, description: e.target.value })} /></Label></section>
      <section className="grid gap-4"><h3 className="text-sm font-semibold">解析与切块</h3><p className="text-xs text-muted-foreground">按文件类型选择解析器，切块配置在下一次建立索引时生效。</p>
        <div className="grid grid-cols-2 gap-4"><Label className="grid gap-2 text-sm">切块方式<Select value={value.settings.chunker} onValueChange={v => change("chunker", v as "title" | "token")}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="title">按标题</SelectItem><SelectItem value="token">按 Token</SelectItem></SelectContent></Select></Label>
          <Label className="grid gap-2 text-sm">每块 Token 数<Input type="number" min={32} max={8192} required value={value.settings.chunk_token_size} onChange={e => change("chunk_token_size", Number(e.target.value))} /></Label>
          {value.settings.chunker === "title" && <><Label className="grid gap-2 text-sm">标题策略<Select value={value.settings.title_method} onValueChange={v => change("title_method", v as "hierarchy" | "group")}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="hierarchy">按层级</SelectItem><SelectItem value="group">按标题组</SelectItem></SelectContent></Select></Label><Label className="grid gap-2 text-sm">目标层级<Input type="number" min={1} max={6} required value={value.settings.target_level} onChange={e => change("target_level", Number(e.target.value))} /></Label></>}
        </div>
        <Label className="grid gap-2 text-sm">Embedding 模型<Input value={value.embedding_model_spec ?? value.settings.embedding_model_spec ?? ""} disabled={!!value.embedding_model_spec} placeholder="使用平台默认模型" onChange={e => change("embedding_model_spec", e.target.value.trim() || null)} /></Label>
        {value.embedding_model_spec && <p className="text-xs text-muted-foreground">此知识库已绑定索引模型。</p>}
      </section>
      <section className="grid gap-4"><h3 className="text-sm font-semibold">检索配置</h3><div className="grid grid-cols-3 gap-3">
        <Label className="grid gap-2 text-sm">Top K<Input type="number" min={1} max={50} required value={value.settings.top_k} onChange={e => change("top_k", Number(e.target.value))} /></Label>
        <Label className="grid gap-2 text-sm">候选数量<Input type="number" min={1} max={100} required value={value.settings.candidate_limit} onChange={e => change("candidate_limit", Number(e.target.value))} /></Label>
        <Label className="grid gap-2 text-sm">最低相似度<Input type="number" min={-1} max={1} step={0.01} value={value.settings.min_score ?? ""} placeholder="不限" onChange={e => change("min_score", e.target.value === "" ? null : Number(e.target.value))} /></Label>
      </div><Label className="flex items-center gap-2 text-sm"><Checkbox checked={value.settings.rerank} onCheckedChange={v => change("rerank", v === true)} />使用平台重排模型</Label></section>
      <DialogFooter><Button type="button" variant="outline" disabled={saving} onClick={() => onOpenChange(false)}>取消</Button><Button type="submit" disabled={saving}>{saving && <Spinner />}保存配置</Button></DialogFooter>
    </form>}
  </DialogContent></Dialog>
}
