"use client"

import * as React from "react"
import {
  BotIcon,
  BookOpenCheckIcon,
  FilesIcon,
  MapIcon,
  SearchIcon,
  SquarePenIcon,
  SquareTerminalIcon,
} from "lucide-react"
import { useLocation, useNavigate } from "react-router"

import logoUrl from "@/assets/logo.svg"
import { NavMain } from "@/components/nav-main"
import { NavProjects } from "@/components/nav-projects"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import { Button } from "@/components/ui/button"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { useAuth } from "@/context/AuthContext"
import { useTranslation } from "@/i18n"

type AppSidebarProps = React.ComponentProps<typeof Sidebar> & {
  onProfile: () => void
  onSettings: () => void
  onSearch: () => void
}

export function AppSidebar({
  onProfile,
  onSettings,
  onSearch,
  ...props
}: AppSidebarProps) {
  const { accessToken, user, logout } = useAuth()
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()

  const data = {
    user: {
      name: "AM User",
      email: user?.email ?? "",
      avatar: "",
    },
    teams: [
      {
        name: "Agent Multiverse",
        logo: <img src={logoUrl} alt="" className="size-4" />,
        url: "/",
        isActive:
          location.pathname === "/" || location.pathname.startsWith("/c/"),
      },
      {
        name: "Knowledge",
        logo: <BookOpenCheckIcon />,
        url: "/knowledge",
        isActive: location.pathname.startsWith("/knowledge"),
      },
      {
        name: "Sandbox",
        logo: <SquareTerminalIcon />,
        url: "/sandbox",
        isActive:
          location.pathname === "/sandbox" || location.pathname === "/static",
      },
    ],
    navMain: [
      {
        title: "New chat",
        url: "/",
        icon: <SquarePenIcon />,
        isActive: location.pathname === "/",
      },
      {
        title: "Knowledge",
        url: "/knowledge",
        icon: <BookOpenCheckIcon />,
        isActive: location.pathname.startsWith("/knowledge"),
      },
      {
        title: "Agent",
        url: "/agent",
        icon: <BotIcon />,
        isActive: location.pathname === "/agent",
      },
      {
        title: "Satellite",
        url: "/static",
        icon: <FilesIcon />,
        isActive: location.pathname === "/static",
      },
      {
        title: "Map",
        url: "/map",
        icon: <MapIcon />,
        isActive: location.pathname === "/map",
      },
      {
        title: "Sandbox",
        url: "/sandbox",
        icon: <SquareTerminalIcon />,
        isActive: location.pathname === "/sandbox",
      },
    ],
  }

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="mt-1.5 h-8 flex-row items-center gap-0.5 px-2 py-0">
        <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
          <TeamSwitcher teams={data.teams} onSettings={onSettings} />
        </div>
        {accessToken && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t("Search conversations")}
            title={t("Search conversations")}
            className="size-[30px] shrink-0 rounded-[7px] text-muted-foreground hover:text-foreground group-data-[collapsible=icon]:hidden"
            onClick={onSearch}
          >
            <SearchIcon className="size-4" />
          </Button>
        )}
        <SidebarTrigger className="size-[30px] shrink-0 rounded-[7px] group-data-[collapsible=icon]:mx-auto" />
      </SidebarHeader>
      <SidebarContent className="gap-2 py-0">
        <NavMain items={data.navMain} />
        {accessToken && <SidebarSeparator className="mx-2.5 my-1 group-data-[collapsible=icon]:hidden" />}
        {accessToken && <NavProjects onSearch={onSearch} />}
      </SidebarContent>
      <SidebarFooter className="px-2 pt-0 pb-1.5">
        <NavUser
          user={data.user}
          onProfile={onProfile}
          onSettings={onSettings}
          onLogout={() => {
            logout()
            navigate("/login")
          }}
        />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
