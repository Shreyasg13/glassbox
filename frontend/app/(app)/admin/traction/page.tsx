"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Summary = {
  days: number;
  as_of: string;
  live_now: number;
  today: { visitors: number; pageviews: number };
  totals: { visitor_days: number; pageviews: number; signups: number; signup_rate: number | null };
  series: { day: string; visitors: number; pageviews: number; signups: number }[];
  pages: { path: string; visitors: number; pageviews: number }[];
  sources: { source: string; visitors: number }[];
  campaigns: { source: string; medium: string; campaign: string; visitors: number }[];
  devices: { device: string; visitors: number }[];
  funnel: { step: string; visitors: number }[];
  note: string;
};
type Repo = { stargazers_count: number; forks_count: number; subscribers_count: number; open_issues_count: number; pushed_at: string; html_url: string };

const REPO = "Shreyasg13/glassbox-trading-agents";
const RANGES = [7, 30, 90] as const;
const PLATFORMS = ["linkedin", "x", "hackernews", "reddit", "devto", "youtube", "newsletter", "other"] as const;

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp3">
      <div className="text-[9.5px] font-bold uppercase tracking-wider text-t3">{label}</div>
      <div className="mono mt-1 text-[20px] font-extrabold text-t1">{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-t3">{sub}</div>}
    </div>
  );
}

function Bars({ rows, unit = "visitors" }: { rows: { label: string; value: number }[]; unit?: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (!rows.length) return <p className="text-[12px] text-t3">Nothing yet.</p>;
  return (
    <ul className="flex flex-col gap-1.5">
      {rows.map((r) => (
        <li key={r.label} className="text-[12px]">
          <div className="flex justify-between gap-sp2">
            <span className="min-w-0 truncate text-t1">{r.label}</span>
            <span className="mono shrink-0 text-t2">{r.value.toLocaleString()} {unit}</span>
          </div>
          <div className="mt-0.5 h-1.5 rounded-full bg-bg3"><div className="h-1.5 rounded-full bg-teal" style={{ width: `${(r.value / max) * 100}%` }} /></div>
        </li>
      ))}
    </ul>
  );
}

function DailyChart({ s }: { s: Summary }) {
  const W = 640, H = 160, PAD = 14;
  const max = Math.max(1, ...s.series.map((d) => d.visitors));
  const bw = (W - 2 * PAD) / s.series.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Visitors per day for the last ${s.days} days`}>
      {s.series.map((d, i) => {
        const h = (d.visitors / max) * (H - 2 * PAD - 12);
        return (
          <g key={d.day}>
            <rect x={PAD + i * bw + 1} y={H - PAD - h} width={Math.max(1, bw - 2)} height={h} rx="1.5" className="fill-teal">
              <title>{`${d.day}: ${d.visitors} visitors, ${d.pageviews} page views, ${d.signups} sign-ups`}</title>
            </rect>
            {d.signups > 0 && <circle cx={PAD + i * bw + bw / 2} cy={H - PAD - h - 5} r="3" className="fill-gold" />}
          </g>
        );
      })}
      <text x={PAD} y={H - 2} className="fill-t3" fontSize="9">{s.series[0]?.day}</text>
      <text x={W - PAD} y={H - 2} textAnchor="end" className="fill-t3" fontSize="9">{s.series[s.series.length - 1]?.day}</text>
      <text x={W - PAD} y={10} textAnchor="end" className="fill-t3" fontSize="9">peak {max}</text>
    </svg>
  );
}

function GithubPanel() {
  const q = useQuery({
    queryKey: ["gh-repo"],
    queryFn: async () => {
      const res = await fetch(`https://api.github.com/repos/${REPO}`, { headers: { Accept: "application/vnd.github+json" } });
      if (!res.ok) throw new Error(`GitHub ${res.status}`);
      return (await res.json()) as Repo;
    },
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
  return (
    <section className="glass-panel p-sp4" aria-label="Open-source traction">
      <h2 className="text-[15px] font-bold text-t1">Open-source traction (GitHub)</h2>
      {q.isPending && <p className="mt-sp2 text-[12px] text-t3">Loading…</p>}
      {q.isError && <p className="mt-sp2 text-[12px] text-t3">Couldn&rsquo;t reach GitHub just now.</p>}
      {q.data && (
        <div className="mt-sp3 grid grid-cols-2 gap-sp3 sm:grid-cols-4">
          <Kpi label="Stars" value={q.data.stargazers_count.toLocaleString()} />
          <Kpi label="Forks" value={q.data.forks_count.toLocaleString()} />
          <Kpi label="Watchers" value={q.data.subscribers_count.toLocaleString()} />
          <Kpi label="Open issues + PRs" value={q.data.open_issues_count.toLocaleString()} />
        </div>
      )}
      <p className="mt-sp3 text-[11.5px] leading-snug text-t3">
        Repo page views, clones and where GitHub visitors come from are private to you:{" "}
        <a className="text-teal underline" href={`https://github.com/${REPO}/graph/traffic`} target="_blank" rel="noopener noreferrer">open the repo&rsquo;s Traffic page</a>.
      </p>
    </section>
  );
}

