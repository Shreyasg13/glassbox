"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiFetch } from "./api";
import type { Role } from "./types";

const STORAGE_KEY = "glassbox_auth";

type AuthState = { token: string | null; role: Role | null; username: string | null };

/**
 * Reads the `sub` claim (username) out of a JWT client-side, no
 * verification -- this app never trusts this value for anything
 * security-sensitive (the backend re-validates the token's signature
 * on every request), it's only used to scope per-user UI preferences
 * like onboarding-completion (see lib/glassboxGuide.ts's
 * postLoginRedirect) so two different accounts on the same browser
 * don't share one global "has this browser seen onboarding" flag.
 */
function decodeJwtSub(token: string): string | null {
  try {
    const payload = token.split(".")[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = JSON.parse(atob(base64));
    return typeof json.sub === "string" ? json.sub : null;
  } catch {
    return null;
  }
}

type AuthContextValue = AuthState & {
  loading: boolean;
  // Return the just-decoded username directly (not via this hook's own
  // `username` field) -- React only applies setState on the next
  // render, so a caller reading useAuth().username synchronously right
  // after awaiting login() would still see the stale (often null)
  // value from the render that's currently executing.
  login: (username: string, password: string) => Promise<string | null>;
  signup: (username: string, password: string) => Promise<string | null>;
  /** Stores a token already minted server-side (Google OAuth callback) --
   * no API call, unlike login/signup. See app/oauth/complete/page.tsx. */
  completeOAuth: (token: string, role: Role) => string | null;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ token: null, role: null, username: null });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setState(JSON.parse(raw));
    } catch {
      // ignore malformed/inaccessible storage
    }
    setLoading(false);
  }, []);

  const authenticate = useCallback(async (endpoint: "/auth/login" | "/auth/signup", username: string, password: string) => {
    const res = await apiFetch<{ access_token: string; token_type: string; role: Role }>(endpoint, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    const next: AuthState = { token: res.access_token, role: res.role, username: decodeJwtSub(res.access_token) };
    setState(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // storage unavailable, session-only auth still works
    }
    return next.username;
  }, []);

  const login = useCallback(
    (username: string, password: string) => authenticate("/auth/login", username, password),
    [authenticate]
  );

  const signup = useCallback(
    (username: string, password: string) => authenticate("/auth/signup", username, password),
    [authenticate]
  );

  const completeOAuth = useCallback((token: string, role: Role) => {
    const next: AuthState = { token, role, username: decodeJwtSub(token) };
    setState(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // storage unavailable, session-only auth still works
    }
    return next.username;
  }, []);

  const logout = useCallback(() => {
    setState({ token: null, role: null, username: null });
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, loading, login, signup, completeOAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
