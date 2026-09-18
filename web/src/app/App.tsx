import { useEffect } from "react";
import { useLocation } from "react-router";
import { Toaster } from "sonner";

import AppRoutes from "@/app/routes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useTranslation } from "@/i18n";

export default function App() {
  const { t } = useTranslation();
  const location = useLocation();
  useEffect(() => {
    const titles: Record<string, string> = {
      "/": "Chat",
      "/library": "Library",
      "/knowledge": "Knowledge",
      "/agent": "Agent",
      "/static": "Static",
      "/sandbox": "Sandbox",
    };
    const page = titles[location.pathname] ?? (location.pathname.startsWith("/c/") ? "Chat" : "AM");
    document.title = `${t(page)} · AM`;
  }, [location.pathname, t]);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return (
    <TooltipProvider>
      <AppRoutes />
      <Toaster position="top-center" richColors />
    </TooltipProvider>
  );
}