function LinkBuilder() {
  const [platform, setPlatform] = useState<(typeof PLATFORMS)[number]>("linkedin");
  const [campaign, setCampaign] = useState("launch");
  const [copied, setCopied] = useState(false);
  const clean = campaign.trim().toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-|-$/g, "") || "campaign";
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const medium = platform === "newsletter" ? "email" : "social";
  const url = `${origin}/?utm_source=${platform}&utm_medium=${medium}&utm_campaign=${clean}`;
  return (
    <section className="glass-panel p-sp4" aria-label="Tracked link builder">
      <h2 className="text-[15px] font-bold text-t1">Tracked link builder</h2>
      <p className="mt-1 text-[11.5px] text-t3">Use one link per post so you can see which one brought visitors and sign-ups.</p>
      <div className="mt-sp3 flex flex-wrap items-end gap-sp3">
        <label className="flex flex-col gap-1 text-[11px] text-t3">Where you&rsquo;ll post it
          <select value={platform} onChange={(e) => setPlatform(e.target.value as (typeof PLATFORMS)[number])} className="rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[13px] text-t1">
            {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="flex min-w-0 flex-1 flex-col gap-1 text-[11px] text-t3">Campaign name
          <input value={campaign} onChange={(e) => setCampaign(e.target.value)} maxLength={60} className="min-w-0 rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[13px] text-t1" />
        </label>
      </div>
      <div className="mt-sp3 flex flex-wrap items-center gap-sp2">
        <code className="mono min-w-0 flex-1 break-all rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[11.5px] text-t2">{url}</code>
        <button
          type="button"
          onClick={async () => { try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ } }}
          className="rounded-r1 border border-border px-sp3 py-sp2 text-[12px] font-semibold text-t2 hover:bg-bg3"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </section>
  );
}

