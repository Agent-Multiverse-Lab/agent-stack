import { useEffect, useState } from "react"
import { Download, RefreshCw } from "lucide-react"
import { cancelKnowledgeTask, listKnowledgeTasks, saveKnowledgeDownload } from "@/api/knowledge"
import type { KnowledgeTask } from "@/api/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDateTime } from "@/pages/knowledge/lib/format"

const operations = { parse: "解析", index: "建立索引", extract: "图谱抽取", delete: "删除文件", evaluate: "检索评估" }
const statuses = { pending: "等待执行", running: "执行中", completed: "已完成", failed: "失败", cancelled: "已取消" }

export function KnowledgeTasksPanel({ kbId, evaluationsOnly = false, version = 0 }: { kbId: string; evaluationsOnly?: boolean; version?: number }) {
  const [tasks, setTasks] = useState<KnowledgeTask[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      try {
        const items = await listKnowledgeTasks(kbId)
        if (active) {
          setTasks(items); setError("")
          if (items.some(item => ["pending", "running"].includes(item.status))) timer = setTimeout(load, 2000)
        }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "任务读取失败") }
      finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false; clearTimeout(timer) }
  }, [kbId, reload, version])
  async function cancel(task: KnowledgeTask) {
    try { await cancelKnowledgeTask(kbId, task.task_id); setReload(v => v + 1) }
    catch (e) { setError(e instanceof Error ? e.message : "取消失败") }
  }
  const visible = tasks.filter(task => !evaluationsOnly || task.operation === "evaluate")
  const task = tasks.find(item => item.task_id === selected)
  return <div className="flex min-h-0 flex-1 flex-col overflow-auto p-(--page-padding)">
    <div className="mb-4 flex items-center justify-between"><h2 className="text-sm font-semibold">{evaluationsOnly ? "评估记录" : "处理任务"}</h2><Button size="sm" variant="ghost" onClick={() => setReload(v => v + 1)}><RefreshCw />刷新</Button></div>
    {error && <p role="alert" className="mb-4 text-sm text-destructive">{error}</p>}
    <Table><TableHeader><TableRow><TableHead>任务</TableHead><TableHead>状态</TableHead><TableHead>进度</TableHead><TableHead>提交时间</TableHead><TableHead>操作</TableHead></TableRow></TableHeader><TableBody>
      {visible.map(item => <TableRow key={item.task_id}><TableCell><Button variant="ghost" size="sm" onClick={() => setSelected(item.task_id)}>{operations[item.operation]}</Button></TableCell><TableCell><Badge variant={item.status === "failed" ? "destructive" : item.status === "completed" ? "success" : "secondary"}>{statuses[item.status]}</Badge></TableCell><TableCell className="tabular-nums">{item.completed} / {item.total}</TableCell><TableCell>{formatDateTime(item.created_at)}</TableCell><TableCell>{["pending", "running"].includes(item.status) ? <Button variant="ghost" size="sm" onClick={() => cancel(item)}>取消后续处理</Button> : <Button variant="ghost" size="sm" onClick={() => setSelected(item.task_id)}>查看结果</Button>}</TableCell></TableRow>)}
      {!visible.length && <TableRow><TableCell colSpan={5} className="h-32 text-center text-muted-foreground">{loading ? "正在读取任务…" : "暂无任务"}</TableCell></TableRow>}
    </TableBody></Table>
    {task && <section className="mt-6 grid gap-3"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">{operations[task.operation]}结果</h3><Button variant="outline" size="sm" onClick={() => saveKnowledgeDownload(new Blob([JSON.stringify(task.report ?? task, null, 2)], { type: "application/json" }), `knowledge-${task.task_id}.json`)}><Download />下载报告</Button></div>
      {task.error && <p role="alert" className="text-sm text-destructive">{task.error}</p>}
      {task.report && <><p className="text-sm">建议 Top K：{task.report.selection.recommended_top_k}</p><Table><TableHeader><TableRow>{["数据划分", "K", "问题数", "命中率", "精确率", "召回率", "F1"].map(label => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader><TableBody>{task.report.summary_by_k.map(row => <TableRow key={`${row.split}-${row.k}`}><TableCell>{row.split}</TableCell><TableCell>{row.k}</TableCell><TableCell>{row.query_count}</TableCell>{[row.hit_rate, row.precision, row.recall, row.f1].map((value, index) => <TableCell key={index} className="tabular-nums">{(value * 100).toFixed(1)}%</TableCell>)}</TableRow>)}</TableBody></Table><Table><TableHeader><TableRow><TableHead>问题</TableHead><TableHead>命中标注</TableHead><TableHead>返回分块</TableHead></TableRow></TableHeader><TableBody>{task.report.queries.map(query => <TableRow key={query.query_id}><TableCell>{query.query}</TableCell><TableCell>{query.matched_chunk_ids.length} / {query.relevant_chunk_ids.length}</TableCell><TableCell className="max-w-80 break-all text-xs">{query.retrieved_chunk_ids.join(", ")}</TableCell></TableRow>)}</TableBody></Table></>}
      {!task.report && <ul className="grid gap-2 text-sm">{task.results.map((result, index) => <li key={index} className={result.success ? "text-foreground" : "text-destructive"}>{result.file_id ?? result.query}：{result.success ? "成功" : result.error}</li>)}</ul>}
    </section>}
  </div>
}
