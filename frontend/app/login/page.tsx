"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import { useAuth } from "@/lib/auth";
import { GlassPanel } from "@/components/GlassPanel";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
    <div className="mx-auto flex min-h-screen max-w-[400px] flex-col justify-center px-sp5 py-sp10">
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
          <form onSubmit={onSubmit} className="flex flex-col gap-sp4">
            <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
              Username
              <input
                className="input focus:shadow-teal"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
              />
            </label>
            <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
              Password
              <input
                className="input focus:shadow-teal"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
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
  );
}
