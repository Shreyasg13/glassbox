"use client";

import { ExplainTooltip } from "@/components/ExplainTooltip";
import { AgentAvatar } from "./AgentAvatar";
import { AGENT_PERSONAS, getAgentPersona, hexToRgba } from "./agentPersonas";

function Meter({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-[7px] flex-1 overflow-hidden rounded-full bg-raised">
      <div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} />
    </div>
  );
}

export function StepAgent({ selectedId, onSelect }: { selectedId: string; onSelect: (id: string) => void }) {
  const agent = getAgentPersona(selectedId);

  return (
    <div>
      <div className="mb-1 flex items-center gap-1 text-[17px] font-bold text-t1">
        Choose your agent
        <ExplainTooltip
          tag="What is this?"
          title="Your agent"
          desc="Each agent is a lens -- it reads the same verified data through a different investing style, re-weighting which factors matter. The evidence never changes; only the emphasis does. You can switch anytime before you continue."
        />
      </div>
      <div className="mb-sp4 text-[13px] text-t3">
        Pick the agent that will guide your onboarding and frame your first verification.
      </div>

      <div
        className="relative mx-auto mb-sp4 max-w-[340px] rounded-r4 border-2 p-sp5 text-center"
        style={{ borderColor: agent.color, boxShadow: `0 10px 34px ${hexToRgba(agent.color, 0.1)}` }}
      >
        <div className="mono absolute left-sp3 top-sp3 rounded-r1 border border-border bg-bg2 px-2 py-1 text-[11px] font-bold text-t3">
          {agent.rank} · {agent.tag}
        </div>
        <div className="mx-auto mt-sp2 mb-sp3">
          <div className="mx-auto flex justify-center">
            <AgentAvatar face={agent.face} color={agent.color} size={110} showCheck />
          </div>
        </div>
        <div className="text-[22px] font-extrabold tracking-tight text-t1">{agent.name}</div>
        <div className="mono mt-1 text-[11px] font-bold uppercase tracking-wide" style={{ color: agent.color }}>
          {agent.tag}
        </div>

        <div className="my-sp4 rounded-r2 border border-border bg-bg2 p-sp3 text-center">
          <div className="text-[12.5px] text-t2">
            Strategy · <b className="text-t1">{agent.strategy}</b>
          </div>
          <div className="mt-0.5 text-[12px] font-bold" style={{ color: agent.color }}>
            {agent.who}
          </div>
          <div className="mono mt-sp2 text-[11px] leading-relaxed text-t3">📈 {agent.note}</div>
        </div>

        <div className="mb-sp4 flex flex-col gap-sp2 text-left">
          <div className="flex items-center gap-sp3">
            <span className="mono w-[56px] shrink-0 text-[10px] font-bold uppercase tracking-wide text-t3">
              Growth
            </span>
            <Meter value={agent.growth} color="var(--c-gold)" />
            <span className="mono w-[26px] shrink-0 text-right text-[13px] font-extrabold" style={{ color: "var(--c-gold)" }}>
              {agent.growth}
            </span>
          </div>
          <div className="flex items-center gap-sp3">
            <span className="mono w-[56px] shrink-0 text-[10px] font-bold uppercase tracking-wide text-t3">
              Risk
            </span>
            <Meter value={agent.risk} color="var(--c-green)" />
            <span className="mono w-[26px] shrink-0 text-right text-[13px] font-extrabold" style={{ color: "var(--c-green)" }}>
              {agent.risk}
            </span>
          </div>
        </div>
      </div>

      <div className="flex gap-sp2 overflow-x-auto pb-1" role="tablist" aria-label="Choose your agent">
        {AGENT_PERSONAS.map((a) => {
          const on = a.id === selectedId;
          return (
            <button
              key={a.id}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => onSelect(a.id)}
              className={`flex w-[74px] shrink-0 flex-col items-center gap-1 rounded-r2 border p-sp2 text-center transition-colors ${
                on ? "" : "border-border bg-bg2 hover:border-border2"
              }`}
              style={on ? { borderColor: a.color, background: hexToRgba(a.color, 0.1) } : undefined}
            >
              <AgentAvatar face={a.face} color={a.color} size={42} />
              <span
                className="text-[10px] font-bold leading-tight"
                style={{ color: on ? a.color : "var(--c-t2)" }}
              >
                {a.name.replace("The ", "").replace(" Agent", "")}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
