"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LedgerRow, LedgerVerify } from "@/lib/types";

function shortHash(h: string) {
  return h.slice(0, 10) + "…";
}

function fmtDate(iso: string) {
  return iso.slice(0, 19).replace("T", " ");
}

export function LedgerPanel() {
  const { token } = useAuth();
  const [fromSeq, setFromSeq] = useState(1);
  const [limit, setLimit] = useState(100);
  const [verifyResult, setVerifyResult] = useState<LedgerVerify | null>(null);
  const [verifying, setVerifying] = useState(false);

  const q = useQuery({
    queryKey: ["admin-ledger", fromSeq, limit],
    queryFn: () =>
      apiFetch<LedgerRow[]>(
        `/api/admin/ledger?${new URLSearchParams({ from_seq: String(fromSeq), limit: String(limit) })}`,
        { token: token ?? undefined }
      ),
    enabled: !!token,
    refetchInterval: 30_000,
    retry: false,
  });

  async function handleVerify() {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await apiFetch<LedgerVerify>(`/api/admin/ledger/verify`, {
        token: token ?? undefined,
        method: "POST",
      });
      setVerifyResult(res);
    } catch (e) {
      setVerifyResult({ ok: false, rows: 0, first_bad_seq: null, reason: e instanceof ApiError ? e.message : "Verify failed" });
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="flex flex-col gap-sp5">
      <section className="glass-panel p-sp4">
        <h2 className="text-[15px] font-bold text-t1">Call ledger</h2>
        <p className="mt-1 text-[11px] text-t3">
          Append-only, hash-chained record of every committee call. Any edit to any row breaks the chain and is
          reported by <code className="mono">verify()</code>.
        </p>

        <div className="mt-sp3 flex flex-wrap items-end gap-sp2">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-t3 block mb-1">From seq</label>
            <input
              type="number"
              min="1"
              value={fromSeq}
              onChange={(e) => setFromSeq(Math.max(1, parseInt(e.target.value) || 1))}
              className="rounded-r1 border border-border bg-bg2 px-sp2 py-sp1 text-[11px] text-t1 w-[100px]"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-wider text-t3 block mb-1">Limit</label>
            <input
              type="number"
              min="1"
              max="1000"
              value={limit}
              onChange={(e) => setLimit(Math.max(1, Math.min(1000, parseInt(e.target.value) || 100)))}
              className="rounded-r1 border border-border bg-bg2 px-sp2 py-sp1 text-[11px] text-t1 w-[100px]"
            />
          </div>
          <button
            type="button"
            onClick={handleVerify}
            disabled={verifying}
            className="rounded-r1 border border-border px-sp3 py-sp1.5 text-[11px] font-semibold text-t2 hover:bg-bg3 disabled:opacity-50"
          >
            {verifying ? "Verifying…" : "Verify chain"}
          </button>
        </div>

        {verifyResult && (
          <div
            className={`mt-sp3 p-sp3 rounded-r2 text-[12px] ${
              verifyResult.ok ? "bg-teal-dim border border-teal/40 text-teal" : "bg-red-dim border border-red/40 text-red"
            }`}
            role="alert"
          >
            <b>{verifyResult.ok ? "Chain OK" : "Chain BROKEN"}</b> — {verifyResult.reason}
            {verifyResult.first_bad_seq && (
              <span className="ml-2 mono">first bad seq: {verifyResult.first_bad_seq}</span>
            )}
            <span className="ml-2 mono">rows checked: {verifyResult.rows}</span>
          </div>
        )}

        {q.isPending && <p className="mt-sp2 text-[12px] text-t3">Loading…</p>}
        {q.isError && (
          <p className="mt-sp2 text-[12px] text-red">
            {q.error instanceof ApiError ? q.error.message : "Could not load ledger."}
          </p>
        )}

        {q.data && (
          <div className="mt-sp3 overflow-x-auto">
            <table className="w-full text-left text-[11px]">
              <thead className="text-[9.5px] uppercase tracking-wider text-t3">
                <tr>
                  <th className="py-1 pr-sp3">Seq</th>
                  <th className="py-1 pr-sp3">Recorded at</th>
                  <th className="py-1 pr-sp3">Ticker</th>
                  <th className="py-1 pr-sp3">Call type</th>
                  <th className="py-1 pr-sp3">Call ID</th>
                  <th className="py-1 pr-sp3">Hash</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((row) => (
                  <tr key={row.seq} className="border-t border-white/[0.04] hover:bg-bg3">
                    <td className="py-1 pr-sp3 font-mono text-t1">{row.seq}</td>
                    <td className="py-1 pr-sp3 font-mono text-t1">{fmtDate(row.recorded_at)}</td>
                    <td className="py-1 pr-sp3 font-mono text-t2">{row.ticker}</td>
                    <td className="py-1 pr-sp3 text-t1">{row.call_type}</td>
                    <td className="py-1 pr-sp3 font-mono text-t3">{row.call_id.slice(0, 16)}…</td>
                    <td className="py-1 pr-sp3 font-mono text-t3">{shortHash(row.hash)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {q.data.length === 0 && <p className="text-[12px] text-t3 py-sp4 text-center">No ledger entries match the filter.</p>}
          </div>
        )}
      </section>
    </div>
  );
}