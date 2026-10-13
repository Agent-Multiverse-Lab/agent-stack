import { type CSSProperties, useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router";

import { AppSidebar } from "@/components/app-sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { useAuth } from "@/context/AuthContext";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import {
  ProfileDialog,
  SearchChat,
} from "@/layouts/MainLayout/components/NavigationDialogs";
import { Settings } from "@/layouts/MainLayout/components/Settings";

export default function MainLayout() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const location = useLocation();
  const [profileOpen, setProfileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const openProfile = () => {
    setSettingsOpen(false);
    setProfileOpen(true);
  };
  const openSettings = () => {
    setProfileOpen(false);
    setSettingsOpen(true);
  };

  const page = location.pathname.startsWith("/c/")
    ? "Chat"
    : location.pathname.startsWith("/knowledge/")
      ? "Knowledge"
      : ({
          "/": "Chat",
          "/knowledge": "Knowledge",
          "/agent": "Agent",
          "/static": "Satellite",
          "/map": "Map",
          "/sandbox": "Sandbox",
        } as Record<string, string>)[location.pathname] ?? "Chat";

  return (
    <>
      <SidebarProvider
        className="h-dvh min-h-0 overflow-hidden"
        style={{ "--sidebar-width": "15.5rem" } as CSSProperties}
      >
        <AppSidebar
          variant="sidebar"
          aria-label={t("Application navigation")}
          onProfile={openProfile}
          onSettings={openSettings}
          onSearch={() => setSearchOpen(true)}
        />
        <SidebarInset className="min-h-0 min-w-0 overflow-hidden">
          <header
            className={cn(
              "flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12",
              location.pathname.startsWith("/sandbox") && "border-b border-border",
            )}
          >
            <div className="flex items-center gap-2 px-4">
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <BreadcrumbLink render={<Link to="/" />}>
                      Agent Multiverse
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbPage>{t(page)}</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
            </div>
          </header>
          <div className="min-h-0 flex-1 overflow-hidden">
            <Outlet />
          </div>
        </SidebarInset>
      </SidebarProvider>
      <ProfileDialog
        open={profileOpen}
        close={() => setProfileOpen(false)}
        user={user}
      />
      <Settings
        open={settingsOpen}
        close={() => setSettingsOpen(false)}
        user={user}
      />
      <SearchChat open={searchOpen} close={() => setSearchOpen(false)} />
    </>
  );
}
