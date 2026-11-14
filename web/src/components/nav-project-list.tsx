import { useState } from "react"
import { ChevronRightIcon, FolderIcon, MoreHorizontalIcon, PencilIcon, PinIcon, PinOffIcon, PlusIcon, Trash2Icon } from "lucide-react"

import { createProject, deleteProject, updateProject, type ProjectResponse } from "@/api/project"
import { NavProjects } from "@/components/nav-projects"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuAction, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import { useTranslation } from "@/i18n"

export function NavProjectList({ projects, revision, onChanged, expandedProject, onExpand, loading, error, onRetry }: {
  projects: ProjectResponse[]
  revision: number
  onChanged: () => void
  expandedProject: string | null
  onExpand: (projectId: string | null) => void
  loading: boolean
  error: string
  onRetry: () => void
}) {
  const { t } = useTranslation()
  const [dialog, setDialog] = useState<{ action: "create" | "rename" | "delete"; project?: ProjectResponse } | null>(null)
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState("")

  function open(action: "create" | "rename" | "delete", project?: ProjectResponse) {
    setName(project?.name ?? "")
    setActionError("")
    setDialog({ action, project })
  }

  async function submit() {
    if (!dialog || saving) return
    setSaving(true)
    setActionError("")
    try {
      if (dialog.action === "create") {
        const created = await createProject(name.trim())
        onExpand(created.project_id)
      } else if (dialog.project) {
        if (dialog.action === "rename") await updateProject(dialog.project.project_id, { name: name.trim() })
        else {
          await deleteProject(dialog.project.project_id)
          if (expandedProject === dialog.project.project_id) onExpand(null)
        }
      }
      setDialog(null)
      onChanged()
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : t("Operation failed. Please try again."))
    } finally {
      setSaving(false)
    }
  }

  async function pin(project: ProjectResponse) {
    setSaving(true)
    setActionError("")
    try {
      await updateProject(project.project_id, { pinned: !project.pinned })
      onChanged()
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : t("Operation failed. Please try again."))
    } finally {
      setSaving(false)
    }
  }

  return <>
    <SidebarGroup className="shrink-0 pt-1 group-data-[collapsible=icon]:hidden" aria-label={t("Projects")}>
      <SidebarGroupLabel className="justify-between">
        <span>{t("Projects")}</span>
        <Button variant="ghost" size="icon-sm" aria-label={t("New project")} onClick={() => open("create")}><PlusIcon /></Button>
      </SidebarGroupLabel>
      <SidebarMenu>
        {loading && <SidebarMenuItem><p role="status" className="px-2 text-xs text-muted-foreground">{t("Loading…")}</p></SidebarMenuItem>}
        {error && <SidebarMenuItem><p role="alert" className="px-2 text-xs text-destructive">{error}</p><Button variant="ghost" size="sm" onClick={onRetry}>{t("Retry")}</Button></SidebarMenuItem>}
        {!dialog && actionError && <SidebarMenuItem><p role="alert" className="px-2 text-xs text-destructive">{actionError}</p></SidebarMenuItem>}
        {!loading && !error && !projects.length && <SidebarMenuItem><p className="px-2 text-xs text-muted-foreground">{t("No projects")}</p></SidebarMenuItem>}
        {projects.map((project) => <SidebarMenuItem key={project.project_id}>
          <SidebarMenuButton id={`project-${project.project_id}`} aria-expanded={expandedProject === project.project_id} aria-controls={`project-threads-${project.project_id}`} onClick={() => onExpand(expandedProject === project.project_id ? null : project.project_id)} title={project.name} className="text-[13px]">
            <ChevronRightIcon className={expandedProject === project.project_id ? "rotate-90" : ""} /><FolderIcon /><span>{project.name}</span>
          </SidebarMenuButton>
          <DropdownMenu>
            <DropdownMenuTrigger render={<SidebarMenuAction showOnHover />} aria-label={t("Project actions: {{name}}", { name: project.name })}><MoreHorizontalIcon /></DropdownMenuTrigger>
            <DropdownMenuContent side="right" align="start">
              <DropdownMenuItem onClick={() => open("rename", project)}><PencilIcon />{t("Rename")}</DropdownMenuItem>
              <DropdownMenuItem disabled={saving} onClick={() => void pin(project)}>{project.pinned ? <PinOffIcon /> : <PinIcon />}{t(project.pinned ? "Unpin" : "Pin")}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => open("delete", project)}><Trash2Icon />{t("Delete project")}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {expandedProject === project.project_id && <div id={`project-threads-${project.project_id}`} className="ml-3">
            <NavProjects projectId={project.project_id} projects={projects} revision={revision} onChanged={onChanged} />
          </div>}
        </SidebarMenuItem>)}
      </SidebarMenu>
    </SidebarGroup>
    <Dialog open={dialog !== null} onOpenChange={(isOpen) => { if (!isOpen && !saving) setDialog(null) }}>
      <DialogContent showCloseButton={!saving}>
        <DialogHeader>
          <DialogTitle>{t(dialog?.action === "delete" ? "Delete project" : dialog?.action === "rename" ? "Rename project" : "New project")}</DialogTitle>
          <DialogDescription className={dialog?.action === "delete" ? "" : "sr-only"}>
            {dialog?.action === "delete" ? t("Delete {{name}}? Its conversations will remain in your history.", { name: dialog.project?.name }) : t("Project name")}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={(event) => { event.preventDefault(); void submit() }}>
          {dialog?.action !== "delete" && <Input autoFocus maxLength={255} aria-label={t("Project name")} value={name} disabled={saving} onChange={(event) => setName(event.target.value)} />}
          {actionError && <p role="alert" className="mt-2 text-sm text-destructive">{actionError}</p>}
          <DialogFooter className="mt-4">
            <Button type="button" variant="ghost" disabled={saving} onClick={() => setDialog(null)}>{t("Cancel")}</Button>
            <Button type="submit" variant={dialog?.action === "delete" ? "destructive" : "default"} disabled={saving || (dialog?.action !== "delete" && !name.trim())}>
              {t(saving ? "Processing..." : dialog?.action === "delete" ? "Delete" : "Save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </>
}
