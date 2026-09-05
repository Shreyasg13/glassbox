"use client";

import { useEffect, useState } from "react";
import { useLensVoice } from "@/lib/useLensVoice";
import { GLASSBOX_GUIDE } from "@/lib/glassboxGuide";

// Real, live-verified ElevenLabs voice ID (fetched from GET /v2/voices
// with a real key earlier this build, not guessed) -- "River", labeled
// "Relaxed, Neutral, Informative" by ElevenLabs itself. Deliberately
// not one of the 8 IDs already assigned to the investor Strategy Lens
// personas (lensData.ts): this is a system agent, not an investor
// archetype, and a neutral voice fits that distinction on purpose.
const GUIDE_ELEVENLABS_VOICE_ID = "SAz9YHcvj6GT2YYXdXww";
// Kokoro fallback reuses an already-assigned Kokoro id (am_onyx, Shaw's
// lens) rather than guessing an unverified new one -- this session's
// hard-learned rule is to never guess a provider's voice-id namespace.
// This is only the FALLBACK path (ElevenLabs is primary and working),
// and the Guide (onboarding) and that lens (marketing carousel) are
// never on screen at the same time, so the overlap is low-stakes and
// disclosed here rather than silent.
const GUIDE_KOKORO_VOICE_ID = "am_onyx";

/**
 * The GlassBox Guide's avatar + name/role badge -- shared across
 * onboarding, the dashboard welcome note, and My Agents, so the Guide
 * reads as one consistent identity everywhere it appears.
 */
export function GuideAvatar({ size = 38 }: { size?: number }) {
  return (
    <div
      className="grid shrink-0 place-items-center rounded-full text-[15px] font-extrabold"
      style={{
        width: size,
        height: size,
        background: `var(--c-${GLASSBOX_GUIDE.accent}-dim)`,
        color: `var(--c-${GLASSBOX_GUIDE.accent})`,
        border: `2px solid var(--c-${GLASSBOX_GUIDE.accent})`,
      }}
    >
      ✓
    </div>
  );
}

/**
 * A contextual Guide message -- text always visible (per spec, voice is
 * an enhancement, never a dependency). Two distinct controls, both
 * real: a persistent mute/enable toggle showing current state (spec
 * explicitly requires "clear mute/enable controls", not just an
 * implicit one), and a one-click "hear this" action that turns voice on
 * if it's currently off and speaks either way (same convenience
 * pattern Hero.tsx's Listen button already uses: `if (!voice.enabled)
 * voice.toggle()` before speaking, rather than requiring a separate
 * prior toggle before the button even appears). Never autoplays --
 * speaking only ever happens from an explicit click, and stop() fires
 * on unmount so navigating away cuts it off cleanly (the `key`-driven
 * remount from step to step in OnboardingFlow already causes this
 * unmount naturally).
 */
export function GuideBubble({
  message,
  compact = false,
}: {
  message: string;
  compact?: boolean;
}) {
  const voice = useLensVoice();

  // Real stop-on-unmount, not just an assertion: OnboardingFlow remounts
  // this per step (keyed on the step), and the dashboard welcome note
  // unmounts on dismiss/navigation -- either way, any in-flight speech
  // must not keep playing into whatever's shown next. Depends on
  // voice.stop specifically (a stable useCallback reference), not the
  // whole voice object -- useLensVoice() returns a fresh object literal
  // every render, so depending on it directly would run this cleanup
  // (and re-register the effect) on every render, not just unmount.
  useEffect(() => () => voice.stop(), [voice.stop]);

  function handleSpeak() {
    voice.primeAudio();
    if (!voice.enabled) voice.toggle();
    voice.speak(GLASSBOX_GUIDE.id, message, GUIDE_ELEVENLABS_VOICE_ID, GUIDE_KOKORO_VOICE_ID);
  }

  function handleToggleVoice() {
    voice.primeAudio();
    if (voice.enabled) voice.stop();
    voice.toggle();
  }

  return (
    <div className={`flex gap-sp3 ${compact ? "items-center" : "items-start"}`}>
      <GuideAvatar size={compact ? 30 : 38} />
      <div className="flex-1">
        <div className="mb-0.5 flex items-center justify-between gap-sp2">
          {!compact ? (
            <div className="flex items-center gap-sp2">
              <span className="text-[12px] font-extrabold text-t1">{GLASSBOX_GUIDE.name}</span>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-t3">
                {GLASSBOX_GUIDE.role}
              </span>
            </div>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={handleToggleVoice}
            aria-pressed={voice.enabled}
            aria-label={voice.enabled ? "Turn off GlassBox Guide voice" : "Turn on GlassBox Guide voice"}
            title={voice.enabled ? "Voice on" : "Voice off"}
            className={`shrink-0 rounded-r4 border px-sp2 py-0.5 text-[10px] font-semibold ${
              voice.enabled ? "border-teal/30 text-teal" : "border-border2 text-t4"
            }`}
          >
            {voice.enabled ? "🔊 Voice on" : "🔈 Voice off"}
          </button>
        </div>
        <div className="flex items-start gap-sp2">
          <p className={`flex-1 text-t2 ${compact ? "text-[12px]" : "text-[13px] leading-relaxed"}`}>
            {message}
          </p>
          <button
            type="button"
            onClick={handleSpeak}
            aria-label="Hear this from GlassBox Guide"
            title="Hear this"
            className="shrink-0 text-[13px] text-t3 hover:text-teal"
          >
            ▶
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Small, accessible click-to-reveal explanation, reused across the
 * dashboard/reports pages -- same pattern StepVerify's onboarding
 * metric tooltips already established (extracted here so it's not
 * duplicated per page). A real <button>, not a hover-only div, so it's
 * keyboard-operable; role="tooltip" + aria-expanded for screen readers.
 * Deliberately doesn't speak -- these are quick inline glossary hints,
 * not Guide messages, so they don't carry the voice controls above.
 */
export function GuideHint({ label, explanation }: { label: string; explanation: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`What is ${label}?`}
        className="ml-1 inline-grid h-4 w-4 place-items-center rounded-full border border-border2 text-[9px] font-bold text-t3 hover:border-teal hover:text-teal"
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-1/2 top-full z-10 mt-1 w-[200px] -translate-x-1/2 rounded-r2 border border-border2 bg-panel2 p-sp3 text-left text-[11px] leading-relaxed text-t2 shadow-lg2"
        >
          {explanation}
        </span>
      )}
    </span>
  );
}
