"use client"

import * as React from "react"
import {
  BotIcon,
  BookOpenCheckIcon,
  FilesIcon,
  LibraryIcon,
  SearchIcon,
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
import { Button } from "@/components/ui/button"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
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
          location.pathname.startsWith("/knowledge") ||
          location.pathname === "/library",
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
        {accessToken && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t("Search conversations")}
            title={t("Search conversations")}
            className="size-7 shrink-0 text-muted-foreground hover:text-foreground group-data-[collapsible=icon]:hidden"
            onClick={() => {
              setOpenMobile(false)
              onSearch()
            }}
          >
            <SearchIcon className="size-4" />
          </Button>
        )}
        <SidebarTrigger className="shrink-0 group-data-[collapsible=icon]:mx-auto" />
      </SidebarHeader>
      <SidebarContent className="gap-2 py-1">
        <NavMain items={data.navMain} />
        {accessToken && <SidebarSeparator className="mx-2.5 my-1 group-data-[collapsible=icon]:hidden" />}
        {accessToken && <NavProjects onSearch={onSearch} />}
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border p-2">
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
