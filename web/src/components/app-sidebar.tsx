"use client"

import * as React from "react"
import {
  BotIcon,
  BookOpenCheckIcon,
  FilesIcon,
  LibraryIcon,
  SquarePenIcon,
  SquareTerminalIcon,
} from "lucide-react"
import { useEffect } from "react"
import { useLocation, useNavigate } from "react-router"

import logoUrl from "@/assets/logo.svg"
import { NavMain } from "@/components/nav-main"
import { NavProjects } from "@/components/nav-projects"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import { useAuth } from "@/context/AuthContext"

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
  const { setOpenMobile } = useSidebar()
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => setOpenMobile(false), [location.pathname, setOpenMobile])

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
        isActive:
          location.pathname === "/knowledge" || location.pathname === "/library",
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
        title: "Library",
        url: "/library",
        icon: <LibraryIcon />,
        isActive: location.pathname === "/library",
      },
      {
        title: "Knowledge",
        url: "/knowledge",
        icon: <BookOpenCheckIcon />,
        isActive: location.pathname === "/knowledge",
      },
      {
        title: "Agent",
        url: "/agent",
        icon: <BotIcon />,
        isActive: location.pathname === "/agent",
      },
      {
        title: "Static",
        url: "/static",
        icon: <FilesIcon />,
        isActive: location.pathname === "/static",
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
      <SidebarHeader className="h-12 flex-row items-center gap-1">
        <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
          <TeamSwitcher teams={data.teams} onSettings={onSettings} />
        </div>
        <SidebarTrigger className="shrink-0 group-data-[collapsible=icon]:mx-auto" />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
        {accessToken && <NavProjects onSearch={onSearch} />}
      </SidebarContent>
      <SidebarFooter>
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
