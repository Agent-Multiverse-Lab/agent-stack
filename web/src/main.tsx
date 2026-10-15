import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { ThemeProvider } from "next-themes";

import App from "@/app/App";
import { AuthProvider } from "@/context/AuthContext";
import { ModelProvider } from "@/context/ModelContext";
import "@/i18n";
import "@/styles/index.css";

createRoot(document.getElementById("app")!).render(
  <ThemeProvider attribute="class" defaultTheme="light" storageKey="am-theme">
    <BrowserRouter>
      <AuthProvider>
        <ModelProvider>
          <App />
        </ModelProvider>
      </AuthProvider>
    </BrowserRouter>
  </ThemeProvider>,
);
