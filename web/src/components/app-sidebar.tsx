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
  XIcon,
} from "lucide-react"
import { useEffect, useState } from "react"
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
  SidebarGroup,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
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
  const [searchQuery, setSearchQuery] = useState("")
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
        {accessToken && (
          <SidebarGroup className="pt-1 pb-0">
            <div className="flex h-8 w-full items-center gap-2 rounded-md border border-input bg-background px-2 focus-within:border-ring group-data-[collapsible=icon]:hidden">
              <SearchIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <SidebarInput
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") setSearchQuery("")
                }}
                placeholder={t("Search conversations")}
                aria-label={t("Search conversation")}
                className="h-7 min-w-0 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0"
              />
              {searchQuery && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={t("Clear search")}
                  onClick={() => setSearchQuery("")}
                >
                  <XIcon />
                </Button>
              )}
            </div>
            <SidebarMenu className="hidden group-data-[collapsible=icon]:flex">
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip={t("Search conversations")}
                  aria-label={t("Search conversations")}
                  onClick={() => {
                    setOpenMobile(false)
                    onSearch()
                  }}
                >
                  <SearchIcon />
                  <span>{t("Search conversations")}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroup>
        )}
        <NavMain items={data.navMain} />
        {accessToken && <NavProjects onSearch={onSearch} query={searchQuery} />}
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
