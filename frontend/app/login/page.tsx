"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { GlassPanel } from "@/components/GlassPanel";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
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
    <div className="mx-auto max-w-[400px] py-sp10">
      <GlassPanel variant="raised">
        <h1 className="mb-sp5 text-[18px] font-bold text-t1">Admin Sign In</h1>
        <form onSubmit={onSubmit} className="flex flex-col gap-sp4">
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Username
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
            />
          </label>
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Password
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error && <p className="text-[12px] font-semibold text-red">{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </GlassPanel>
    </div>
  );
}
