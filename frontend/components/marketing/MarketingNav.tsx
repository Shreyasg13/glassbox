"use client";

import Link from "next/link";

const links = [
  { href: "#how-it-works", label: "How it Works" },
  { href: "#for-advisors", label: "For Advisors" },
  { href: "#pricing", label: "Pricing" },
  { href: "#blog", label: "Blog" },
];

export function MarketingNav() {
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
          <a
            key={l.href}
            href={l.href}
            className="text-[13px] font-medium text-t2 transition-colors hover:text-t1"
          >
            {l.label}
          </a>
        ))}
      </div>

      <div className="flex-1" />

      <div className="hidden items-center gap-sp2 rounded-r4 border border-teal/20 px-sp3 py-1 text-[11px] font-semibold text-teal sm:flex">
        <span className="live-dot" />
        Accuracy this week: 99.2%
      </div>

      <Link href="/login" className="btn btn-ghost">
        Sign In
      </Link>
      <Link href="/login" className="btn btn-primary">
        Try Free — No card
      </Link>
    </nav>
  );
}
