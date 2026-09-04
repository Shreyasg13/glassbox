"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Role } from "@/lib/types";

const STORAGE_KEY = "glassbox_onboarding_tour_seen";

type Slide = {
  icon: string;
  color: string; // Tailwind color token name, e.g. "teal"
  title: string;
  body: string;
  linkHref?: string;
  linkLabel?: string;
};

const VIEWER_SLIDES: Slide[] = [
  {
    icon: "◈",
    color: "teal",
    title: "Welcome to GlassBox",
    body: "Every risk score here traces back to raw institutional data and an independent audit — no black box. This quick tour covers the four places you'll spend most of your time.",
  },
  {
    icon: "▤",
    color: "gold",
    title: "Dashboard",
    body: "Your portfolio overview, live signals, real agent-performance stats, and a Monte Carlo stress test — all in one place.",
    linkHref: "/dashboard",
    linkLabel: "Take me there",
  },
  {
    icon: "⚗",
    color: "purple",
    title: "My Agents",
    body: "Pick which agents run your reports. Leave everything unchecked to run the full committee — the default.",
    linkHref: "/agents",
    linkLabel: "Take me there",
  },
  {
    icon: "≡",
    color: "green",
    title: "Reports",
    body: "LLM-narrated daily reports, cross-checked by an independent auditor before you ever see them.",
    linkHref: "/reports",
    linkLabel: "Take me there",
  },
];

const ADMIN_SLIDE: Slide = {
  icon: "⟳",
  color: "blue",
  title: "Admin Tools",
  body: "Agent Factory, orchestrations, the report builder, and observability (cost/latency/audit log) all live under Admin in the sidebar.",
  linkHref: "/admin/agents",
  linkLabel: "Take me there",
};

/**
 * First-time-visitor walkthrough -- a plain modal carousel, not an LLM
 * agent. This is deliberately static, hardcoded content (Dashboard/My
 * Agents/Reports/Admin each get one slide) rather than something
 * generated per-view: a walkthrough of this app's own fixed UI has
 * nothing to gain from an LLM call (extra cost and latency for a
 * result that should be identical every time anyway) and something to
 * lose (a model narrating your own product wrong). Shown once per
 * browser via localStorage, same convention useLensVoice.ts already
 * uses for its own persisted preference.
 */
export function WelcomeTour({ role }: { role: Role | null }) {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);

  const slides = role === "admin" ? [...VIEWER_SLIDES, ADMIN_SLIDE] : VIEWER_SLIDES;

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) !== "1") setOpen(true);
    } catch {
      // storage unavailable -- default to not showing rather than risk
      // showing it on every single page load with no way to dismiss it
    }
  }, []);

  function dismiss() {
    setOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // best-effort -- worst case the tour reappears next visit
    }
  }

  if (!open) return null;

  const slide = slides[index];
  const isLast = index === slides.length - 1;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-sp4 backdrop-blur-sm">
      <div className="glass-panel-raised w-full max-w-[380px] rounded-r3 border border-border2 p-sp5 shadow-lg2">
        <div className="mb-sp4 flex items-center justify-between">
          <div
            className="grid h-[38px] w-[38px] place-items-center rounded-r2 text-[18px]"
            style={{ background: `var(--c-${slide.color}-dim)`, color: `var(--c-${slide.color})` }}
          >
            {slide.icon}
          </div>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Skip tour"
            className="text-[12px] font-semibold text-t3 hover:text-t1"
          >
            Skip
          </button>
        </div>

        <h2 className="mb-sp2 text-[16px] font-bold text-t1">{slide.title}</h2>
        <p className="mb-sp5 text-[13px] leading-relaxed text-t2">{slide.body}</p>

        {slide.linkHref && (
          <Link
            href={slide.linkHref}
            onClick={dismiss}
            className="mb-sp4 inline-block text-[12.5px] font-semibold text-teal hover:underline"
          >
            {slide.linkLabel} →
          </Link>
        )}

        <div className="flex items-center justify-between">
          <div className="flex gap-sp1">
            {slides.map((_, i) => (
              <span
                key={i}
                className={`h-[6px] w-[6px] rounded-full ${i === index ? "bg-teal" : "bg-border2"}`}
              />
            ))}
          </div>
          <div className="flex gap-sp2">
            {index > 0 && (
              <button type="button" className="btn btn-ghost text-[12px]" onClick={() => setIndex((i) => i - 1)}>
                Back
              </button>
            )}
            <button
              type="button"
              className="btn btn-primary text-[12px]"
              onClick={() => (isLast ? dismiss() : setIndex((i) => i + 1))}
            >
              {isLast ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
