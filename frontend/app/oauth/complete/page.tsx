"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { postLoginRedirect } from "@/lib/glassboxGuide";
import type { Role } from "@/lib/types";

/**
 * Landing point for the Google OAuth redirect (backend/app/routers/oauth.py's
 * /auth/oauth/google/callback sends the browser here). The token/role are
 * in the URL fragment, not a query string, specifically so they're never
 * sent to any server on the next request and never show up in access
 * logs -- read them client-side and hand off to the same auth state
 * login()/signup() already populate.
 */
export default function OAuthCompletePage() {
  const { completeOAuth } = useAuth();
  const router = useRouter();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = hash.get("token");
    const role = hash.get("role") as Role | null;

    if (token && (role === "admin" || role === "viewer")) {
      completeOAuth(token, role);
      // Clear the fragment from history so a back-navigation or a copied
      // URL never re-exposes the token.
      window.history.replaceState(null, "", "/oauth/complete");
      router.replace(postLoginRedirect());
    } else {
      router.replace("/login?oauth_error=1");
    }
  }, [completeOAuth, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-[13px] text-t3">Signing you in…</p>
    </div>
  );
}
