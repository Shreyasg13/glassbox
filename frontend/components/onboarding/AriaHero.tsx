"use client";

import { useEffect } from "react";
import { useLensVoice } from "@/lib/useLensVoice";
import { GLASSBOX_GUIDE, GUIDE_ELEVENLABS_VOICE_ID, GUIDE_KOKORO_VOICE_ID } from "@/lib/glassboxGuide";
import { GuideAvatar, CaptionText, useCaptionSweep } from "./GuideBubble";

/**
 * The ONE onboarding hero -- Aria's avatar, name, voice controls, and
 * her per-step message, all in a single frosted card. Replaces the old
 * two-card sidebar (a separate agent-persona "AgentHero" stacked above
 * a "GlassBox Guide" copilot box) that a bug report flagged as a
 * confusing duplicate identity -- there's only ever been one guide
 * persona in this app (GLASSBOX_GUIDE), so showing her twice, once
 * generically and once "in character" as a chosen agent, was the bug,
 * not a feature. See OnboardingFlow.tsx for the also-retired
 * agent-pick step this replaces.
 */
export function AriaHero({ message, compact = false, autoSpeak = false }: {
  message: string;
  compact?: boolean;
  autoSpeak?: boolean;
}) {
  const voice = useLensVoice();
  const caption = useCaptionSweep(message);

  useEffect(() => () => voice.stop(), [voice.stop]);

  function handleSpeak() {
    voice.primeAudio();
    if (!voice.enabled) voice.toggle();
    caption.start();
    const gen = caption.gen();
    voice.speak(
      GLASSBOX_GUIDE.id,
      message,
      GUIDE_ELEVENLABS_VOICE_ID,
      GUIDE_KOKORO_VOICE_ID,
      () => caption.end(gen),
      (fraction) => caption.progress(gen, fraction)
    );
  }

  function handleToggleVoice() {
    voice.primeAudio();
    if (voice.enabled) voice.stop();
    voice.toggle();
  }

  // Autoplay once per mount (parent remounts this via `key={step}`), same
  // gating as GuideBubble's own autoSpeak -- only on the surface that
  // should actually speak automatically (desktop sidebar), never the
  // mobile compact instance too, or two <audio> elements would race.
  useEffect(() => {
    if (!autoSpeak || !voice.enabled) return;
    const t = setTimeout(() => handleSpeak(), 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (compact) {
    return (
      <div className="flex items-center gap-sp3">
        <GuideAvatar size={34} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-sp2">
            <span className="text-[12px] font-extrabold text-t1">{GLASSBOX_GUIDE.name}</span>
            <button
              type="button"
              onClick={handleToggleVoice}
              aria-pressed={voice.enabled}
              aria-label={voice.enabled ? `Turn off ${GLASSBOX_GUIDE.name}'s voice` : `Turn on ${GLASSBOX_GUIDE.name}'s voice`}
              className={`shrink-0 rounded-r4 border px-sp2 py-0.5 text-[10px] font-semibold ${
                voice.enabled ? "border-teal/30 text-teal" : "border-border2 text-t4"
              }`}
            >
              {voice.enabled ? "🔊" : "🔈"}
            </button>
          </div>
          <p className="min-w-0 break-words text-[12px] text-t2">
            <CaptionText message={message} caption={caption} />
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="relative mb-sp4 overflow-hidden rounded-[26px] p-sp5 text-center"
      style={{
        background: "linear-gradient(160deg, var(--c-teal-dim), transparent 70%)",
        border: "1px solid var(--c-border2)",
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
        boxShadow: "0 12px 32px -14px var(--c-teal-dim), inset 0 1px 0 rgba(255,255,255,.08)",
      }}
    >
      {/* top glass highlight -- the "liquid" sheen, not a border */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-1/2 opacity-40"
        style={{ background: "linear-gradient(180deg, rgba(255,255,255,.35), rgba(255,255,255,0))" }}
        aria-hidden="true"
      />

      <div className="relative">
        <div className="relative mx-auto mb-sp3 w-fit">
          <div
            className="absolute inset-[-10px] rounded-full blur-md"
            style={{ background: "var(--c-teal-dim)" }}
            aria-hidden="true"
          />
          <GuideAvatar size={72} />
        </div>
        <div className="text-[17px] font-extrabold tracking-tight text-t1">{GLASSBOX_GUIDE.name}</div>
        <div className="mono mt-0.5 text-[10px] font-bold uppercase tracking-wide text-teal">
          Your onboarding guide
        </div>

        <div className="mt-sp3 flex items-center justify-center gap-sp2">
          <button
            type="button"
            onClick={handleToggleVoice}
            aria-pressed={voice.enabled}
            aria-label={voice.enabled ? `Turn off ${GLASSBOX_GUIDE.name}'s voice` : `Turn on ${GLASSBOX_GUIDE.name}'s voice`}
            className={`rounded-r4 border px-sp3 py-1 text-[11px] font-bold ${
              voice.enabled ? "border-teal/40 bg-teal/10 text-teal" : "border-border2 text-t4"
            }`}
          >
            {voice.enabled ? "🔊 Voice on" : "🔈 Voice off"}
          </button>
          <button
            type="button"
            onClick={handleSpeak}
            aria-label={`Replay narration from ${GLASSBOX_GUIDE.name}`}
            title="Hear this"
            className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-teal/30 text-[12px] text-teal hover:bg-teal/10"
          >
            ↻
          </button>
        </div>

        <div className="mt-sp4 rounded-r3 border border-teal/[0.18] bg-teal/[0.05] p-sp3 text-left">
          <div className="mb-1 flex items-center gap-1 text-[9.5px] font-extrabold uppercase tracking-wide text-teal">
            {GLASSBOX_GUIDE.name} · Guide
            {caption.speaking && <span className="animate-pulse text-[8px] font-bold">● live</span>}
          </div>
          <p className="min-w-0 break-words text-[12.5px] leading-relaxed text-t2">
            <CaptionText message={message} caption={caption} />
          </p>
        </div>
      </div>
    </div>
  );
}
