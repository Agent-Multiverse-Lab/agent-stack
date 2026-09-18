import { useState } from "react";
import type { FormEvent } from "react";
import { Alert, Button, ConfigProvider, Input } from "antd";
import { Lock, Mail } from "lucide-react";

import { useAuth } from "@/context/AuthContext";

export default function LoginForm({
  onAuthenticated,
}: {
  onAuthenticated: () => void;
}) {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [registrationComplete, setRegistrationComplete] = useState(false);

  const clearFeedback = () => {
    setRequestError("");
    setRegistrationComplete(false);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearFeedback();
    if (isRegister && confirmPassword !== password) {
      setRequestError("Passwords do not match");
      return;
    }
    setSubmitting(true);
    try {
      const payload = { email: email.trim().toLowerCase(), password };
      if (isRegister) {
        await auth.register(payload);
        setConfirmPassword("");
        setIsRegister(false);
        setRegistrationComplete(true);
      } else {
        await auth.login(payload);
        onAuthenticated();
      }
    } catch (error) {
      setRequestError(
        error instanceof Error ? error.message : "Authentication failed",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#15545a",
          colorText: "#10272b",
          colorTextPlaceholder: "#748386",
          colorBorder: "#cbd6d5",
          borderRadius: 12,
          controlHeightLG: 44,
          fontSizeLG: 14,
          fontFamily: "var(--font-sans)",
        },
      }}
    >
      <section
        className="w-full max-w-[310px]"
        aria-labelledby="authentication-title"
      >
        <div className="mb-7">
          <h1
            id="authentication-title"
            className="m-0 text-[32px] leading-[1.1] font-bold tracking-[-0.03em] text-[#10272b]"
          >
            {isRegister ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mb-0 mt-2 text-[14px] leading-5 text-[#66777a]">
            {isRegister
              ? "Create an AM account with your email."
              : "Sign in to AM with your email."}
          </p>
        </div>

        <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
          <Input
            size="large"
            type="email"
            name="email"
            autoComplete="email"
            maxLength={255}
            required
            aria-label="Email"
            placeholder="Enter your email"
            prefix={
              <Mail className="mr-1.5 h-4 w-4 text-[#748386]" aria-hidden />
            }
            value={email}
            disabled={submitting}
            onChange={(event) => {
              setEmail(event.target.value);
              clearFeedback();
            }}
          />
          <Input.Password
            size="large"
            name="password"
            autoComplete={isRegister ? "new-password" : "current-password"}
            minLength={6}
            maxLength={128}
            required
            aria-label="Password"
            placeholder="Enter your password"
            prefix={
              <Lock className="mr-1.5 h-4 w-4 text-[#748386]" aria-hidden />
            }
            value={password}
            disabled={submitting}
            onChange={(event) => {
              setPassword(event.target.value);
              clearFeedback();
            }}
          />
          <div
            className={`grid overflow-hidden transition-[grid-template-rows,opacity] duration-300 motion-reduce:transition-none ${isRegister ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}
          >
            <div className="min-h-0">
              {isRegister && (
                <Input.Password
                  size="large"
                  name="confirmPassword"
                  autoComplete="new-password"
                  maxLength={128}
                  required
                  aria-label="Ensure your password"
                  placeholder="Ensure your password"
                  prefix={
                    <Lock
                      className="mr-1.5 h-4 w-4 text-[#748386]"
                      aria-hidden
                    />
                  }
                  value={confirmPassword}
                  disabled={submitting}
                  onChange={(event) => {
                    setConfirmPassword(event.target.value);
                    clearFeedback();
                  }}
                />
              )}
            </div>
          </div>

          {registrationComplete && (
            <Alert
              message="Account created successfully. Please log in."
              showIcon
              type="success"
            />
          )}
          {!registrationComplete && requestError && (
            <Alert message={requestError} showIcon type="error" />
          )}

          <Button
            className="h-[44px]! w-full text-base! font-semibold! shadow-[0_6px_16px_rgba(21,84,90,0.18)]!"
            block
            htmlType="submit"
            loading={submitting}
            size="large"
            type="primary"
          >
            {isRegister ? "Create Account" : "Sign In"}
          </Button>
          <div className="text-center text-sm text-[#66777a]">
            {isRegister ? "Already have an account?" : "Don't have an account?"}
            <button
              type="button"
              className="ml-1 font-semibold text-[#15545a] hover:underline focus:outline-none"
              disabled={submitting}
              onClick={() => {
                clearFeedback();
                setIsRegister(!isRegister);
                setConfirmPassword("");
              }}
            >
              {isRegister ? "Log in" : "Create one"}
            </button>
          </div>
        </form>
      </section>
    </ConfigProvider>
  );
}
