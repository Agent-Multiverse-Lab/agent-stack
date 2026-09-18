import { Link, useNavigate } from "react-router";

import authIllustrationUrl from "@/assets/auth-illustrate.png";
import logoUrl from "@/assets/logo.svg";
import LoginForm from "@/pages/auth/components/LoginForm";

export default function AuthenticationPage() {
  const navigate = useNavigate();
  return (
    <main className="relative h-svh overflow-y-auto bg-white text-[#10272b]">
      <header
        className="absolute inset-x-8 top-8 z-10 flex items-center justify-between max-[1000px]:inset-x-4 max-[1000px]:top-4"
        aria-label="Page header"
      >
        <Link
          className="inline-flex min-h-9 items-center gap-2 rounded-lg px-1 text-sm font-bold tracking-[-0.02em] hover:text-[#15545a] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#15545a]"
          to="/"
          aria-label="AM home"
        >
          <img
            className="size-6 object-contain"
            src={logoUrl}
            alt=""
            aria-hidden
          />
          <span>AM</span>
        </Link>
        <a
          className="grid size-9 place-items-center rounded-lg text-[#10272b] hover:bg-[#f2f4f3] hover:text-[#15545a] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#15545a]"
          href="https://github.com/leeejuju/multi-agent-s2c"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="AM on GitHub"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M12 .5a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.04c-3.22.7-3.9-1.37-3.9-1.37-.53-1.35-1.29-1.71-1.29-1.71-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.74.4-1.26.73-1.55-2.57-.29-5.27-1.29-5.27-5.72 0-1.26.45-2.3 1.2-3.11-.13-.29-.52-1.47.11-3.06 0 0 .98-.31 3.16 1.19A11 11 0 0 1 12 6.1c.97 0 1.94.13 2.84.38 2.18-1.5 3.16-1.19 3.16-1.19.63 1.59.24 2.77.12 3.06.75.81 1.19 1.85 1.19 3.11 0 4.44-2.7 5.43-5.28 5.72.41.35.78 1.02.78 2.06v3.1c0 .31.21.67.79.56A11.5 11.5 0 0 0 12 .5Z" />
          </svg>
        </a>
      </header>
      <div className="flex min-h-full items-center justify-center p-6 max-[1000px]:items-start max-[1000px]:px-4 max-[1000px]:pt-20 max-[1000px]:pb-4">
        <section
          className="grid h-[580px] w-full max-w-[960px] grid-cols-2 overflow-hidden rounded-[20px] bg-white shadow-[0_28px_80px_rgba(8,37,43,0.14)] max-[1000px]:h-auto max-[1000px]:grid-cols-1"
          aria-label="AM authentication"
        >
          <div className="min-h-0 overflow-hidden bg-[#f2f4f3] max-[1000px]:h-[clamp(240px,48vw,420px)]">
            <img
              className="size-full object-cover object-center"
              src={authIllustrationUrl}
              alt=""
              aria-hidden
            />
          </div>
          <div className="flex min-h-0 min-w-0 overflow-y-auto bg-white px-10 py-10 max-[1000px]:px-[clamp(1.5rem,8vw,3rem)] max-[1000px]:py-12">
            <div className="flex w-full justify-center pt-[76px]">
              <LoginForm
                onAuthenticated={() => navigate("/", { replace: true })}
              />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
