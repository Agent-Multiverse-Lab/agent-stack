import { useEffect, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { Outlet, useNavigate } from "react-router";

import { useAuth } from "@/context/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import AppSidebar from "@/layouts/MainLayout/components/AppSidebar";
import { useTranslation } from "@/i18n";
import {
  ProfileDialog,
  SearchChat,
  SettingsDialog,
} from "@/layouts/MainLayout/components/NavigationDialogs";

export default function MainLayout() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
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

  return (
    <>
      <SidebarProvider className="h-dvh min-h-0 overflow-hidden bg-paper text-graphite">
        <AppSidebar
          onProfile={openProfile}
          onSettings={openSettings}
          onSearch={() => setSearchOpen(true)}
        />
        <SidebarInset className="min-h-0 min-w-0 overflow-hidden">
          <header className="flex min-h-[52px] shrink-0 items-center justify-end gap-4 px-[clamp(0.75rem,2vw,1.25rem)] py-2">
            <SidebarTrigger className="mr-auto md:hidden" aria-label={t("Open sidebar")} />
            <DropdownMenu>
              <DropdownMenuTrigger
                type="button"
                className="grid size-9 place-items-center text-slate"
                aria-label={t("More options")}
              >
                <MoreHorizontal size={18} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => navigate("/")}>
                  {t("New chat")}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={openSettings}>{t("Settings")}</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
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
      <SettingsDialog
        open={settingsOpen}
        close={() => setSettingsOpen(false)}
        user={user}
      />
      <SearchChat open={searchOpen} close={() => setSearchOpen(false)} />
    </>
  );
}
