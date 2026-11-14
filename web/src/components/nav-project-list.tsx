import { useId, useState } from "react"
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FolderIcon,
  MoreHorizontalIcon,
  PencilIcon,
  PinIcon,
  PinOffIcon,
  PlusIcon,
  Trash2Icon,
} from "lucide-react"

import { createProject, deleteProject, updateProject, type ProjectResponse } from "@/api/project"
import { NavProjects } from "@/components/nav-projects"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuAction, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import { useTranslation } from "@/i18n"

type ProjectActionMenuProps =
  | {
      project?: undefined
      onCreate: () => void
    }
  | {
      project: ProjectResponse
      saving: boolean
      onRename: () => void
      onTogglePin: () => void
      onDelete: () => void
    }

export function ProjectActionMenu(props: ProjectActionMenuProps) {
  const { t } = useTranslation()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <SidebarMenuAction
            showOnHover
            className="aria-expanded:bg-sidebar-accent aria-expanded:text-sidebar-accent-foreground"
          />
        }
        aria-label={
          props.project
            ? t("Project actions: {{name}}", { name: props.project.name })
            : t("Project actions")
        }
      >
        <MoreHorizontalIcon />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-fit" side="right" align="start">
        {!props.project ? (
          <DropdownMenuItem onClick={props.onCreate}>
            <PlusIcon />
            <span>{t("New project")}</span>
          </DropdownMenuItem>
        ) : (
          <>
            <DropdownMenuItem onClick={props.onRename}>
              <PencilIcon />
              <span>{t("Rename")}</span>
            </DropdownMenuItem>
            <DropdownMenuItem disabled={props.saving} onClick={props.onTogglePin}>
              {props.project.pinned ? <PinOffIcon /> : <PinIcon />}
              <span>{t(props.project.pinned ? "Unpin" : "Pin")}</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={props.onDelete}>
              <Trash2Icon />
              <span>{t("Delete project")}</span>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

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
  const [expanded, setExpanded] = useState(true)
  const listId = useId()
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
        setExpanded(true)
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

  const hasList = loading || Boolean(error) || (!dialog && Boolean(actionError)) || projects.length > 0

  return <>
    <SidebarGroup className="min-h-0 shrink-0 pt-1 group-data-[collapsible=icon]:hidden" aria-label={t("Projects")}>
      <SidebarGroupLabel className="group/menu-item relative mb-1 px-0 font-medium">
        <Button
          type="button"
          variant="ghost"
          aria-expanded={expanded}
          aria-controls={hasList ? listId : undefined}
          onClick={() => setExpanded((value) => !value)}
          className="h-full w-full justify-start gap-1.5 rounded-md px-2 pr-8 text-left text-xs font-medium text-sidebar-foreground/70 group-hover/menu-item:bg-sidebar-accent group-hover/menu-item:text-sidebar-foreground has-[+[aria-expanded=true]]:bg-sidebar-accent has-[+[aria-expanded=true]]:text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <ChevronDownIcon className={`size-4 shrink-0 transition-transform ${expanded ? "" : "-rotate-90"}`} />
          <span>{t("Projects")}</span>
        </Button>
        <ProjectActionMenu onCreate={() => open("create")} />
      </SidebarGroupLabel>
      {hasList && (
        <SidebarMenu id={listId} style={expanded ? undefined : { display: "none" }} className="min-h-0 flex-1 overflow-y-auto gap-1">
          {loading && <SidebarMenuItem><p role="status" className="px-2 py-1 text-xs text-muted-foreground">{t("Loading…")}</p></SidebarMenuItem>}
          {error && <SidebarMenuItem><p role="alert" className="px-2 py-1 text-xs text-destructive">{error}</p><Button variant="ghost" size="sm" onClick={onRetry}>{t("Retry")}</Button></SidebarMenuItem>}
          {!dialog && actionError && <SidebarMenuItem><p role="alert" className="px-2 py-1 text-xs text-destructive">{actionError}</p></SidebarMenuItem>}
          {projects.map((project) => <SidebarMenuItem key={project.project_id}>
            <SidebarMenuButton id={`project-${project.project_id}`} aria-expanded={expandedProject === project.project_id} aria-controls={`project-threads-${project.project_id}`} onClick={() => onExpand(expandedProject === project.project_id ? null : project.project_id)} title={project.name} className="px-2 text-[13px]">
              <ChevronRightIcon className={expandedProject === project.project_id ? "rotate-90" : ""} /><FolderIcon /><span>{project.name}</span>
            </SidebarMenuButton>
            <ProjectActionMenu
              project={project}
              saving={saving}
              onRename={() => open("rename", project)}
              onTogglePin={() => void pin(project)}
              onDelete={() => open("delete", project)}
            />
            {expandedProject === project.project_id && <div id={`project-threads-${project.project_id}`} className="ml-3">
              <NavProjects projectId={project.project_id} projects={projects} revision={revision} onChanged={onChanged} onOpenProject={(id) => {
                setExpanded(true)
                onExpand(id)
              }} />
            </div>}
          </SidebarMenuItem>)}
        </SidebarMenu>
      )}
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
