import { useEffect, useState } from "react";
import { Dropdown, Tooltip } from "antd";
import {
  BookOpenCheck,
  Bot,
  Layers,
  Library,
  LogIn,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  SquarePen,
  SquareTerminal,
} from "lucide-react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";
import logoUrl from "@/assets/logo.svg";
import ChatHistory from "@/layouts/MainLayout/components/ChatHistory";
import {
  Avatar,
  ProfileDialog,
  SearchChat,
  SettingsDialog,
} from "@/layouts/MainLayout/components/NavigationDialogs";
import { useAuth } from "@/context/AuthContext";

const features = [
  { to: "/library", label: "Library", icon: Library },
  { to: "/knowledge", label: "Knowledge", icon: BookOpenCheck },
  { to: "/agent", label: "Agent", icon: Bot },
  { to: "/static", label: "Static", icon: Layers },
  { to: "/sandbox", label: "Sandbox", icon: SquareTerminal },
];
export default function MainLayout() {
  const { accessToken, user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 900px)").matches,
  );
  const [profileOpen, setProfileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 900px)");
    const update = () => {
      setNarrow(query.matches);
      if (!query.matches) setMobileOpen(false);
    };
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => setMobileOpen(false), [location.pathname]);
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
  const mini = collapsed && !narrow;
  const newChat = () => {
    setMobileOpen(false);
    navigate("/");
  };
  return (
    <>
      <div className="flex h-dvh w-full overflow-hidden bg-paper text-graphite">
        <aside
          className={`relative z-20 h-full shrink-0 overflow-hidden bg-mist transition-[width,transform] duration-200 max-[900px]:fixed max-[900px]:inset-y-0 max-[900px]:left-0 max-[900px]:z-50 max-[900px]:w-[min(86vw,19rem)] ${mini ? "w-[60px]" : "w-[260px]"} ${narrow ? (mobileOpen ? "translate-x-0" : "-translate-x-[102%]") : ""}`}
          aria-label="Application navigation"
        >
          <div
            className={`flex h-full flex-col overflow-hidden ${mini ? "w-[60px]" : "w-[260px]"}`}
          >
            <header
              className={`flex min-h-[3.25rem] items-center pt-3 pb-1 ${mini ? "justify-center" : "justify-between px-4"}`}
            >
              {mini ? (
                <Tooltip title="Expand sidebar" placement="right">
                  <button
                    type="button"
                    aria-label="Expand sidebar"
                    onClick={() => setCollapsed(false)}
                  >
                    <PanelLeftOpen size={18} />
                  </button>
                </Tooltip>
              ) : (
                <>
                  <Link
                    to="/"
                    className="inline-flex items-center gap-2 font-semibold"
                    aria-label="AM home"
                  >
                    <img
                      src={logoUrl}
                      className="h-[1.15rem] w-[1.15rem]"
                      alt=""
                    />
                    AM
                  </Link>
                  <div className="flex gap-1">
                    <Tooltip title="Search (Cmd+K)">
                      <button
                        type="button"
                        className="grid size-8 place-items-center text-slate"
                        aria-label="Search conversations"
                        onClick={() => setSearchOpen(true)}
                      >
                        <Search size={18} />
                      </button>
                    </Tooltip>
                    <button
                      type="button"
                      className="grid size-8 place-items-center text-slate"
                      aria-label="Collapse sidebar"
                      onClick={() => setCollapsed(true)}
                    >
                      <PanelLeftClose size={18} />
                    </button>
                  </div>
                </>
              )}
            </header>
            <nav
              className="grid gap-2 px-1.5 pt-0.5 pb-2"
              aria-label="Primary navigation"
            >
              <button
                type="button"
                className={`flex min-h-9 items-center gap-2 rounded-sm px-2.5 text-left text-sm hover:bg-graphite/8 ${mini ? "justify-center" : ""}`}
                onClick={newChat}
                title="New chat"
              >
                <SquarePen size={18} />
                {!mini && "New chat"}
              </button>
              <div className="grid gap-px" aria-label="Features">
                {features.map(({ to, label, icon: Icon }) => (
                  <Link
                    key={to}
                    to={to}
                    title={label}
                    className={`flex min-h-9 items-center gap-2 rounded-sm px-2.5 text-sm hover:bg-graphite/8 ${mini ? "justify-center" : ""} ${location.pathname === to ? "bg-graphite/8 font-semibold" : ""}`}
                  >
                    <Icon size={18} />
                    {!mini && label}
                  </Link>
                ))}
              </div>
            </nav>
            {accessToken && !mini ? (
              <ChatHistory />
            ) : (
              <div className="min-h-0 flex-1" />
            )}
            <footer className="grid gap-px px-1.5 pt-1 pb-3">
              {mini && (
                <button
                  type="button"
                  className="grid min-h-9 place-items-center text-slate"
                  aria-label="Search conversations"
                  onClick={() => setSearchOpen(true)}
                >
                  <Search size={18} />
                </button>
              )}
              {accessToken ? (
                <Dropdown
                  trigger={["click"]}
                  placement="topLeft"
                  menu={{
                    items: [
                      { key: "profile", label: "Profile" },
                      { key: "settings", label: "Settings" },
                      { key: "logout", label: "Log out", danger: true },
                    ],
                    onClick: ({ key }) => {
                      if (key === "profile") setProfileOpen(true);
                      if (key === "settings") setSettingsOpen(true);
                      if (key === "logout") {
                        logout();
                        navigate("/login");
                      }
                    },
                  }}
                >
                  <button
                    type="button"
                    className={`flex min-h-10 items-center gap-2 rounded-sm px-2 text-sm hover:bg-graphite/8 ${mini ? "justify-center" : ""}`}
                    aria-label="Open AM User account menu"
                  >
                    <Avatar />
                    {!mini && "AM User"}
                  </button>
                </Dropdown>
              ) : (
                <Link
                  to="/login"
                  className="flex items-center gap-2 px-2.5 py-2 text-slate"
                >
                  <LogIn size={17} />
                  {!mini && "Log in"}
                </Link>
              )}
            </footer>
          </div>
        </aside>
        {narrow && mobileOpen && (
          <button
            type="button"
            className="fixed inset-0 z-40 bg-graphite/36"
            aria-label="Close sidebar"
            onClick={() => setMobileOpen(false)}
          />
        )}
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <header className="group flex min-h-[52px] shrink-0 items-center justify-end gap-4 px-[clamp(0.75rem,2vw,1.25rem)] py-2">
            {narrow && (
              <button
                type="button"
                aria-label="Open sidebar"
                className="mr-auto"
                onClick={() => setMobileOpen(true)}
              >
                <PanelLeftOpen size={18} />
              </button>
            )}
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  { key: "new-chat", label: "New chat" },
                  { key: "settings", label: "Settings" },
                ],
                onClick: ({ key }) => {
                  if (key === "new-chat") newChat();
                  else setSettingsOpen(true);
                },
              }}
            >
              <button
                type="button"
                className="grid size-9 place-items-center text-slate"
                aria-label="More options"
              >
                <MoreHorizontal size={18} />
              </button>
            </Dropdown>
          </header>
          <div className="min-h-0 flex-1 overflow-hidden">
            <Outlet />
          </div>
        </main>
      </div>
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
      <SearchChat
        open={searchOpen}
        close={() => setSearchOpen(false)}
      />
    </>
  );
}
