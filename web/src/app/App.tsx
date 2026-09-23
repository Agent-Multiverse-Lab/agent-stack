import { useEffect } from "react";
import { useLocation } from "react-router";

import AppRoutes from "@/app/routes";
import { Toaster } from "@/components/ui/sonner";
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
      "/static": "Satellite",
      "/sandbox": "Sandbox",
    };
    const page =
      titles[location.pathname] ??
      (location.pathname.startsWith("/c/")
        ? "Chat"
        : location.pathname.startsWith("/knowledge/")
          ? "Knowledge"
          : "AM");
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
