"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { GateResult, ResearchView } from "@/lib/types";
import { DataSourcesPanel } from "./DataSourcesPanel";
import { Section, Th, tone } from "./shared";

const verdictStyle = (v: GateResult["verdict"]) =>
  v === "edge" ? "bg-teal-dim text-teal" : v === "worse" ? "bg-red-dim text-red" : v === "no edge yet" ? "bg-gold-dim text-gold" : "bg-bg3 text-t3";

function Verdict({ g, label }: { g: GateResult | undefined; label: string }) {
  if (!g) return <span className="text-t3">—</span>;
  return (
    <div>
      <span className={`inline-block whitespace-nowrap rounded-r1 px-2 py-[1px] text-[10px] font-bold uppercase ${verdictStyle(g.verdict)}`}>{g.verdict}</span>
      <div className="mono mt-[2px] text-[10px] text-t3" title={`${label}: needs ${g.needed_days} live days`}>
        {g.n_days}/{g.needed_days} days{g.mean_excess_bps !== null && <> · <span className={tone(g.mean_excess_bps)}>{g.mean_excess_bps >= 0 ? "+" : ""}{g.mean_excess_bps.toFixed(1)} bps/day</span></>}
      </div>
    </div>
  );
}

/** The research loop's window: how the stocks move together (recomputed daily), the strict live-evidence
 * gate every strategy must clear, standing proposals, and the weekly digest. Nothing here changes anything. */
