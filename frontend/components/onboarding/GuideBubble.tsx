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
export function useCaptionSweep(message: string) {
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
 * real, grouped together in the header row so they read as one
 * cohesive voice control rather than a stray glyph floating on the
 * message line: a "▶ Hear" button (always available, works whether or
 * not voice is currently enabled -- turns it on if needed, same
 * convenience pattern Hero.tsx's Listen button uses) and a persistent
 * mute/enable toggle showing current state. During onboarding
 * specifically (see the `autoSpeak` prop), the Guide also speaks each
 * step automatically without waiting for that click -- gated on
 * `voice.enabled`, which the onboarding intro's "Get Started" button
 * turns on via a real user gesture before the first step ever renders.
 * Outside onboarding (dashboard welcome note, My Agents), voice stays
 * click-only. stop() fires on unmount so navigating away cuts audio off
 * cleanly (the `key`-driven remount from step to step in OnboardingFlow
 * already causes this unmount naturally).
 */
/** Renders a message as either the plain string or, mid-speech, the
 * word-by-word highlighted caption sweep -- shared by GuideBubble and
 * AriaHero so the two identical caption-rendering blocks don't drift. */
export function CaptionText({ message, caption }: { message: string; caption: ReturnType<typeof useCaptionSweep> }) {
  if (!caption.speaking) return <>{message}</>;
  let wordPos = -1;
  return (
    <>
      {caption.tokens.map((tok, i) => {
        if (/^\s+$/.test(tok)) return tok;
        wordPos += 1;
        const pos = wordPos;
        const cls =
          pos < caption.activeWord ? "text-t1" : pos === caption.activeWord ? "font-bold text-teal" : "opacity-45";
        return (
          <span key={i} className={cls}>
            {tok}
          </span>
        );
      })}
    </>
  );
}

export function GuideBubble({
  message,
  compact = false,
  autoSpeak = false,
}: {
  message: string;
  compact?: boolean;
  // Speak this message on mount, once, if voice is enabled -- opt-in per
  // instance because OnboardingFlow mounts TWO GuideBubbles for the same
  // step at once (a desktop sidebar one and a `lg:hidden` compact one for
  // mobile; both stay mounted, just CSS-toggled, so both would fire an
  // on-mount effect). Only the desktop instance passes true, or both
  // would speak simultaneously on separate <audio> elements -- real,
  // audible double-playback, not a theoretical bug. Known gap: mobile
  // therefore has no autoplay this pass, same "not verified on iOS"
  // honesty bar the rest of the voice work already holds itself to --
  // the manual Hear button still works everywhere.
  autoSpeak?: boolean;
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

  // Autoplay for this one instance, gated behind the `autoSpeak` prop
  // (see its doc comment above for why only one of the two mounted
  // instances ever passes true) AND `voice.enabled` -- which itself only
  // becomes true after the onboarding intro's "Get Started" click primes
  // + enables voice (OnboardingFlow.tsx), a real gesture. Runs once per
  // mount; GuideBubble is remounted per step via `key={step}` in the
  // parent, so "on mount" already means "once per step" for free -- no
  // extra step-tracking needed here.
  useEffect(() => {
    if (!autoSpeak || !voice.enabled) return;
    const t = setTimeout(() => handleSpeak(), 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={`flex gap-sp3 ${compact ? "items-center" : "items-start"}`}>
      <GuideAvatar size={compact ? 30 : 38} />
      {/* min-w-0 is load-bearing here, not decorative: this column sits in
          a 220px sidebar (grid-cols-[220px_1fr] in OnboardingFlow), and a
          flex item's default min-width is `auto` -- without min-w-0 it
          refuses to shrink below its content's natural width, so text and
          buttons overflow the card's right edge instead of wrapping. Real
          bug caught by a screenshot verification pass, not theoretical. */}
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-sp2">
          {!compact ? (
            <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-sp2">
              <span className="text-[12px] font-extrabold text-t1">{GLASSBOX_GUIDE.name}</span>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-t3">
                {GLASSBOX_GUIDE.role}
              </span>
            </div>
          ) : (
            <span className="flex-1" />
          )}
          <button
            type="button"
            onClick={handleToggleVoice}
            aria-pressed={voice.enabled}
            aria-label={voice.enabled ? `Turn off ${GLASSBOX_GUIDE.name}'s voice` : `Turn on ${GLASSBOX_GUIDE.name}'s voice`}
            title={voice.enabled ? "Voice on" : "Voice off"}
            className={`shrink-0 rounded-r4 border px-sp2 py-0.5 text-[10px] font-semibold ${
              voice.enabled ? "border-teal/30 text-teal" : "border-border2 text-t4"
            }`}
          >
            {voice.enabled ? "🔊 Voice on" : "🔈 Voice off"}
          </button>
        </div>
        <button
          type="button"
          onClick={handleSpeak}
          aria-label={`Hear this from ${GLASSBOX_GUIDE.name}`}
          title="Hear this"
          className="mb-sp2 inline-flex shrink-0 items-center gap-1 rounded-r4 border border-teal/30 px-sp2 py-0.5 text-[10px] font-semibold text-teal hover:bg-teal/10"
        >
          ▶ Hear
        </button>
        <div className="flex min-w-0 items-start gap-sp2">
          <p
            className={`min-w-0 flex-1 break-words text-t2 ${compact ? "text-[12px]" : "text-[13px] leading-relaxed"}`}
          >
            <CaptionText message={message} caption={caption} />
          </p>
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
