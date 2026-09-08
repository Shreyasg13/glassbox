"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLensVoice } from "@/lib/useLensVoice";
import { GLASSBOX_GUIDE, GUIDE_ELEVENLABS_VOICE_ID, GUIDE_KOKORO_VOICE_ID } from "@/lib/glassboxGuide";

/**
 * Live word-by-word captions while the Guide's real ElevenLabs/Kokoro
 * audio plays -- driven by the actual <audio> element's currentTime via
 * useLensVoice's onProgress callback (real playback fraction, not a
 * guessed timer), weighted by each word's character length so a longer
 * word gets proportionally more of the highlighted timeline. Purely a
 * rendering concern local to GuideBubble; doesn't touch voice state.
 */
function useCaptionSweep(message: string) {
  const tokens = useMemo(() => message.split(/(\s+)/), [message]);
  const wordPositions = useMemo(
    () => tokens.map((t, i) => (/^\s+$/.test(t) ? -1 : i)).filter((i) => i >= 0),
    [tokens]
  );
  const cumLens = useMemo(() => {
    let sum = 0;
    return wordPositions.map((i) => (sum += tokens[i].length, sum));
  }, [wordPositions, tokens]);
  const totalLen = cumLens[cumLens.length - 1] || 1;

  const [speaking, setSpeaking] = useState(false);
  const [activeWord, setActiveWord] = useState(-1);
  // Guards against a race: a previous speak() call's onEnded/onProgress
  // firing after a newer call already started for a different message
  // (e.g. rapid step navigation) -- same shape of problem the hook's own
  // internal requestIdRef solves, just needed again at this consumer level
  // since this component's callbacks close over component state, not the
  // hook's internals.
  const genRef = useRef(0);

  function start() {
    genRef.current += 1;
    setSpeaking(true);
    setActiveWord(0);
  }
  function progress(gen: number, fraction: number) {
    if (gen !== genRef.current) return;
    const target = fraction * totalLen;
    let idx = cumLens.length - 1;
    for (let i = 0; i < cumLens.length; i++) {
      if (target <= cumLens[i]) {
        idx = i;
        break;
      }
    }
    setActiveWord(idx);
  }
  function end(gen: number) {
    if (gen !== genRef.current) return;
    setSpeaking(false);
    setActiveWord(-1);
  }

  return { tokens, wordPositions, activeWord, speaking, start, progress, end, gen: () => genRef.current };
}

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
  const caption = useCaptionSweep(message);

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
            {caption.speaking
              ? (() => {
                  let wordPos = -1;
                  return caption.tokens.map((tok, i) => {
                    if (/^\s+$/.test(tok)) return tok;
                    wordPos += 1;
                    const pos = wordPos;
                    const cls =
                      pos < caption.activeWord
                        ? "text-t1"
                        : pos === caption.activeWord
                          ? "font-bold text-teal"
                          : "opacity-45";
                    return (
                      <span key={i} className={cls}>
                        {tok}
                      </span>
                    );
                  });
                })()
              : message}
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
