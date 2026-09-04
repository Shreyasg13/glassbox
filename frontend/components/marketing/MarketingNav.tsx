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
        <div className="grid h-[26px] w-[26px] place-items-center rounded-r1 bg-gradient-to-br from-teal to-blue text-[10px] font-extrabold text-bg">
          GB
        </div>
        <span className="text-[14px] font-bold tracking-tight text-t2">
          glass<span className="text-teal">box</span>
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
