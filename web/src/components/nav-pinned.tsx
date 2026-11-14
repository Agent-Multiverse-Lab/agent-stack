import { FolderIcon, PinOffIcon } from "lucide-react"
import { useState } from "react"

import { updateProject, type ProjectResponse } from "@/api/project"
import { NavProjects } from "@/components/nav-projects"
import { SidebarMenuAction, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import { useTranslation } from "@/i18n"

export function NavPinned({ projects, revision, onChanged, onOpenProject }: {
  projects: ProjectResponse[]
  revision: number
  onChanged: () => void
  onOpenProject: (projectId: string) => void
}) {
  const { t } = useTranslation()
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)
  const pinned = projects.filter((project) => project.pinned)

  async function unpin(project: ProjectResponse) {
    setSaving(true)
    setError("")
    try {
      await updateProject(project.project_id, { pinned: false })
      onChanged()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("Operation failed. Please try again."))
    } finally {
      setSaving(false)
    }
  }

  return <NavProjects pinnedOnly projects={projects} revision={revision} onChanged={onChanged} hasLeading={pinned.length > 0 || Boolean(error)} leading={<>
    {pinned.map((project) => <SidebarMenuItem key={project.project_id}>
      <SidebarMenuButton onClick={() => onOpenProject(project.project_id)} title={project.name} className="text-[13px]">
        <FolderIcon /><span>{project.name}</span>
      </SidebarMenuButton>
      <SidebarMenuAction disabled={saving} onClick={() => void unpin(project)} aria-label={t("Unpin {{name}}", { name: project.name })}>
        <PinOffIcon />
      </SidebarMenuAction>
    </SidebarMenuItem>)}
    {error && <SidebarMenuItem><p role="alert" className="px-2 text-xs text-destructive">{error}</p></SidebarMenuItem>}
  </>} />
}
