"use client";

import { useState } from "react";
import type { StrategyAgent, StrategyDecision } from "@/lib/types";
import { LeanChip, RiskChip, leanTone } from "./shared";

function AgentRow({ a, call, prompt }: { a: StrategyAgent; call: string | null; prompt: string | null }) {
  const [open, setOpen] = useState(false);
  const dissent = a.ok && call && a.lean !== call;
  return (
    <li className={`rounded-r2 border px-sp3 py-sp2 ${dissent ? "border-gold/40 bg-gold-dim/40" : "border-border bg-bg2/40"}`}>
      <div className="flex flex-wrap items-center gap-x-sp3 gap-y-1">
        <span className="text-[12px] font-semibold text-t1">{a.agent}</span>
        {a.ok ? (
          <>
            <LeanChip lean={a.lean} small />
            {a.confidence !== undefined && <span className="mono text-[10px] text-t2">{a.confidence}% sure</span>}
            {a.risk_level && <RiskChip level={a.risk_level} />}
            {dissent && <span className="text-[10px] font-bold uppercase text-gold">dissent</span>}
          </>
        ) : (
          <span className="text-[10px] font-bold uppercase text-red">no answer</span>
        )}
        <span className="mono ml-auto text-[10px] text-t3">
          {a.type === "deterministic" ? "engine · no model" : [a.provider, a.model].filter(Boolean).join(" · ")}
          {a.latency_s !== undefined && a.type === "llm" ? ` · ${a.latency_s}s` : ""}
        </span>
      </div>
      {a.failed_over_from && <p className="mt-1 text-[10px] text-gold">answered by {a.provider} after {a.failed_over_from} was unavailable</p>}
      {a.ok ? (
        <p className="mt-1 text-[11px] leading-snug text-t2">{a.summary}</p>
      ) : (
        <p className="mt-1 text-[11px] text-red">{a.error}</p>
      )}
      {a.type === "llm" && (a.raw || a.system_prompt) && (
        <>
          <button type="button" className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-teal hover:underline" onClick={() => setOpen(!open)}>
            {open ? "Hide" : "Show"} prompt &amp; raw reply
          </button>
          {open && (
            <div className="mt-sp2 grid gap-sp2 text-[10px]">
              {a.system_prompt && (
                <div>
                  <div className="mb-[2px] font-bold uppercase tracking-wide text-t3">System prompt (this agent&rsquo;s role)</div>
                  <pre className="mono max-h-[140px] overflow-auto whitespace-pre-wrap rounded-r1 bg-bg3 p-sp2 text-t2">{a.system_prompt}</pre>
                </div>
              )}
              {prompt && (
                <div>
                  <div className="mb-[2px] font-bold uppercase tracking-wide text-t3">Prompt (identical for every analyst)</div>
                  <pre className="mono max-h-[180px] overflow-auto whitespace-pre-wrap rounded-r1 bg-bg3 p-sp2 text-t2">{prompt}</pre>
                </div>
              )}
              {a.raw && (
                <div>
                  <div className="mb-[2px] font-bold uppercase tracking-wide text-t3">
                    Raw reply {a.structured === false && <span className="text-gold">· not valid JSON, vote read from the text</span>}
                  </div>
                  <pre className="mono max-h-[160px] overflow-auto whitespace-pre-wrap rounded-r1 bg-bg3 p-sp2 text-t2">{a.raw}</pre>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </li>
  );
}

/** Every committee member on one decision, split the way the committee is built: the three
 * deterministic engine agents (no model, always available) and the seven LLM analysts. */
export function AgentInspector({ d }: { d: StrategyDecision }) {
  const prompt = d.prompt ?? d.context;
  const trio = d.agents.filter((a) => a.type === "deterministic");
  const panel = d.agents.filter((a) => a.type !== "deterministic");
  const call = d.decision;
  const group = (title: string, note: string, rows: StrategyAgent[]) => (
    <div>
      <div className="mb-sp2 flex items-baseline gap-sp2">
        <h3 className="text-[11px] font-bold uppercase tracking-wide text-t2">{title}</h3>
        <span className="text-[10px] text-t3">{note}</span>
      </div>
      {rows.length ? (
        <ul className="flex flex-col gap-sp2">
          {rows.map((a) => (
            <AgentRow key={a.agent} a={a} call={call} prompt={prompt} />
          ))}
        </ul>
      ) : (
        <p className="text-[11px] text-t3">none recorded</p>
      )}
    </div>
  );
  return (
    <div className="grid gap-sp4 lg:grid-cols-[1fr_1.4fr]">
      {group(`Engine trio · ${trio.length}`, "deterministic — reads the signal, never a model", trio)}
      {group(`Analyst panel · ${panel.length}`, `${panel.filter((a) => a.ok).length} answered · confidence is self-reported, not calibrated`, panel)}
      {d.error && <p className="text-[11px] text-red lg:col-span-2">Run error: {d.error}</p>}
      {!d.error && call && (
        <p className={`text-[11px] lg:col-span-2 ${leanTone(call)}`}>
          Vote → <b>{call}</b>
          {d.action && d.action !== call ? ` · after the risk check: ${d.action}` : ""}
        </p>
      )}
    </div>
  );
}
