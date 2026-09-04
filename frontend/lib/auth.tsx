"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiFetch } from "./api";
import type { Role } from "./types";

const STORAGE_KEY = "glassbox_auth";

type AuthState = { token: string | null; role: Role | null };

type AuthContextValue = AuthState & {
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  signup: (username: string, password: string) => Promise<void>;
  /** Stores a token already minted server-side (Google OAuth callback) --
   * no API call, unlike login/signup. See app/oauth/complete/page.tsx. */
  completeOAuth: (token: string, role: Role) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ token: null, role: null });
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
    const next: AuthState = { token: res.access_token, role: res.role };
    setState(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // storage unavailable, session-only auth still works
    }
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
    const next: AuthState = { token, role };
    setState(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // storage unavailable, session-only auth still works
    }
  }, []);

  const logout = useCallback(() => {
    setState({ token: null, role: null });
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
