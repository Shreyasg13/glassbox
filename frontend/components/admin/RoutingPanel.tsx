"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RoutingStatus, RoutingTestResult } from "@/lib/types";

const TIER: Record<string, string> = {
  free: "text-teal",
  freemium: "text-teal",
  local: "text-t2",
  custom: "text-t2",
  paid: "text-gold",
};

function fmtWait(s: number): string {
  return s >= 3600 ? `${Math.round(s / 3600)}h` : s >= 60 ? `${Math.round(s / 60)}m` : `${s}s`;
}

/** Where LLM traffic goes when Gemini's free tier runs out: which fallback
 * providers are configured (a key is all it takes), which are resting after a
 * quota error, and a one-click test that proves the failover works. */
export function RoutingPanel() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["llm-routing"],
    queryFn: () => apiFetch<RoutingStatus>("/api/admin/providers/routing", { token: token ?? undefined }),
    refetchInterval: 20_000,
    enabled: !!token,
  });
  const test = useMutation({
    mutationFn: () => apiFetch<RoutingTestResult>("/api/admin/providers/routing/test", { method: "POST", token: token ?? undefined, body: "{}" }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["llm-routing"] }),
  });

  if (!data) return null;
  const usable = data.providers.filter((p) => p.configured && !p.cooling_down_s).length;
  const rows = [...data.providers].sort((a, b) => Number(b.configured) - Number(a.configured) || data.order.indexOf(a.provider) - data.order.indexOf(b.provider));
  const err = test.error instanceof ApiError ? test.error.message : null;

  return (
    <div className="glass-panel p-sp4">
      <div className="flex flex-wrap items-start justify-between gap-sp3">
        <div>
          <h2 className="text-[13px] font-bold uppercase tracking-wide text-t3">LLM routing &amp; failover</h2>
          <p className="mt-1 max-w-[70ch] text-[11px] text-t3">
            If a provider runs out of quota, requests move to the next configured one instead of stopping. Add a key to the server’s <span className="mono">.env</span> to enable a
            provider. Order: <span className="mono">{data.order.join(" → ")}</span>. {usable} usable now.
            {!data.enabled && <strong className="ml-1 text-red">Failover is switched off.</strong>}
          </p>
        </div>
        <button type="button" className="btn btn-primary" disabled={test.isPending} onClick={() => test.mutate()}>
          {test.isPending ? "Testing…" : "Test failover"}
        </button>
      </div>

      {test.isSuccess && (
        <p className="mt-sp3 text-[12px] text-teal">
          ✓ Answered by <strong>{test.data.answered_by}</strong> ({test.data.model}){test.data.failed_over ? " — failed over from the first choice" : ""}: “{test.data.reply}”
        </p>
      )}
      {test.isError && <p className="mt-sp3 text-[12px] text-red">✗ No provider could answer{err ? ` — ${err}` : ""}. Add a free key below (OpenRouter is the quickest).</p>}

      <div className="mt-sp3 overflow-x-auto">
        <table className="w-full min-w-[560px] text-[12px]">
          <thead>
            <tr className="text-left text-[10px] font-bold uppercase tracking-wide text-t3">
              <th className="px-sp3 py-sp2">Provider</th>
              <th className="px-sp3 py-sp2">Cost</th>
              <th className="px-sp3 py-sp2">Status</th>
              <th className="px-sp3 py-sp2">Last result</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.provider} className="border-t border-border">
                <td className="px-sp3 py-sp2">
                  <span className="font-semibold text-t1">{p.label}</span>
                  <span className="mono ml-2 text-[10px] text-t3">{p.provider}</span>
                </td>
                <td className={`px-sp3 py-sp2 text-[11px] font-semibold uppercase ${TIER[p.tier] ?? "text-t3"}`}>{p.tier}</td>
                <td className="px-sp3 py-sp2">
                  {!p.configured ? (
                    <span className="text-t3">
                      not set up{p.get_a_key && (
                        <>
                          {" · "}
                          <a href={p.get_a_key} target="_blank" rel="noreferrer" className="text-teal underline">
                            get a key
                          </a>
                        </>
                      )}
                    </span>
                  ) : p.cooling_down_s ? (
                    <span className="text-gold" title={p.cooldown_reason}>
                      resting {fmtWait(p.cooling_down_s)} — {p.cooldown_reason}
                    </span>
                  ) : (
                    <span className="text-teal">ready</span>
                  )}
                </td>
                <td className="px-sp3 py-sp2 text-t3">{p.last ? (p.last.ok ? "✓ ok" : `✗ ${p.last.detail}`) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
