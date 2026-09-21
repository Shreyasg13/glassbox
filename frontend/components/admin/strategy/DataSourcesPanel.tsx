"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DataSources } from "@/lib/types";
import { Section, Th, pct, plainPct } from "./shared";

const LABELS: Record<string, string> = { sec: "SEC EDGAR filings", treasury: "US Treasury yield curve", bls_unemployment: "BLS unemployment", bls_cpi: "BLS consumer prices" };
const num = (n: number | null | undefined, d = 1) => (n === null || n === undefined ? "—" : n.toFixed(d));

/** The free public data feeding the committee: which sources are live, and what they say per stock. */
export function DataSourcesPanel() {
  const { token } = useAuth();
  const q = useQuery({
    queryKey: ["strategy-data-sources"],
    queryFn: () => apiFetch<DataSources>("/api/admin/strategy/data-sources", { token: token ?? undefined }),
    enabled: !!token,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
  if (q.isPending) return null;
  if (q.isError) return <p className="text-[12px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load the data sources"}</p>;
  const d = q.data;
  const keys = ["sec", "treasury", "bls_unemployment", "bls_cpi"];
  const withData = d.rows.filter((r) => r.fundamentals || r.events.length);

  return (
    <Section
      title="Free public data feeding the committee"
      note="All free and commercially usable: SEC filings (fundamentals and 8-K events) and US Treasury / BLS macro. Refreshed daily before the committee runs; every figure is as of the filing date, never later."
    >
      <div className="flex flex-wrap gap-sp2">
        {keys.map((k) => {
          const s = d.status[k];
          return (
            <div key={k} className={`rounded-r2 border px-sp3 py-sp2 ${s?.ok ? "border-teal/40 bg-teal-dim/40" : "border-gold/40 bg-gold-dim/40"}`} title={s?.detail}>
              <div className="text-[11px] font-bold text-t1">{LABELS[k]}</div>
              <div className={`text-[10px] ${s?.ok ? "text-teal" : "text-gold"}`}>{s ? (s.ok ? `live · ${s.detail}` : `off · ${s.detail}`) : "not run yet"}</div>
            </div>
          );
        })}
      </div>
      {!d.sec_configured && (
        <p className="mt-sp2 text-[11px] text-gold">
          SEC data is off: set <span className="mono">SEC_USER_AGENT</span> (your project name and a contact email, required by the SEC) on the server, then run the refresh job.
        </p>
      )}
      {d.macro_line && <p className="mt-sp3 text-[12px] leading-snug text-t2">{d.macro_line}</p>}

      {withData.length > 0 && (
        <div className="mt-sp3 overflow-x-auto">
          <table className="w-full min-w-[720px] text-[12px]">
            <thead>
              <tr>
                <Th>Symbol</Th>
                <Th right>Revenue YoY</Th>
                <Th right>Net margin</Th>
                <Th right>ROE</Th>
                <Th right>P/E</Th>
                <Th>Latest filing</Th>
              </tr>
            </thead>
            <tbody>
              {withData.map((r) => (
                <tr key={r.symbol} className="border-t border-border">
                  <td className="px-sp3 py-sp2 font-semibold text-t1">{r.symbol}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t2">{r.fundamentals?.revenue_growth === undefined ? "—" : pct(r.fundamentals.revenue_growth)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t2">{r.fundamentals?.net_margin === undefined ? "—" : plainPct(r.fundamentals.net_margin, 1)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t2">{r.fundamentals?.roe === undefined ? "—" : plainPct(r.fundamentals.roe)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t2">{num(r.fundamentals?.pe)}</td>
                  <td className="px-sp3 py-sp2 text-t3">
                    {r.events[0] ? (
                      <span className={r.events[0].flag ? "text-gold" : ""}>
                        {r.events[0].form} {r.events[0].filed} — {r.events[0].text}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {withData.length === 0 && <p className="mt-sp3 text-[12px] text-t3">No company data cached yet. Funds (SPY, QQQ, GLD, TLT, IWM) have no company filings by design.</p>}
    </Section>
  );
}
