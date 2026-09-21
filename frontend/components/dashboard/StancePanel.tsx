"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { StanceResponse, StanceRow } from "@/lib/types";
import { LeanChip, RiskChip } from "@/components/admin/strategy/shared";

function Row({ r }: { r: StanceRow }) {
  return (
    <li className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp3">
      <div className="flex flex-wrap items-center gap-x-sp3 gap-y-1">
        <span className="text-[14px] font-extrabold text-t1">{r.symbol}</span>
        <span className="text-[11px] text-t3">{r.name}</span>
        <span className="ml-auto flex flex-wrap items-center gap-sp2">
          <span className="text-[9px] font-bold uppercase tracking-wide text-t3">engine</span>
          <LeanChip lean={r.engine.signal} small />
          {r.committee?.action && (
            <>
              <span className="text-[9px] font-bold uppercase tracking-wide text-t3">committee</span>
              <LeanChip lean={r.committee.action} small />
            </>
          )}
          {r.risk && <RiskChip level={r.risk.level} />}
        </span>
      </div>
      <p className="mt-1 text-[12px] leading-snug text-t2">{r.summary}</p>
      {r.committee?.headline && <p className="mt-1 text-[10px] text-t3">Committee ({r.committee.date}): {r.committee.headline}</p>}
    </li>
  );
}

/** What deserves a look today, and nothing else. Everything unremarkable is collapsed into one
 * line: the aim is fewer, better signals, not a wall of tickers all flashing. */
export function StancePanel() {
  const { token } = useAuth();
  const q = useQuery({
    queryKey: ["my-stance"],
    queryFn: () => apiFetch<StanceResponse>("/api/me/stance", { token: token ?? undefined }),
    enabled: !!token,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  if (!token || q.isError) return null;
  if (q.isPending) return <div className="glass-panel p-sp4 text-[12px] text-t3">Reading today&rsquo;s stance…</div>;
  const s = q.data;
  const attention = s.rows.filter((r) => r.attention);
  const watch = s.rows.filter((r) => r.watch);
  const quiet = s.rows.filter((r) => !r.attention && !r.watch);
  return (
    <section className="glass-panel p-sp4" aria-label="Today's stance">
      <div className="flex flex-wrap items-baseline justify-between gap-sp2">
        <h2 className="text-[15px] font-bold text-t1">Today&rsquo;s stance</h2>
        <span className="mono text-[11px] text-t3">{s.as_of ? `as of ${s.as_of} close` : "no data yet"}</span>
      </div>
      <p className="mt-1 text-[12px] text-t2">
        {attention.length ? (
          <>
            <b className="text-t1">{attention.length}</b> worth a look
            {watch.length > 0 && <> · <b className="text-t1">{watch.length}</b> at elevated risk</>} · <b className="text-t1">{quiet.length}</b> quiet — nothing to do.
          </>
        ) : (
          <>Nothing needs your attention today. This is a long-horizon system: most days the right move is no move.</>
        )}
      </p>
      {attention.length > 0 && (
        <ul className="mt-sp3 flex flex-col gap-sp2">
          {attention.map((r) => (
            <Row key={r.symbol} r={r} />
          ))}
        </ul>
      )}
      {watch.length > 0 && (
        <details className="mt-sp3" open={attention.length === 0}>
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wide text-t3">
            {watch.length} at elevated risk — no action suggested
          </summary>
          <ul className="mt-sp2 flex flex-wrap gap-sp2">
            {watch.map((r) => (
              <li key={r.symbol} className="flex items-center gap-sp2 rounded-r1 border border-border bg-bg2/40 px-sp2 py-[2px] text-[11px] text-t2">
                <span className="font-semibold text-t1">{r.symbol}</span>
                {r.risk && <RiskChip level={r.risk.level} score={r.risk.score} />}
              </li>
            ))}
          </ul>
          <p className="mt-sp2 text-[10px] text-t3">Risk is a rule-based read of volatility and drawdown, not a forecast. When markets fall, many symbols rate HIGH together.</p>
        </details>
      )}
      {quiet.length > 0 && (
        <details className="mt-sp3">
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wide text-t3">
            {quiet.length} quiet symbol{quiet.length === 1 ? "" : "s"}
          </summary>
          <p className="mt-sp2 text-[12px] text-t3">{quiet.map((r) => r.symbol).join(" · ")}</p>
        </details>
      )}
      <p className="mt-sp3 text-[10px] text-t3">Simulated research signals from daily closes, not investment advice. Past results do not predict future returns.</p>
    </section>
  );
}
