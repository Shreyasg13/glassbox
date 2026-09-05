"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GuideBubble } from "./GuideBubble";
import { GUIDE_DASHBOARD_WELCOME, DASHBOARD_WELCOME_SEEN_KEY } from "@/lib/glassboxGuide";

/**
 * Replaces the old 4-slide WelcomeTour (Welcome to GlassBox / Dashboard /
 * My Agents / Reports) with ONE small, dismissible, one-time note --
 * per the product decision that the real onboarding wizard (Concern ->
 * Portfolio -> Verify -> Alerts, all now introduced by GlassBox Guide)
 * is the actual walkthrough, and a second full tour of the same ground
 * right after it would be redundant, competing onboarding. Shows
 * whether the user came through the real wizard or chose "explore with
 * sample data" from /choose -- either way lands on /dashboard, and
 * either way deserves this one short orientation, just not a second
 * multi-step tour.
 *
 * Gated by its own localStorage flag (DASHBOARD_WELCOME_SEEN_KEY), not
 * ONBOARDING_COMPLETE_KEY -- a sample-data visitor who skips the real
 * wizard entirely still gets this one note exactly once.
 */
export function DashboardWelcomeNote() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(DASHBOARD_WELCOME_SEEN_KEY) !== "1") setVisible(true);
    } catch {
      // storage unavailable -- default to not showing
    }
  }, []);

  function dismiss() {
    setVisible(false);
    try {
      localStorage.setItem(DASHBOARD_WELCOME_SEEN_KEY, "1");
    } catch {
      // best-effort
    }
  }

  if (!visible) return null;

  return (
    <div className="glass-panel-accent mb-sp5 flex items-start justify-between gap-sp4 rounded-r3 border border-teal/20 p-sp4">
      <GuideBubble message={GUIDE_DASHBOARD_WELCOME} compact />
      <div className="flex shrink-0 items-center gap-sp3">
        <Link href="/agents" onClick={dismiss} className="whitespace-nowrap text-[12px] font-semibold text-teal hover:underline">
          My Agents →
        </Link>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss"
          className="text-[13px] text-t3 hover:text-t1"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
