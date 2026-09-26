"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Snapshot, SnapshotDetail } from "@/lib/types";

const SOURCE_LABEL: Record<string, string> = {
  sec_facts: "SEC Fundamentals",
  sec_filings: "SEC Filings",
  sec_insiders: "SEC Insiders",
  treasury: "Treasury",
  bls: "BLS",
  prices: "Prices",
};

function shortHash(h: string) {
  return h.slice(0, 12) + "…";
}

function fmtDate(iso: string) {
  return iso.slice(0, 19).replace("T", " ");
}

export function SnapshotsPanel() {
  const { token } = useAuth();
  const [sourceFilter, setSourceFilter] = useState("");
  const [tickerFilter, setTickerFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SnapshotDetail | null>(null);

  const q = useQuery({
    queryKey: ["admin-snapshots", sourceFilter, tickerFilter],
    queryFn: () =>
      apiFetch<Snapshot[]>(
        `/api/admin/snapshots?${new URLSearchParams({ source: sourceFilter, ticker: tickerFilter, limit: "100" })}`,
        { token: token ?? undefined }
      ),
    enabled: !!token,
    refetchInterval: 30_000,
    retry: false,
  });

  async function loadDetail(id: string) {
    setSelectedId(id);
    try {
      const d = await apiFetch<SnapshotDetail>(`/api/admin/snapshots/${id}`, { token: token ?? undefined });
      setDetail(d);
    } catch (e) {
      setDetail(null);
    }
  }

  function closeDetail() {
    setSelectedId(null);
    setDetail(null);
  }

  const sources = [...new Set(q.data?.map((s) => s.source) ?? [])].sort();
  const tickers = [...new Set(q.data?.map((s) => s.ticker).filter(Boolean) ?? [])].sort();

  return (
    <div className="flex flex-col gap-sp5">
      <section className="glass-panel p-sp4">
        <h2 className="text-[15px] font-bold text-t1">Point-in-time fetch snapshots</h2>
        <p className="mt-1 text-[11px] text-t3">
          Every external data fetch is recorded here with its <code className="mono">fetched_at</code> timestamp. The committee reads
          only snapshots with <code className="mono">fetched_at ≤ run_time</code>, so it can never see data that arrived after the run started.
        </p>

        <div className="mt-sp3 flex flex-wrap gap-sp2">
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded-r1 border border-border bg-bg2 px-sp2 py-sp1 text-[11px] text-t1"
            aria-label="Filter by source"
          >
            <option value="">All sources</option>
            {sources.map((s) => (
              <option key={s} value={s}>
                {SOURCE_LABEL[s] ?? s}
              </option>
            ))}
          </select>
          <select
            value={tickerFilter}
            onChange={(e) => setTickerFilter(e.target.value)}
            className="rounded-r1 border border-border bg-bg2 px-sp2 py-sp1 text-[11px] text-t1"
            aria-label="Filter by ticker"
          >
            <option value="">All tickers</option>
            {tickers.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        {q.isPending && <p className="mt-sp2 text-[12px] text-t3">Loading…</p>}
        {q.isError && <p className="mt-sp2 text-[12px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load snapshots."}</p>}

        {q.data && (
          <div className="mt-sp3 overflow-x-auto">
            <table className="w-full text-left text-[11px]">
              <thead className="text-[9.5px] uppercase tracking-wider text-t3">
                <tr>
                  <th className="py-1 pr-sp3">Source</th>
                  <th className="py-1 pr-sp3">Ticker</th>
                  <th className="py-1 pr-sp3">As of</th>
                  <th className="py-1 pr-sp3">Fetched at</th>
                  <th className="py-1 pr-sp3">Hash</th>
                  <th className="py-1"></th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((s) => (
                  <tr key={s.id} className="border-t border-white/[0.04] hover:bg-bg3">
                    <td className="py-1 pr-sp3 text-t2">{SOURCE_LABEL[s.source] ?? s.source}</td>
                    <td className="py-1 pr-sp3 font-mono text-t1">{s.ticker || "—"}</td>
                    <td className="py-1 pr-sp3 font-mono text-t1">{s.as_of}</td>
                    <td className="py-1 pr-sp3 font-mono text-t1">{fmtDate(s.fetched_at)}</td>
                    <td className="py-1 pr-sp3 font-mono text-t3">{shortHash(s.payload_hash)}</td>
                    <td className="py-1">
                      <button
                        type="button"
                        onClick={() => loadDetail(s.id)}
                        className="rounded-r1 border border-border px-sp2 py-0.5 text-[10px] font-semibold text-t2 hover:bg-bg3"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {q.data.length === 0 && <p className="text-[12px] text-t3 py-sp4 text-center">No snapshots match the filters.</p>}
          </div>
        )}
      </section>

      {detail && (
        <section className="glass-panel p-sp4">
          <div className="flex items-baseline justify-between gap-sp2">
            <h3 className="text-[15px] font-bold text-t1">Snapshot detail</h3>
            <button type="button" onClick={closeDetail} className="rounded-r1 border border-border px-sp2 py-sp1 text-[11px] font-semibold text-t2 hover:bg-bg3">
              Close
            </button>
          </div>
          <div className="mt-sp3 grid gap-sp2 lg:grid-cols-2 text-[11px]">
            <div><span className="text-t3">ID</span> <div className="mono text-t1">{detail.id}</div></div>
            <div><span className="text-t3">Source</span> <div className="text-t1">{SOURCE_LABEL[detail.source] ?? detail.source}</div></div>
            <div><span className="text-t3">Ticker</span> <div className="mono text-t1">{detail.ticker || "—"}</div></div>
            <div><span className="text-t3">As of</span> <div className="mono text-t1">{detail.as_of}</div></div>
            <div><span className="text-t3">Fetched at</span> <div className="mono text-t1">{fmtDate(detail.fetched_at)}</div></div>
            <div><span className="text-t3">Payload hash</span> <div className="mono text-t1">{detail.payload_hash}</div></div>
          </div>
          <div className="mt-sp3">
            <div className="text-[10px] uppercase tracking-wider text-t3 mb-1">Payload (JSON)</div>
            <pre className="rounded-r2 border border-border bg-bg2/40 p-sp3 text-[10px] overflow-auto max-h-[400px] text-t1">
              {JSON.stringify(detail.payload, null, 2)}
            </pre>
          </div>
        </section>
      )}
    </div>
  );
}