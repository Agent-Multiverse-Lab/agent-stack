import folderIcon from "@/assets/folder.svg";
import { Label } from "@/components/ui/label"
import { useEffect, useState } from "react"
import { FolderPlus, Pencil, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { deleteKnowledgeFolder, listKnowledgeFolders, saveKnowledgeFolder } from "@/api/knowledge"
import type { KnowledgeFolder } from "@/api/knowledge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export const ALL_KNOWLEDGE_FILES = "__all"

export function FolderSelect({ folders, value, onChange, label = "目标文件夹" }: { folders: KnowledgeFolder[]; value: string | null; onChange: (value: string | null) => void; label?: string }) {
  return <Select value={value ?? "__root"} onValueChange={v => onChange(v === "__root" ? null : String(v))}>
    <SelectTrigger aria-label={label} className="w-full"><SelectValue>{value ? folders.find(item => item.folder_id === value)?.name ?? "文件夹" : "根目录"}</SelectValue></SelectTrigger>
    <SelectContent><SelectItem value="__root">根目录</SelectItem>{folders.map(folder => <SelectItem key={folder.folder_id} value={folder.folder_id}>{folder.name}</SelectItem>)}</SelectContent>
  </Select>
}

export function KnowledgeFolderSidebar({ kbId, selected, onSelect, onLoaded, version }: { kbId: string; selected: string | null; onSelect: (id: string | null) => void; onLoaded: (folders: KnowledgeFolder[]) => void; version: number }) {
  const [folders, setFolders] = useState<KnowledgeFolder[]>([])
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)
  const [form, setForm] = useState<{ id?: string; name: string; parent: string | null } | null>(null)
  const [deleting, setDeleting] = useState<KnowledgeFolder | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    listKnowledgeFolders(kbId).then(items => { if (active) { setFolders(items); onLoaded(items); setError("") } }).catch((e: unknown) => { if (active) setError(e instanceof Error ? e.message : "目录读取失败") })
    return () => { active = false }
  }, [kbId, reload, version, onLoaded])
  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!form || busy) return
    setBusy(true)
    try {
      const folder = await saveKnowledgeFolder(kbId, { name: form.name, parent_id: form.parent }, form.id)
      setForm(null); setReload(v => v + 1); onSelect(folder.folder_id)
    } catch (e) { toast.error(e instanceof Error ? e.message : "保存失败") }
    finally { setBusy(false) }
  }
  async function remove() {
    if (!deleting || busy) return
    setBusy(true)
    try { await deleteKnowledgeFolder(kbId, deleting.folder_id); onSelect(deleting.parent_id); setDeleting(null); setReload(v => v + 1) }
    catch (e) { toast.error(e instanceof Error ? e.message : "删除失败") }
    finally { setBusy(false) }
  }
  function tree(parent: string | null, depth = 0): React.ReactNode {
    return folders.filter(folder => folder.parent_id === parent).map(folder => <div key={folder.folder_id}>
      <Button variant={selected === folder.folder_id ? "secondary" : "ghost"} className="h-8 w-full justify-start truncate text-xs" style={{ paddingLeft: 10 + depth * 12 }} onClick={() => onSelect(folder.folder_id)} title={folder.name}><img src={folderIcon} alt="" className="size-3.5 shrink-0" /><span className="truncate">{folder.name}</span></Button>
      {tree(folder.folder_id, depth + 1)}
    </div>)
  }
  const current = folders.find(folder => folder.folder_id === selected)
  return <aside className="flex w-42 shrink-0 flex-col gap-2 border-r border-border p-2" aria-label="知识库目录">
    <div className="flex items-center justify-between px-2"><h3 className="text-xs font-medium text-muted-foreground">文件夹</h3><Button size="icon-xs" variant="ghost" aria-label="新建文件夹" onClick={() => setForm({ name: "", parent: current?.folder_id ?? null })}><FolderPlus /></Button></div>
    <nav className="min-h-0 flex-1 overflow-auto"><Button variant={selected === ALL_KNOWLEDGE_FILES ? "secondary" : "ghost"} className="h-8 w-full justify-start text-xs" onClick={() => onSelect(ALL_KNOWLEDGE_FILES)}>全部文件</Button><Button variant={selected === null ? "secondary" : "ghost"} className="h-8 w-full justify-start text-xs" onClick={() => onSelect(null)}>根目录</Button>{tree(null)}</nav>
    {error && <div role="alert" className="text-xs text-destructive">{error}<Button variant="ghost" size="sm" onClick={() => setReload(v => v + 1)}>重新读取</Button></div>}
    {current && <div className="flex gap-1"><Button variant="ghost" size="sm" aria-label="编辑文件夹" onClick={() => setForm({ id: current.folder_id, name: current.name, parent: current.parent_id })}><Pencil />编辑</Button><Button variant="ghost" size="icon-sm" aria-label="删除文件夹" onClick={() => setDeleting(current)}><Trash2 /></Button></div>}
    <Dialog open={!!form} onOpenChange={open => { if (!open && !busy) setForm(null) }}><DialogContent><DialogHeader><DialogTitle>{form?.id ? "编辑文件夹" : "新建文件夹"}</DialogTitle></DialogHeader>{form && <form onSubmit={save} className="grid gap-4"><Label className="grid gap-2 text-sm">名称<Input required autoFocus maxLength={255} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></Label><Label className="grid gap-2 text-sm">上级目录<FolderSelect folders={folders.filter(item => item.folder_id !== form.id)} value={form.parent} onChange={parent => setForm({ ...form, parent })} /></Label><DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={() => setForm(null)}>取消</Button><Button disabled={busy || !form.name.trim()}>保存</Button></DialogFooter></form>}</DialogContent></Dialog>
    <Dialog open={!!deleting} onOpenChange={open => { if (!open && !busy) setDeleting(null) }}><DialogContent><DialogHeader><DialogTitle>删除文件夹“{deleting?.name}”？</DialogTitle></DialogHeader><p className="text-sm text-muted-foreground">只能删除空文件夹。</p><DialogFooter><Button variant="outline" onClick={() => setDeleting(null)}>取消</Button><Button variant="destructive" disabled={busy} onClick={remove}>删除</Button></DialogFooter></DialogContent></Dialog>
  </aside>
}