export function ResearchPanel() {
  const { token } = useAuth();
  const q = useQuery({
    queryKey: ["strategy-research"],
    queryFn: () => apiFetch<ResearchView>("/api/admin/strategy/research", { token: token ?? undefined }),
    enabled: !!token,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
  if (q.isPending) return <p className="py-sp6 text-center text-[13px] text-t3">Analysing how the stocks move together…</p>;
  if (q.isError) return <p className="py-sp6 text-center text-[13px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load research"}</p>;
  const r = q.data;
  const a = r.associations;

  return (
    <div className="flex flex-col gap-sp5">
      <div className="rounded-r3 border border-gold/40 bg-gold-dim/40 p-sp4 text-[12px] leading-snug text-t2">
        <b className="text-gold">How this learns — and what it will not do.</b> Data, correlations, risk and the committee&rsquo;s peer context refresh every day. Once a week a digest reports what
        changed and what the live results support. A strategy is only called an improvement after {r.min_live_days} live trading days with a confidence interval above zero, corrected for how many
        strategies are being compared. Proposals are advice for you: nothing here edits an agent, a weight or a strategy by itself, because with this little data self-modification would just fit noise.
      </div>

      <Section title="Live evidence gate" note={`Live (out-of-sample) daily excess return against each yardstick. Every verdict except "insufficient" needs ${r.min_live_days} days. It is normal for weeks to read "insufficient".`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-[12px]">
            <thead>
              <tr>
                <Th>Strategy</Th>
                <Th right>Live days</Th>
                <Th>vs equal-weight hold</Th>
                <Th>vs placebo</Th>
              </tr>
            </thead>
            <tbody>
              {r.evidence.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="px-sp3 py-sp2 font-semibold text-t1">
                    {e.name}
                    {e.challenger && <span className="ml-2 rounded-r1 bg-purple-dim px-2 py-[1px] text-[9px] font-bold uppercase tracking-wide text-purple">challenger</span>}
                  </td>
                  <td className="mono px-sp3 py-sp2 text-right text-t2">{e.live_days}</td>
                  <td className="px-sp3 py-sp2"><Verdict g={e.vs.ctl_equal} label="vs equal-weight hold" /></td>
                  <td className="px-sp3 py-sp2"><Verdict g={e.vs.ctl_placebo} label="vs placebo" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-sp3">
          <h3 className="text-[11px] font-bold uppercase tracking-wide text-t2">Proposals</h3>
          {r.proposals.length ? (
            <ul className="mt-1 list-disc pl-5 text-[12px] text-t2">{r.proposals.map((p) => <li key={p}>{p}</li>)}</ul>
          ) : (
            <p className="mt-1 text-[12px] text-t3">None. No strategy has cleared the gate and no agent has enough scored calls, so the system is not suggesting any change.</p>
          )}
        </div>
      </Section>

      {a && (
        <Section title="How the stocks move together" note={`Last ${a.window_days} trading days, ${a.symbols} symbols, as of ${a.date}. Recomputed from prices every day.`}>
          <div className="grid gap-sp4 md:grid-cols-3">
            <div className="rounded-r2 border border-border bg-bg2/40 p-sp3">
              <div className="text-[10px] font-bold uppercase tracking-wide text-t3">Market cohesion</div>
              <div className="mt-1 text-[20px] font-extrabold text-t1">{a.cohesion.value === null ? "—" : (Math.round(a.cohesion.value * 100) / 100 + 0).toFixed(2)}</div>
              <div className={`text-[12px] font-semibold ${a.cohesion.label === "crowded" ? "text-red" : a.cohesion.label === "diversifying" ? "text-teal" : "text-t2"}`}>
                {a.cohesion.label}{a.cohesion.percentile !== null && ` · ${Math.round(a.cohesion.percentile)}th percentile of its history`}
              </div>
              <p className="mt-1 text-[10px] text-t3">Average correlation between every pair. When it is high, owning many names buys less diversification than it looks.</p>
            </div>
            <div className="rounded-r2 border border-border bg-bg2/40 p-sp3">
              <div className="text-[10px] font-bold uppercase tracking-wide text-t3">Groups that are really one bet</div>
              {a.clusters.length ? (
                <ul className="mt-1 flex flex-col gap-1 text-[12px] text-t1">{a.clusters.map((g) => <li key={g.join("+")} className="mono">{g.join(" · ")}</li>)}</ul>
              ) : (
                <p className="mt-1 text-[12px] text-t3">None above the 0.70 correlation threshold.</p>
              )}
            </div>
            <div className="rounded-r2 border border-border bg-bg2/40 p-sp3">
              <div className="text-[10px] font-bold uppercase tracking-wide text-t3">Strongest / weakest pairs</div>
              <ul className="mono mt-1 flex flex-col gap-[2px] text-[11px] text-t2">
                {a.strongest_pairs.slice(0, 3).map((p) => <li key={p.a + p.b}>{p.a}–{p.b} <span className="text-teal">{p.r.toFixed(2)}</span></li>)}
                {a.weakest_pairs.slice(0, 2).map((p) => <li key={p.a + p.b}>{p.a}–{p.b} <span className="text-gold">{p.r.toFixed(2)}</span></li>)}
              </ul>
            </div>
          </div>
          <p className="mt-sp3 text-[12px] leading-snug text-t2">
            <b className="text-t1">Lead-lag.</b> {a.lead_lag.tests.toLocaleString()} pair-and-lag combinations were tested, and a relationship only counts if it beats the strongest chance correlation found in shuffled copies of the same data
            {a.lead_lag.threshold_r !== null && <> (|r| ≥ {a.lead_lag.threshold_r.toFixed(2)})</>}.{" "}
            {a.lead_lag.findings.length ? (
              <>Survived: {a.lead_lag.findings.slice(0, 3).map((f) => `${f.leader} leads ${f.follower} by ${f.lag_days}d (r=${f.r.toFixed(2)})`).join("; ")}.</>
            ) : (
              <>None survived: no name reliably moves before another, which is the normal result for liquid large caps.</>
            )}
          </p>
        </Section>
      )}

      <DataSourcesPanel />

      <Section title="Latest weekly digest" note="Also saved in Admin → Reports. Written after each Friday's close.">
        {r.latest_digest ? (
          <pre className="mono max-h-[520px] overflow-auto whitespace-pre-wrap rounded-r2 bg-bg3 p-sp3 text-[11px] leading-relaxed text-t2">{r.latest_digest.narrative}</pre>
        ) : (
          <p className="text-[12px] text-t3">No digest yet. The first one is written on Friday evening.</p>
        )}
      </Section>
    </div>
  );
}
