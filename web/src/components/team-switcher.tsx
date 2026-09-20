"use client"

import * as React from "react"
import { ChevronDownIcon, Settings2Icon } from "lucide-react"
import { useNavigate } from "react-router"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useTranslation } from "@/i18n"

type Team = {
  name: string
  logo: React.ReactNode
  url: string
  isActive: boolean
}

export function TeamSwitcher({
  teams,
  onSettings,
}: {
  teams: Team[]
  onSettings: () => void
}) {
  const { t } = useTranslation()
  const { isMobile, setOpenMobile } = useSidebar()
  const navigate = useNavigate()
  const activeTeam = teams.find((team) => team.isActive) ?? teams[0]

  if (!activeTeam) {
    return null
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="default"
                className="data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground"
              />
            }
          >
            <div className="flex size-5 shrink-0 items-center justify-center [&_svg]:size-4">
              {activeTeam.logo}
            </div>
            <span className="min-w-0 flex-1 truncate text-left font-medium">
              {activeTeam.name}
            </span>
            <ChevronDownIcon className="ml-auto size-4 text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-fit"
            align="start"
            side={isMobile ? "bottom" : "right"}
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-xs text-muted-foreground">
                {t("Workspaces")}
              </DropdownMenuLabel>
              {teams.map((team, index) => (
                <DropdownMenuItem
                  key={team.name}
                  onClick={() => {
                    setOpenMobile(false)
                    navigate(team.url)
                  }}
                  className="gap-2 p-2"
                >
                  <div className="flex size-6 items-center justify-center rounded-md border">
                    {team.logo}
                  </div>
                  {team.name}
                  <DropdownMenuShortcut>⌘{index + 1}</DropdownMenuShortcut>
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem
                className="gap-2 p-2"
                onClick={() => {
                  setOpenMobile(false)
                  onSettings()
                }}
              >
                <div className="flex size-6 items-center justify-center rounded-md border bg-transparent">
                  <Settings2Icon className="size-4" />
                </div>
                <div className="font-medium text-muted-foreground">
                  {t("Settings")}
                </div>
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