/** Admin: who is visiting, where they come from, and whether they sign up. */
export default function TractionPage() {
  const { token, role } = useAuth();
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const q = useQuery({
    queryKey: ["admin-traction", days],
    queryFn: () => apiFetch<Summary>(`/api/admin/analytics/summary?days=${days}`, { token: token ?? undefined }),
    enabled: !!token && role === "admin",
    refetchInterval: 60_000,
    retry: false,
  });

  if (role !== "admin") return <p className="py-sp10 text-center text-[13px] text-t3">This page is for administrators.</p>;
  const s = q.data;
  return (
    <div className="flex flex-col gap-sp5">
      <header className="flex flex-wrap items-end justify-between gap-sp3">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight text-t1">Traction</h1>
          <p className="mt-1 max-w-[80ch] text-[12px] text-t3">Who is finding GlassBox, from where, and whether they sign up. Cookie-free, no IP addresses stored.</p>
        </div>
        <div className="flex gap-1" role="group" aria-label="Date range">
          {RANGES.map((r) => (
            <button key={r} type="button" onClick={() => setDays(r)} aria-pressed={days === r} className={`rounded-r1 border px-sp3 py-1 text-[12px] ${days === r ? "border-teal/60 bg-teal-dim text-teal" : "border-border text-t3"}`}>{r} days</button>
          ))}
        </div>
      </header>

      {q.isPending && <p className="text-[12px] text-t3">Loading…</p>}
      {q.isError && <p className="text-[12px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load analytics."}</p>}
      {s && (
        <>
          <div className="grid grid-cols-2 gap-sp3 lg:grid-cols-6">
            <Kpi label="On the site now" value={String(s.live_now)} sub="last 30 min" />
            <Kpi label="Visitors today" value={String(s.today.visitors)} sub={`${s.today.pageviews} page views`} />
            <Kpi label={`Visitors, ${s.days}d`} value={s.totals.visitor_days.toLocaleString()} sub="visitor-days" />
            <Kpi label="Page views" value={s.totals.pageviews.toLocaleString()} />
            <Kpi label="Sign-ups" value={String(s.totals.signups)} />
            <Kpi label="Visit → sign-up" value={s.totals.signup_rate == null ? "n/a" : `${(s.totals.signup_rate * 100).toFixed(1)}%`} />
          </div>

          <section className="glass-panel p-sp4" aria-label="Visitors per day">
            <h2 className="mb-sp2 text-[15px] font-bold text-t1">Visitors per day <span className="text-[11px] font-normal text-t3">(dot = a sign-up that day)</span></h2>
            {s.totals.pageviews === 0 ? <p className="text-[12px] text-t3">No visits recorded yet. Counting started when this feature went live.</p> : <DailyChart s={s} />}
          </section>

          <div className="grid gap-sp5 lg:grid-cols-2">
            <section className="glass-panel p-sp4" aria-label="Where visitors come from">
              <h2 className="mb-sp3 text-[15px] font-bold text-t1">Where they come from</h2>
              <Bars rows={s.sources.map((x) => ({ label: x.source, value: x.visitors }))} />
            </section>
            <section className="glass-panel p-sp4" aria-label="Campaigns">
              <h2 className="mb-sp3 text-[15px] font-bold text-t1">Campaigns (tracked links)</h2>
              <Bars rows={s.campaigns.map((x) => ({ label: `${x.campaign} · ${x.source}${x.medium ? ` / ${x.medium}` : ""}`, value: x.visitors }))} />
              {s.campaigns.length === 0 && <p className="mt-sp2 text-[11px] text-t3">Make a link below, use it in a post, and it shows up here.</p>}
            </section>
            <section className="glass-panel p-sp4" aria-label="Funnel">
              <h2 className="mb-sp3 text-[15px] font-bold text-t1">Funnel</h2>
              <Bars rows={s.funnel.map((x) => ({ label: x.step, value: x.visitors }))} unit="" />
            </section>
            <section className="glass-panel p-sp4" aria-label="Top pages">
              <h2 className="mb-sp3 text-[15px] font-bold text-t1">Top pages</h2>
              <Bars rows={s.pages.map((x) => ({ label: x.path, value: x.visitors }))} />
            </section>
            <section className="glass-panel p-sp4" aria-label="Devices">
              <h2 className="mb-sp3 text-[15px] font-bold text-t1">Devices</h2>
              <Bars rows={s.devices.map((x) => ({ label: x.device, value: x.visitors }))} />
            </section>
            <GithubPanel />
          </div>
          <LinkBuilder />
          <p className="text-[11px] leading-snug text-t3">{s.note}</p>
        </>
      )}
      {!s && <GithubPanel />}
    </div>
  );
}
