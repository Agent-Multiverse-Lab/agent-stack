import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "@fontsource-variable/geist";

import App from "@/app/App";
import { AuthProvider } from "@/context/AuthContext";
import { ModelProvider } from "@/context/ModelContext";
import "@/i18n";
import "@/styles/index.css";

createRoot(document.getElementById("app")!).render(
  <BrowserRouter>
    <AuthProvider>
      <ModelProvider>
        <App />
      </ModelProvider>
    </AuthProvider>
  </BrowserRouter>,
);
