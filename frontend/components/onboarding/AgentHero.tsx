"use client";

import { useEffect } from "react";
import { useLensVoice } from "@/lib/useLensVoice";
import { AgentAvatar } from "./AgentAvatar";
import { getAgentPersona, hexToRgba } from "./agentPersonas";

/**
 * Persistent "your chosen agent" identity block -- shown above the
 * existing GuideBubble in the onboarding sidebar (not merged into it),
 * so the system Guide voice and the chosen persona stay visually
 * distinct. A frosted "liquid glass" surface (same backdrop-filter
 * technique globals.css's .glass-nav already uses) rather than a flat
 * bordered rectangle -- no second hard-edged box stacked directly above
 * GuideBubble's own bordered card. Left-aligned, avatar-beside-name
 * layout so it reads as an assistant header, not a centered profile card.
 */
export function AgentHero({ agentId }: { agentId: string }) {
  const agent = getAgentPersona(agentId);
  const voice = useLensVoice();
  const hasVoice = Boolean(agent.elevenLabsVoiceId && agent.kokoroVoiceId);

  // Stop any in-flight narration when the shown agent changes (switching
  // in the deck rail) or this panel unmounts -- same reasoning as
  // GuideBubble's stop-on-unmount effect.
  useEffect(() => () => voice.stop(), [agentId, voice.stop]);

  function handleSpeak() {
    if (!hasVoice) return;
    voice.primeAudio();
    if (!voice.enabled) voice.toggle();
    voice.speak(agent.id, agent.say, agent.elevenLabsVoiceId!, agent.kokoroVoiceId!);
  }

  return (
    <div
      className="relative mb-sp4 overflow-hidden rounded-[26px] p-sp4"
      style={{
        background: `linear-gradient(160deg, ${hexToRgba(agent.color, 0.16)}, ${hexToRgba(agent.color, 0.05)})`,
        border: `1px solid ${hexToRgba(agent.color, 0.28)}`,
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
        boxShadow: `0 12px 32px -14px ${hexToRgba(agent.color, 0.45)}, inset 0 1px 0 ${hexToRgba("#ffffff", 0.08)}`,
      }}
    >
      {/* top glass highlight -- the "liquid" sheen, not a border */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-1/2 opacity-40"
        style={{ background: "linear-gradient(180deg, rgba(255,255,255,.35), rgba(255,255,255,0))" }}
        aria-hidden="true"
      />

      <div className="relative flex items-center gap-sp3 text-left">
        <div className="relative shrink-0">
          {/* soft halo behind the avatar for a rounded, "dynamic" feel
              instead of a hard-edged box around it */}
          <div
            className="absolute inset-[-8px] rounded-full blur-md"
            style={{ background: hexToRgba(agent.color, 0.35) }}
            aria-hidden="true"
          />
          <AgentAvatar face={agent.face} color={agent.color} size={56} />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span
              className="h-[7px] w-[7px] shrink-0 rounded-full"
              style={{ background: agent.color, boxShadow: `0 0 0 3px ${hexToRgba(agent.color, 0.2)}` }}
            />
            <span className="text-[13.5px] font-extrabold leading-tight text-t1">{agent.name}</span>
          </div>
          <div className="mono mt-0.5 text-[10px] font-bold uppercase tracking-wide" style={{ color: agent.color }}>
            {agent.tag}
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={handleSpeak}
        disabled={!hasVoice}
        title={hasVoice ? undefined : "Voice narration needs a live ElevenLabs key -- not configured in this environment yet"}
        aria-pressed={voice.enabled && hasVoice}
        className="relative mt-sp3 w-full rounded-r4 border py-1.5 text-[11px] font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-45"
        style={{ borderColor: hexToRgba(agent.color, 0.5), color: agent.color }}
      >
        {hasVoice ? "🔊 Hear this agent" : "🔈 Voice coming soon"}
      </button>
    </div>
  );
}
