"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";

// Absolute "/#section" hrefs, not bare "#section" -- this nav also renders
// on /login and /signup (see app/login/page.tsx, app/signup/page.tsx), and
// a bare hash href only ever scrolls within the CURRENT page. From those
// pages a bare "#how-it-works" just appends the hash to /login with
// nothing there to scroll to. "/#how-it-works" + next/link's Link (not a
// plain <a>) navigates to the homepage first when needed, then scrolls --
// and still does an in-page scroll with no full reload when already on it.
const links = [
  { href: "/#how-it-works", label: "How it Works" },
  { href: "/#strategy-lenses", label: "Strategy Lenses" },
  { href: "/#for-advisors", label: "For Advisors" },
  { href: "/#pricing", label: "Pricing" },
  { href: "/#blog", label: "Blog" },
];

export function MarketingNav() {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    // hrefs are "/#id" -- strip the leading "/#" (2 chars), not just "#".
    const ids = links.map((l) => l.href.slice(2));
    const sections = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) {
          setActive(`/#${visible[0].target.id}`);
        }
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 }
    );

    sections.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <nav className="glass-nav sticky top-0 z-50 flex items-center gap-sp6 px-sp6 py-sp3 md:px-sp10">
      <Link href="/" className="flex items-center gap-sp2">
        {/* Overlay accents on top of the flattened logo-mark.png: "porthole"
            crops of the SAME image (see .logo-porthole in globals.css) sit
            exactly over the AAPL/NVDA/MSFT/TSLA fish, the rod, and the
            octopus tentacles and wiggle in place -- there's no separated
            layer art, so this fakes per-element motion without any seam
            since each porthole matches the base image pixel-for-pixel at
            rest. Dollar-sign particles are positioned on the $ marks
            already painted next to each fish. Coordinates are eyeballed
            percentages of the source art -- nudge if misaligned. */}
        <div className="relative h-[150px] w-[150px] shrink-0 overflow-hidden rounded-r1">
          {/* eslint-disable-next-line @next/next/no-img-element -- fixed
              static brand asset (public/logo-mark.png), not user content;
              plain <img> avoids next/image's layout-shift reservation for
              a 150px nav mark. */}
          <img
            src="/logo-mark.png"
            alt="GlassBox"
            className="h-full w-full object-cover"
          />

          {/* Water flowing left-to-right underneath everything else -- a
              horizontal band of the same image, tiled and scrolled. Sits
              behind the fish (rendered first, so later elements paint on
              top) so the fish appear to float on top of moving water
              rather than sliding sideways with it. Band is 60-68%: the
              narrow strip of plain wave crest between the fish row and
              the "GlassBox / See the data..." wordmark starting at ~71%
              -- it must stay clear of that text, which is what was
              blurring/appearing to move before. */}
          <span
            aria-hidden
            className="logo-water"
            style={{ left: 0, top: "60%", width: "100%", height: "8%", backgroundPositionY: "-90px" }}
          />

          {/* AAPL -- the one actually being caught: floats, then gets
              hooked and pulled up on the same story clock as the rod.
              backgroundPosition = -(left% * 150px), -(top% * 150px): each
              porthole's background must be offset by its own position so
              the crop it shows lines up with the base image underneath. */}
          <span
            aria-hidden
            className="logo-porthole logo-fish-catch"
            style={{ left: "56%", top: "19%", width: "19%", height: "18%", backgroundPosition: "-84px -28.5px", transformOrigin: "50% 100%" }}
          />
          {/* NVDA / MSFT / TSLA -- just ambient water motion, unsynced */}
          <span aria-hidden className="logo-porthole logo-fish-b" style={{ left: "13%", top: "47%", width: "16%", height: "14%", backgroundPosition: "-19.5px -70.5px", animationDelay: "0.3s" }} />
          <span aria-hidden className="logo-porthole logo-fish-a" style={{ left: "40%", top: "53%", width: "16%", height: "14%", backgroundPosition: "-60px -79.5px", animationDelay: "0.7s" }} />
          <span aria-hidden className="logo-porthole logo-fish-b" style={{ left: "73%", top: "55%", width: "16%", height: "14%", backgroundPosition: "-109.5px -82.5px", animationDelay: "1.1s" }} />

          {/* Fishing rod -- pivots near the character's hands, dips to
              hook AAPL on the same 8s story clock */}
          <span
            aria-hidden
            className="logo-porthole logo-rod"
            style={{ left: "40%", top: "5%", width: "28%", height: "32%", backgroundPosition: "-60px -7.5px", transformOrigin: "18% 88%" }}
          />

          {/* Just the nearest tentacle (not the whole octopus body/head)
              reaches toward the catch, same clock; the rest of the octopus
              stays put in the static base image. */}
          <span
            aria-hidden
            className="logo-porthole logo-tentacles"
            style={{ left: "60%", top: "26%", width: "20%", height: "18%", backgroundPosition: "-90px -39px", transformOrigin: "85% 85%" }}
          />
          <span aria-hidden className="logo-risk-glow" style={{ top: "22%", right: "4%", width: "44%", height: "44%" }} />

          {/* Ambient $ sparkle on the wave fish; AAPL's own $ only fires
              at the moment it's actually hooked (logo-dollar-catch). */}
          <span aria-hidden className="logo-dollar-catch" style={{ left: "70%", top: "16%", fontSize: 11 }}>$</span>
          <span aria-hidden className="logo-dollar" style={{ left: "22%", top: "44%", fontSize: 10, animationDuration: "2.6s", animationDelay: "0.5s" }}>$</span>
          <span aria-hidden className="logo-dollar" style={{ left: "52%", top: "50%", fontSize: 10, animationDuration: "3.2s", animationDelay: "1s" }}>$</span>
          <span aria-hidden className="logo-dollar" style={{ left: "83%", top: "52%", fontSize: 10, animationDuration: "2.8s", animationDelay: "1.5s" }}>$</span>
        </div>
        <span className="text-[15px] font-extrabold tracking-tight text-t1">
          Glass<span className="text-teal">Box</span>
        </span>
      </Link>

      <div className="hidden items-center gap-sp5 md:flex">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`relative text-[13px] font-medium transition-colors ${
              active === l.href ? "text-teal" : "text-t2 hover:text-t1"
            }`}
          >
            {l.label}
            <span
              className={`absolute -bottom-1 left-0 h-[2px] w-full origin-left rounded-full bg-teal transition-transform duration-200 ease-glass ${
                active === l.href ? "scale-x-100" : "scale-x-0"
              }`}
            />
          </Link>
        ))}
      </div>

      <div className="flex-1" />

      <div className="hidden items-center gap-sp2 rounded-r4 border border-teal/20 px-sp3 py-1 text-[11px] font-semibold text-teal sm:flex">
        <span className="live-dot" />
        Accuracy this week: 99.2%
      </div>

      <ThemeToggle />

      <Link href="/login" className="btn btn-ghost">
        Sign In
      </Link>
      <Link href="/login" className="btn btn-primary">
        Try Free · No card
      </Link>
    </nav>
  );
}
