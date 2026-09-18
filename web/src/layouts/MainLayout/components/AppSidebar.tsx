import { useEffect } from "react";
import {
  BookOpenCheck,
  Bot,
  Layers,
  Library,
  LogIn,
  Search,
  SquarePen,
  SquareTerminal,
} from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router";

import logoUrl from "@/assets/logo.svg";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/context/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import ChatHistory from "@/layouts/MainLayout/components/ChatHistory";
import { useTranslation } from "@/i18n";

const features = [
  { to: "/library", label: "Library", icon: Library },
  { to: "/knowledge", label: "Knowledge", icon: BookOpenCheck },
  { to: "/agent", label: "Agent", icon: Bot },
  { to: "/static", label: "Static", icon: Layers },
  { to: "/sandbox", label: "Sandbox", icon: SquareTerminal },
];

export default function AppSidebar({
  onProfile,
  onSettings,
  onSearch,
}: {
  onProfile: () => void;
  onSettings: () => void;
  onSearch: () => void;
}) {
  const { t } = useTranslation();
  const { accessToken, logout } = useAuth();
  const { isMobile, setOpenMobile } = useSidebar();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => setOpenMobile(false), [location.pathname, setOpenMobile]);

  const newChat = () => {
    setOpenMobile(false);
    navigate("/");
  };
  const openSearch = () => {
    setOpenMobile(false);
    onSearch();
  };

  return (
    <Sidebar collapsible="icon" aria-label={t("Application navigation")}>
      <SidebarHeader className="shrink-0 px-2 pt-3 pb-1">
        <div className="flex h-9 items-center justify-between gap-1 group-data-[collapsible=icon]:justify-center">
          <Link
            to="/"
            onClick={() => setOpenMobile(false)}
            className="flex min-w-0 items-center gap-2 px-2 font-semibold group-data-[collapsible=icon]:hidden"
            aria-label={t("AM home")}
          >
            <img src={logoUrl} alt="" className="size-[1.15rem]" />
            <span>AM</span>
          </Link>
          <div className="flex items-center gap-1 group-data-[collapsible=icon]:hidden">
            <Tooltip>
              <TooltipTrigger
                type="button"
                className="grid size-8 place-items-center rounded-md text-slate hover:bg-sidebar-accent"
                aria-label={t("Search conversations")}
                onClick={openSearch}
              >
                <Search size={18} />
              </TooltipTrigger>
              <TooltipContent>{t("Search (Cmd+K)")}</TooltipContent>
            </Tooltip>
            <SidebarTrigger
              className="size-8 text-slate"
              aria-label={isMobile ? t("Close sidebar") : t("Collapse sidebar")}
            />
          </div>
          <SidebarTrigger
            className="hidden group-data-[collapsible=icon]:inline-flex"
            aria-label={t("Expand sidebar")}
          />
        </div>
      </SidebarHeader>

      <SidebarContent className="overflow-hidden">
        <SidebarGroup className="shrink-0 px-2 pt-1 pb-0">
          <SidebarGroupContent>
            <nav aria-label={t("Primary navigation")}>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton tooltip={t("New chat")} onClick={newChat}>
                    <SquarePen />
                    <span>{t("New chat")}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                {features.map(({ to, label, icon: Icon }) => (
                  <SidebarMenuItem key={to}>
                    <SidebarMenuButton
                      render={<Link to={to} onClick={() => setOpenMobile(false)} />}
                      tooltip={t(label)}
                      isActive={location.pathname === to}
                      aria-current={location.pathname === to ? "page" : undefined}
                    >
                      <Icon />
                      <span>{t(label)}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
        {accessToken && <ChatHistory />}
      </SidebarContent>

      <SidebarFooter className="shrink-0 px-2 pt-1 pb-3">
        <SidebarMenu>
          <SidebarMenuItem className="hidden group-data-[collapsible=icon]:block">
            <SidebarMenuButton tooltip={t("Search conversations")} onClick={openSearch}>
              <Search />
              <span>{t("Search conversations")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            {accessToken ? (
              <DropdownMenu>
                <DropdownMenuTrigger
                  type="button"
                  className="flex h-10 w-full items-center gap-2 rounded-md px-2 text-sm hover:bg-sidebar-accent focus-visible:outline-2 focus-visible:outline-sidebar-ring group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0"
                  aria-label={t("Open AM User account menu")}
                >
                  <Avatar className="size-7" aria-hidden="true">
                    <AvatarFallback className="bg-graphite font-utility text-[11px] font-bold text-paper">
                      A
                    </AvatarFallback>
                  </Avatar>
                  <span className="truncate group-data-[collapsible=icon]:hidden">
                    {t("AM User")}
                  </span>
                </DropdownMenuTrigger>
                <DropdownMenuContent side="top" align="start">
                  <DropdownMenuItem
                    onClick={() => {
                      setOpenMobile(false);
                      onProfile();
                    }}
                  >
                    {t("Profile")}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      setOpenMobile(false);
                      onSettings();
                    }}
                  >
                    {t("Settings")}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => {
                      setOpenMobile(false);
                      logout();
                      navigate("/login");
                    }}
                  >
                    {t("Log out")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <SidebarMenuButton
                render={<Link to="/login" onClick={() => setOpenMobile(false)} />}
                tooltip={t("Log in")}
              >
                <LogIn />
                <span>{t("Log in")}</span>
              </SidebarMenuButton>
            )}
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
