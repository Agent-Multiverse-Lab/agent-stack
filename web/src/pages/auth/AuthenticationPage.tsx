import { useNavigate } from "react-router";

import { LoginForm } from "@/pages/auth/components/login-form";

export default function AuthenticationPage() {
  const navigate = useNavigate();

  return (
    <main className="flex min-h-svh items-center justify-center bg-background p-6 text-foreground">
      <div className="w-full max-w-[900px]">
        <LoginForm onAuthenticated={() => navigate("/", { replace: true })} />
      </div>
    </main>
  );
}
