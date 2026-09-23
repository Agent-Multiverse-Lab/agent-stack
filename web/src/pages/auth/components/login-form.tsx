import { useRef, useState } from "react";
import type { SubmitEvent } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { CircleAlert, CircleCheck, Eye, EyeOff, LoaderCircle } from "lucide-react";
import { Link } from "react-router";

import authIllustrationUrl from "@/assets/auth-illustrate.png";
import logoUrl from "@/assets/logo.svg";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "@/i18n";

gsap.registerPlugin(useGSAP);

export function LoginForm({
  onAuthenticated,
}: {
  onAuthenticated: () => void;
}) {
  const { t } = useTranslation();
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [registrationComplete, setRegistrationComplete] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const confirmPasswordContainer = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.to(confirmPasswordContainer.current, {
      height: isRegister ? "auto" : 0,
      autoAlpha: isRegister ? 1 : 0,
      y: isRegister ? 0 : -6,
      duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 0.3,
      ease: "power2.inOut",
      overwrite: true,
    });
  }, { dependencies: [isRegister], scope: confirmPasswordContainer });

  const clearFeedback = () => {
    setRequestError("");
    setRegistrationComplete(false);
  };

  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearFeedback();
    if (isRegister && confirmPassword !== password) {
      setRequestError(t("Passwords do not match"));
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
        error instanceof Error ? error.message : t("Authentication failed"),
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card
      className="gap-0 overflow-hidden p-0 shadow-sm"
      aria-labelledby="authentication-title"
    >
      <CardContent className="grid min-h-144 p-0 md:grid-cols-2">
        <form
          className="flex flex-col justify-center p-6 md:p-8 lg:p-10"
          onSubmit={(event) => void submit(event)}
        >
          <FieldGroup className="gap-5">
            <header className="flex flex-col items-center gap-2 text-center">
              <Link
                to="/"
                aria-label={t("AM home")}
                className="mb-3 inline-flex items-center gap-2 rounded-md font-semibold focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
              >
                <img className="size-6" src={logoUrl} alt="" aria-hidden />
                <span>AM</span>
              </Link>
              <h1
                id="authentication-title"
                className="text-2xl font-bold tracking-tight"
              >
                {isRegister ? t("Create your account") : t("Welcome back")}
              </h1>
            </header>

            <Field>
              <FieldLabel htmlFor="auth-email">{t("Email")}</FieldLabel>
              <Input
                id="auth-email"
                type="email"
                name="email"
                autoComplete="email"
                maxLength={255}
                required
                placeholder="m@example.com"
                className="h-10"
                value={email}
                disabled={submitting}
                onChange={(event) => {
                  setEmail(event.target.value);
                  clearFeedback();
                }}
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="auth-password">{t("Password")}</FieldLabel>
              <div className="relative">
                <Input
                  id="auth-password"
                  type={showPassword ? "text" : "password"}
                  name="password"
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  minLength={6}
                  maxLength={128}
                  required
                  placeholder={t("Enter your password")}
                  className="h-10 pr-11"
                  value={password}
                  disabled={submitting}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    clearFeedback();
                  }}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={showPassword ? t("Hide password") : t("Show password")}
                  className="absolute top-1 right-1 text-muted-foreground"
                  disabled={submitting}
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
                </Button>
              </div>
            </Field>

            <div
              ref={confirmPasswordContainer}
              className="invisible -mt-5 h-0 overflow-hidden opacity-0"
              aria-hidden={!isRegister}
              inert={!isRegister}
            >
              <Field className="pt-5">
                <FieldLabel htmlFor="auth-confirm-password">
                  {t("Ensure your password")}
                </FieldLabel>
                <div className="relative">
                  <Input
                    id="auth-confirm-password"
                    type={showConfirmPassword ? "text" : "password"}
                    name="confirmPassword"
                    autoComplete="new-password"
                    maxLength={128}
                    required={isRegister}
                    placeholder={t("Ensure your password")}
                    className="h-10 pr-11 hover:border-ring focus-visible:border-foreground/60 focus-visible:ring-0"
                    value={confirmPassword}
                    disabled={submitting || !isRegister}
                    onChange={(event) => {
                      setConfirmPassword(event.target.value);
                      clearFeedback();
                    }}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={
                      showConfirmPassword
                        ? t("Hide confirmation password")
                        : t("Show confirmation password")
                    }
                    className="absolute top-1 right-1 text-muted-foreground"
                    disabled={submitting || !isRegister}
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
                  </Button>
                </div>
              </Field>
            </div>

            {registrationComplete && (
              <Alert>
                <CircleCheck />
                <AlertDescription>
                  {t("Account created successfully. Please log in.")}
                </AlertDescription>
              </Alert>
            )}
            {requestError && (
              <Alert variant="destructive">
                <CircleAlert />
                <AlertDescription>{requestError}</AlertDescription>
              </Alert>
            )}

            <Field>
              <Button type="submit" size="lg" className="w-full" disabled={submitting}>
                {submitting && <LoaderCircle className="animate-spin" aria-hidden />}
                {isRegister ? t("Create Account") : t("Sign In")}
              </Button>
            </Field>
            <FieldDescription className="text-center">
              {isRegister ? t("Already have an account?") : t("Don't have an account?")}{" "}
              <Button
                type="button"
                variant="link"
                className="h-auto p-0 font-semibold"
                disabled={submitting}
                onClick={() => {
                  clearFeedback();
                  setIsRegister(!isRegister);
                  setConfirmPassword("");
                }}
              >
                {isRegister ? t("Log in") : t("Create one")}
              </Button>
            </FieldDescription>
          </FieldGroup>
        </form>
        <div className="relative hidden bg-muted md:block" aria-hidden="true">
          <img
            className="absolute inset-0 size-full object-cover object-center"
            src={authIllustrationUrl}
            alt=""
          />
        </div>
      </CardContent>
    </Card>
  );
}
