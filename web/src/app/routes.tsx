import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";

import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "@/i18n";
import AuthenticationPage from "@/pages/auth/AuthenticationPage";
import MainLayout from "@/layouts/MainLayout/MainLayout";
import ChatPage from "@/pages/chat/ChatPage";
import KnowledgePage from "@/pages/knowledge/KnowledgePage";
import LibraryPage from "@/pages/library/LibraryPage";
import AgentPage from "@/pages/agent/AgentPage";
import StaticPage from "@/pages/static/StaticPage";
import SandboxPage from "@/pages/sandbox/SandboxPage";

function AuthGate({
  children,
  login = false,
}: {
  children: React.ReactNode;
  login?: boolean;
}) {
  const { t } = useTranslation();
  const { accessToken, restore } = useAuth();
  const [ready, setReady] = useState(false);
  const location = useLocation();
  useEffect(() => {
    let current = true;
    void restore().finally(() => {
      if (current) setReady(true);
    });
    return () => {
      current = false;
    };
  }, [restore]);
  if (!ready)
    return (
      <div className="grid h-dvh place-items-center text-muted-foreground">{t("Loading...")}</div>
    );
  if (login) return accessToken ? <Navigate to="/" replace /> : children;
  return accessToken ? (
    children
  ) : (
    <Navigate to="/login" state={{ from: location }} replace />
  );
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <AuthGate login>
            <AuthenticationPage />
          </AuthGate>
        }
      />
      <Route
        element={
          <AuthGate>
            <MainLayout />
          </AuthGate>
        }
      >
        <Route path="/" element={<ChatPage />} />
        <Route path="/c/:threadId" element={<ChatPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/agent" element={<AgentPage />} />
        <Route path="/static" element={<StaticPage />} />
        <Route path="/sandbox" element={<SandboxPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
