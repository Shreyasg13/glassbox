"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import { useAuth } from "@/lib/auth";
import { GlassPanel } from "@/components/GlassPanel";
import { MarketingNav } from "@/components/marketing/MarketingNav";
import { SocialSignIn } from "@/components/auth/SocialSignIn";
import { PasswordField } from "@/components/auth/PasswordField";
import { postLoginRedirect } from "@/lib/glassboxGuide";

export default function SignupPage() {
  const { signup } = useAuth();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords don't match");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await signup(username, password);
      router.push(postLoginRedirect());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
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
            <h2 className="mb-sp5 text-[15px] font-bold text-t1">Create your account</h2>

            <SocialSignIn />

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
                    minLength={3}
                  />
                </div>
                <span className="text-[10.5px] font-normal text-t4">At least 3 characters</span>
              </label>
              <PasswordField label="Password" value={password} onChange={setPassword} autoComplete="new-password" />
              <PasswordField
                label="Confirm password"
                value={confirmPassword}
                onChange={setConfirmPassword}
                autoComplete="new-password"
              />
              {error && <p className="text-[12px] font-semibold text-red">{error}</p>}
              <button className="btn btn-primary py-sp3" type="submit" disabled={submitting}>
                {submitting ? "Creating account…" : "Create Account →"}
              </button>
            </form>

            <p className="mt-sp4 text-center text-[12px] text-t3">
              Already have an account?{" "}
              <Link href="/login" className="font-semibold text-teal hover:underline">
                Sign in
              </Link>
            </p>
          </GlassPanel>
        </motion.div>

        <p className="mt-sp5 text-center text-[11.5px] text-t3">
          Research tool, not investment advice · E&amp;O insured
        </p>
      </div>
    </div>
  );
}
