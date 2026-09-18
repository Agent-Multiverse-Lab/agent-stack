import { useNavigate } from "react-router";

import { LoginForm } from "@/pages/auth/components/login-form";

export default function AuthenticationPage() {
  const navigate = useNavigate();

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted p-6 text-foreground md:p-10">
      <div className="w-full max-w-sm md:max-w-4xl">
        <LoginForm onAuthenticated={() => navigate("/", { replace: true })} />
      </div>
    </main>
  );
}
