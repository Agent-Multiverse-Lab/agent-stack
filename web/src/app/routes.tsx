import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";

import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "@/i18n";
import AuthenticationPage from "@/pages/auth/AuthenticationPage";
import MainLayout from "@/layouts/MainLayout/MainLayout";
import ChatPage from "@/pages/chat/ChatPage";
import KnowledgePage from "@/pages/knowledge/KnowledgePage";
import KnowledgeBaseDetailPage from "@/pages/knowledge/KnowledgeBaseDetailPage";
import AgentPage from "@/pages/agent/AgentPage";
import Satellite from "@/pages/statellite/Satellite";
import SandboxPage from "@/pages/sandbox/SandboxPage";

const MapPage = lazy(() => import("@/pages/map/MapPage"));

function useRestoredSession() {
  const { accessToken, restore } = useAuth();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let current = true;
    void restore().finally(() => {
      if (current) setReady(true);
    });
    return () => {
      current = false;
    };
  }, [restore]);

  return { accessToken, ready };
}

function RouteLoading() {
  const { t } = useTranslation();
  return (
    <div className="grid h-dvh place-items-center text-muted-foreground">
      {t("Loading...")}
    </div>
  );
}

function GuestRoute() {
  const { accessToken, ready } = useRestoredSession();

  if (!ready) return <RouteLoading />;
  return accessToken ? <Navigate to="/" replace /> : <Outlet />;
}

function ProtectedRoute() {
  const { accessToken, ready } = useRestoredSession();
  const location = useLocation();

  if (!ready) return <RouteLoading />;
  return accessToken ? <Outlet /> : (
    <Navigate to="/login" state={{ from: location }} replace />
  );
}

export default function AppRoutes() {
  const { t } = useTranslation();
  return (
    <Routes>
      <Route element={<GuestRoute />}>
        <Route path="login" element={<AuthenticationPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route index element={<ChatPage />} />
          <Route path="c/:threadId" element={<ChatPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="knowledge/:kbId" element={<KnowledgeBaseDetailPage />} />
          <Route path="agent" element={<AgentPage />} />
          <Route path="static" element={<Satellite />} />
          <Route
            path="map"
            element={
              <Suspense
                fallback={<div className="grid h-full place-items-center text-muted-foreground">{t("Loading map")}</div>}
              >
                <MapPage />
              </Suspense>
            }
          />
          <Route path="sandbox" element={<SandboxPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
