"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Sends one anonymous page-view ping per page. No cookies, no local storage, no third party: the server
 * never stores the IP (see backend/app/analytics.py). Skipped for admins (so your own clicks don't inflate
 * traffic) and whenever the browser sends Do-Not-Track. Failures are ignored: analytics must never affect a visitor. */
export function PageViewBeacon() {
  const pathname = usePathname();
  const { role, loading } = useAuth();
  const last = useRef<string | null>(null);

  useEffect(() => {
    if (loading || role === "admin" || !pathname || last.current === pathname) return;
    if (typeof navigator !== "undefined" && (navigator.doNotTrack === "1" || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl)) return;
    last.current = pathname;
    try {
      const q = new URLSearchParams(window.location.search);
      fetch(apiUrl("/api/analytics/hit"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: pathname,
          referrer: document.referrer || "",
          utm_source: q.get("utm_source") ?? "",
          utm_medium: q.get("utm_medium") ?? "",
          utm_campaign: q.get("utm_campaign") ?? "",
        }),
        keepalive: true,
        credentials: "omit",
      }).catch(() => {});
    } catch {
      /* never let analytics break the page */
    }
  }, [pathname, role, loading]);

  return null;
}
