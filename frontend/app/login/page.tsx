"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import { useAuth } from "@/lib/auth";
import { GlassPanel } from "@/components/GlassPanel";
import { MarketingNav } from "@/components/marketing/MarketingNav";

// Google/Microsoft sign-in: real OAuth needs two things that don't exist
// yet -- an actual user table (auth.py currently has 2 hardcoded dev
// accounts, no persistence) and registered OAuth apps with Google Cloud
// Console + Microsoft Entra ID (client id/secret, same external-provider
// pattern as the Gemini/Hugging Face keys elsewhere in this build). These
// buttons are disabled with an honest "not set up yet" state rather than
// wired to a fake success path -- see docs/PROJECT_STATUS.md task list.
function SocialButton({ provider, icon }: { provider: string; icon: React.ReactNode }) {
  return (
    <button
      type="button"
      disabled
      title="Needs OAuth app registration -- not set up yet"
      className="btn btn-ghost flex-1 cursor-not-allowed justify-center gap-sp2 opacity-60"
    >
      {icon}
      {provider}
    </button>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      router.push("/choose");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen">
      <MarketingNav />
      <div className="mx-auto flex max-w-[400px] flex-col justify-center px-sp5 py-sp10">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 0.68, 0, 1.2] }}
        className="mb-sp6 text-center"
      >
        <div className="mb-sp4 inline-flex items-center gap-sp2 rounded-r4 border border-teal/20 bg-teal-dim px-sp3 py-1 text-[11px] font-semibold text-teal">
          <span className="live-dot" />
          AI Verification · Not AI Advice
        </div>
        <h1 className="text-[22px] font-extrabold leading-tight tracking-tight text-t1">
          See the math.
          <br />
          <span className="text-teal">Trust the data.</span>
        </h1>
      </motion.div>

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.08, ease: [0.22, 0.68, 0, 1.2] }}
      >
        <GlassPanel variant="accent" className="shadow-teal">
          <h2 className="mb-sp5 text-[15px] font-bold text-t1">Sign in</h2>

          <div className="mb-sp4 flex gap-sp2">
            <SocialButton
              provider="Google"
              icon={
                <svg width="15" height="15" viewBox="0 0 24 24">
                  <path
                    fill="currentColor"
                    d="M21.6 12.23c0-.68-.06-1.36-.17-2H12v3.99h5.4a4.63 4.63 0 0 1-2 3.04v2.5h3.23c1.9-1.75 2.97-4.32 2.97-7.53Z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 22c2.7 0 4.97-.89 6.63-2.42l-3.23-2.5c-.9.6-2.05.95-3.4.95-2.6 0-4.8-1.76-5.6-4.12H3.07v2.58A10 10 0 0 0 12 22Z"
                  />
                  <path fill="currentColor" d="M6.4 13.9a6 6 0 0 1 0-3.8V7.5H3.07a10 10 0 0 0 0 9l3.33-2.6Z" />
                  <path
                    fill="currentColor"
                    d="M12 5.98c1.47 0 2.79.5 3.82 1.5l2.87-2.87A9.96 9.96 0 0 0 12 2 10 10 0 0 0 3.07 7.5l3.33 2.6c.8-2.36 3-4.12 5.6-4.12Z"
                  />
                </svg>
              }
            />
            <SocialButton
              provider="Microsoft"
              icon={
                <svg width="15" height="15" viewBox="0 0 24 24">
                  <path fill="#F25022" d="M2 2h9.5v9.5H2z" />
                  <path fill="#7FBA00" d="M12.5 2H22v9.5h-9.5z" />
                  <path fill="#00A4EF" d="M2 12.5h9.5V22H2z" />
                  <path fill="#FFB900" d="M12.5 12.5H22V22h-9.5z" />
                </svg>
              }
            />
          </div>

          <div className="mb-sp4 flex items-center gap-sp3 text-[11px] text-t3">
            <div className="h-px flex-1 bg-border" />
            or with username
            <div className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={onSubmit} className="flex flex-col gap-sp4">
            <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
              Username
              <div className="relative">
                <span className="pointer-events-none absolute left-sp3 top-1/2 -translate-y-1/2 text-t4">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" strokeLinecap="round" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                </span>
                <input
                  className="input pl-[34px] focus:shadow-teal"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus
                  autoComplete="username"
                />
              </div>
            </label>
            <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
              Password
              <div className="relative">
                <span className="pointer-events-none absolute left-sp3 top-1/2 -translate-y-1/2 text-t4">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="4" y="11" width="16" height="9" rx="2" />
                    <path d="M8 11V7a4 4 0 0 1 8 0v4" strokeLinecap="round" />
                  </svg>
                </span>
                <input
                  className="input pl-[34px] pr-[38px] focus:shadow-teal"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-sp3 top-1/2 -translate-y-1/2 text-t4 hover:text-t2"
                >
                  {showPassword ? (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.83 2.83M9.36 5.36A9.7 9.7 0 0 1 12 5c5 0 9 4 10 7-.32.99-1 2.11-2 3.16M6.3 6.53C4.6 7.68 3.3 9.28 2 12c1 3 5 7 10 7 1.5 0 2.9-.36 4.13-.94"
                      />
                    </svg>
                  ) : (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z" strokeLinecap="round" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </label>
            {error && <p className="text-[12px] font-semibold text-red">{error}</p>}
            <button className="btn btn-primary py-sp3" type="submit" disabled={submitting}>
              {submitting ? "Signing in…" : "Sign In →"}
            </button>
          </form>
        </GlassPanel>
      </motion.div>

      <p className="mt-sp5 text-center text-[11.5px] text-t3">
        Research tool, not investment advice · E&amp;O insured
      </p>
      </div>
    </div>
  );
}
