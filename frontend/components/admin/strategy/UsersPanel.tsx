"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch, apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CommitteePortfolio, type PortfolioView } from "@/components/portfolio/CommitteePortfolio";

type UserRow = { username: string; archetype: string | null; risk_level: string | null; tickers: string[]; final: number; profit: number; return: number | null };
type Aggregate = {
  users: number;
  live_days: number;
  reviews: number;
  scored_reviews: number;
  note: string;
  pooled: {
    committee_added_dollars: number;
    mean_committee_edge_5d: number | null;
    mean_engine_edge_5d: number | null;
    committee_hit_rate_5d: number | null;
    engine_hit_rate_5d: number | null;
    disagreement_rate: number | null;
  };
  per_user: {
    username: string;
    archetype: string | null;
    committee_return: number | null;
    engine_return: number | null;
    benchmark_return: number | null;
    committee_live_return: number | null;
    committee_added_dollars: number;
    reviews: number;
    disagreements: number;
  }[];
};

const pct = (v: number | null | undefined, d = 1) => (v == null ? "n/a" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);
const usd = (v: number) => `${v >= 0 ? "+" : "-"}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const tone = (v: number | null | undefined) => (v == null || v === 0 ? "text-t2" : v > 0 ? "text-teal" : "text-red");

/** Admin: pick any user and see their committee-run portfolio (growth, Monte Carlo, per-stock reasons,
 * agent record), plus the cohort roll-up and the validation/inference dataset behind it. */
export function UsersPanel() {
  const { token } = useAuth();
  const opts = { token: token ?? undefined };
  const [picked, setPicked] = useState<string | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);

  const users = useQuery({ queryKey: ["admin-portfolio-users"], queryFn: () => apiFetch<{ users: UserRow[] }>("/api/admin/strategy/users", opts), enabled: !!token, retry: false });
  const agg = useQuery({ queryKey: ["admin-portfolio-aggregate"], queryFn: () => apiFetch<Aggregate>("/api/admin/strategy/aggregate", opts), enabled: !!token, retry: false, staleTime: 60_000 });
  const selected = picked ?? users.data?.users[0]?.username ?? null;
  const one = useQuery({
    queryKey: ["admin-user-portfolio", selected],
    queryFn: () => apiFetch<PortfolioView>(`/api/admin/strategy/user-portfolio/${encodeURIComponent(selected!)}`, opts),
    enabled: !!token && !!selected,
    retry: false,
    staleTime: 60_000,
  });

  async function download() {
    setDlError(null);
    try {
      const res = await fetch(apiUrl("/api/admin/strategy/validation-dataset?format=csv"), { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      const a = Object.assign(document.createElement("a"), { href: url, download: "glassbox-validation-dataset.csv" });
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setDlError(e instanceof Error ? e.message : "Download failed");
    }
  }

  const a = agg.data;
  return (
    <div className="flex flex-col gap-sp5">
      <section className="glass-panel p-sp4" aria-label="All users">
        <div className="flex flex-wrap items-baseline justify-between gap-sp2">
          <h2 className="text-[15px] font-bold text-t1">All users: is the committee helping?</h2>
          <button type="button" onClick={download} className="rounded-r1 border border-border px-sp3 py-sp1 text-[11px] font-semibold text-t2 hover:bg-bg3">
            Download validation dataset (CSV)
          </button>
        </div>
        {dlError && <p className="mt-1 text-[11px] text-red">{dlError}</p>}
        {agg.isPending && <p className="mt-sp2 text-[12px] text-t3">Loading…</p>}
        {agg.isError && <p className="mt-sp2 text-[12px] text-t3">{agg.error instanceof ApiError ? agg.error.message : "Could not load the roll-up."}</p>}
        {a && (
          <>
            <div className="mt-sp3 grid grid-cols-2 gap-sp3 lg:grid-cols-5">
              {[
                ["Users", String(a.users)],
                ["Live days", String(a.live_days)],
                ["Reviews / scored", `${a.reviews} / ${a.scored_reviews}`],
                ["Committee hit rate (5d)", pct(a.pooled.committee_hit_rate_5d, 0)],
                ["Engine hit rate (5d)", pct(a.pooled.engine_hit_rate_5d, 0)],
              ].map(([k, val]) => (
                <div key={k} className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp2">
                  <div className="text-[9.5px] font-bold uppercase tracking-wider text-t3">{k}</div>
                  <div className="mono text-[16px] font-extrabold text-t1">{val.replace("+", "")}</div>
                </div>
              ))}
            </div>
            <p className="mt-sp2 text-[11px] leading-snug text-t3">
              Committee added across all users: <b className={tone(a.pooled.committee_added_dollars)}>{usd(a.pooled.committee_added_dollars)}</b> · mean 5-day edge committee {pct(a.pooled.mean_committee_edge_5d, 2)} vs engine {pct(a.pooled.mean_engine_edge_5d, 2)} · disagrees with the engine on {pct(a.pooled.disagreement_rate, 0).replace("+", "")} of reviews. {a.note}
            </p>
            <div className="mt-sp3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[12px]">
                <thead className="text-[10px] uppercase tracking-wide text-t3">
                  <tr><th className="py-1 pr-sp3">User</th><th className="pr-sp3">Type</th><th className="pr-sp3">Committee-run</th><th className="pr-sp3">Engine only</th><th className="pr-sp3">Plan</th><th className="pr-sp3">Committee added</th><th>Overruled engine</th></tr>
                </thead>
                <tbody>
                  {a.per_user.map((u) => (
                    <tr key={u.username} className="cursor-pointer border-t border-white/[0.04] hover:bg-bg3/40" onClick={() => setPicked(u.username)}>
                      <td className="py-1.5 pr-sp3 font-semibold text-t1">{u.username}</td>
                      <td className="pr-sp3 text-t3">{u.archetype ?? "–"}</td>
                      <td className={`mono pr-sp3 ${tone(u.committee_return)}`}>{pct(u.committee_return)}</td>
                      <td className={`mono pr-sp3 ${tone(u.engine_return)}`}>{pct(u.engine_return)}</td>
                      <td className={`mono pr-sp3 ${tone(u.benchmark_return)}`}>{pct(u.benchmark_return)}</td>
                      <td className={`mono pr-sp3 ${tone(u.committee_added_dollars)}`}>{usd(u.committee_added_dollars)}</td>
                      <td className="mono text-t2">{u.disagreements}/{u.reviews}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section className="glass-panel p-sp4" aria-label="One user">
        <div className="mb-sp3 flex flex-wrap items-center gap-sp3">
          <label htmlFor="pick-user" className="text-[12px] font-bold text-t1">Inspect user</label>
          <select id="pick-user" value={selected ?? ""} onChange={(e) => setPicked(e.target.value)} className="rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[13px] text-t1">
            {users.data?.users.map((u) => (
              <option key={u.username} value={u.username}>
                {u.username}{u.archetype ? ` · ${u.archetype}` : ""}
              </option>
            ))}
          </select>
          {users.data && users.data.users.length === 0 && <span className="text-[12px] text-t3">No committee-run accounts yet: the next daily paper cycle creates them.</span>}
        </div>
        {one.isPending && selected && <p className="text-[12px] text-t3">Loading…</p>}
        {one.isError && <p className="text-[12px] text-t3">{one.error instanceof ApiError ? one.error.message : "Could not load this user."}</p>}
        {one.data && <CommitteePortfolio v={one.data} />}
      </section>
    </div>
  );
}
