"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { apiUrl } from "./api";

const STORAGE_KEY = "glassbox_lens_voices_enabled";

// Shared "voice enabled" flag via useSyncExternalStore rather than
// per-hook-instance useState. This feature is used on the same page in
// more than one place at once now (Hero's demo card AND Strategy Lenses
// both live on the marketing landing page) -- with independent useState,
// toggling voice on in one component wouldn't be reflected in the other
// until a reload, which is a real, visible inconsistency, not a
// theoretical one. One module-level store + subscribers keeps every
// useLensVoice() call on the page in sync immediately.
let sharedEnabled = false;
const listeners = new Set<() => void>();

function readInitialEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function setSharedEnabled(next: boolean) {
  sharedEnabled = next;
  try {
    localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
  } catch {
    // storage unavailable -- in-memory value still updates for this session
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return sharedEnabled;
}

function getServerSnapshot() {
  return false;
}

/**
 * Text-to-speech playback -- used by the Strategy Lenses carousel, the
 * marketing Hero demo card, and the dashboard's live signal ticker. Off
 * by default (audio must never autoplay without explicit opt-in) --
 * persists the user's choice in localStorage so it's remembered on
 * return visits, and shared live across every component on the page via
 * useSyncExternalStore (see above). Caches fetched audio blobs per
 * "speaker id" for the session's lifetime so replaying an
 * already-spoken line doesn't re-fetch.
 */
export function useLensVoice() {
  const enabled = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const [unavailable, setUnavailable] = useState(false);
  // ONE persistent <audio> element reused for every speak() call, not a
  // fresh `new Audio()` per call -- required for reliable playback on
  // mobile Safari/WebKit. Those browsers only allow .play() when it's
  // attributable to a real user gesture; an element "unlocked" by a
  // gesture-synchronous play/pause (see primeAudio below) stays unlocked
  // for ITS OWN lifetime, but a brand-new element created later (e.g.
  // inside an async fetch callback, or from autoplay's setInterval with
  // no gesture at all) does not inherit that unlock. Reusing one element
  // across every call, primed once on the first real click, is the
  // standard cross-browser fix for this class of bug.
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const primedRef = useRef(false);
  const cacheRef = useRef<Map<string, string>>(new Map()); // speakerId -> object URL
  const requestIdRef = useRef(0);

  function getAudioElement(): HTMLAudioElement {
    if (!audioRef.current) audioRef.current = new Audio();
    return audioRef.current;
  }

  /** Call SYNCHRONOUSLY (no `await` before it) from inside a real click
   * handler -- priming after an `await` defeats the whole point, since
   * strict mobile browsers attribute a gesture only to code still on the
   * original call stack. Idempotent: only actually primes once. */
  const primeAudio = useCallback(() => {
    if (primedRef.current) return;
    primedRef.current = true;
    try {
      const el = getAudioElement();
      const p = el.play();
      // A source-less element's play() rejects (nothing to play) --
      // that's fine and expected, the attempt itself is what registers
      // the gesture-unlock on this element for later, real playback.
      if (p && typeof p.catch === "function") p.catch(() => {});
      el.pause();
    } catch {
      // Some older WebKit versions throw synchronously here instead of
      // rejecting a promise -- either way, priming is best-effort; a
      // failure here just means speak() falls back to whatever the
      // browser's normal (possibly stricter) autoplay policy allows.
    }
  }, []);

  // One-time hydration of the module-level store from localStorage --
  // only the first mounted instance on a page actually needs to do this
  // (subsequent instances read the already-hydrated `sharedEnabled`), but
  // running it on every mount is idempotent and cheap, so no gating logic.
  useEffect(() => {
    setSharedEnabled(readInitialEnabled());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = useCallback(() => {
    const next = !sharedEnabled;
    if (next) {
      // Turning voice ON is always a direct click -- prime here so the
      // persistent element is unlocked before any later, possibly
      // non-gesture-triggered (autoplay) speak() call needs it.
      primeAudio();
    } else {
      audioRef.current?.pause();
      try {
        window.speechSynthesis?.cancel();
      } catch {
        // speechSynthesis unsupported -- nothing to cancel
      }
    }
    setSharedEnabled(next);
  }, [primeAudio]);

  const stop = useCallback(() => {
    audioRef.current?.pause();
    try {
      window.speechSynthesis?.cancel();
    } catch {
      // speechSynthesis unsupported -- nothing to cancel
    }
  }, []);

  /** Last-resort fallback when BOTH server providers (ElevenLabs, then
   * Kokoro/Hugging Face) are unavailable -- most commonly because a
   * free-tier credit quota ran out on one or both, which has now
   * happened to both providers independently. A third server-side API
   * key would just be a third finite quota; the browser's own built-in
   * speech synthesis has no external quota to exhaust at all. This is a
   * genuine degradation, not a like-for-like replacement: it uses
   * whatever default voice/OS the visitor's browser ships (not the
   * per-persona ElevenLabs/Kokoro voice ids -- SpeechSynthesisUtterance
   * has no concept of those), so every persona sounds the same instead
   * of distinct. That tradeoff is deliberate -- degraded shared audio
   * beats total silence when the primary/secondary providers are down.
   * Returns false (caller falls through to the "unavailable" state) only
   * if the browser has no speechSynthesis support at all. */
  function speakViaBrowser(text: string, onEnded?: () => void): boolean {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      if (onEnded) {
        utterance.onend = onEnded;
        utterance.onerror = onEnded;
      }
      window.speechSynthesis.speak(utterance);
      return true;
    } catch {
      return false;
    }
  }

  const speak = useCallback(
    async (
      personaId: string,
      text: string,
      elevenLabsVoiceId: string,
      kokoroVoiceId: string,
      onEnded?: () => void,
      // Real playback progress (0..1), driven by the actual <audio>
      // element's currentTime/duration via the native `timeupdate` event
      // -- not a guessed/estimated timer. Used by GuideBubble's live
      // word-by-word caption sweep so the highlight tracks genuine
      // ElevenLabs/Kokoro audio, not an assumed speaking rate.
      onProgress?: (fraction: number) => void
    ) => {
      const el = getAudioElement();
      el.pause();
      // Clear any handlers from a previous speak() call on this shared
      // element before attaching new ones, so a superseded call's
      // onEnded/onProgress can't fire late against the wrong persona/row.
      el.onended = null;
      el.onpause = null;
      el.ontimeupdate = null;
      try {
        // Cancel any in-flight browser-fallback utterance from a
        // previous speak() call too -- same reasoning as el.pause() above.
        window.speechSynthesis?.cancel();
      } catch {
        // speechSynthesis unsupported -- nothing to cancel
      }
      setUnavailable(false);

      function playUrl(url: string) {
        if (onEnded) {
          el.onended = onEnded;
          el.onpause = onEnded;
        }
        if (onProgress) {
          el.ontimeupdate = () => {
            onProgress(el.duration ? el.currentTime / el.duration : 0);
          };
        }
        el.src = url;
        const p = el.play();
        if (p && typeof p.catch === "function") {
          p.catch(() => {
            // Autoplay can still be blocked by the browser even after an
            // earlier user gesture primed this element (e.g. this call
            // itself isn't gesture-attributable, such as autoplay's
            // setInterval-driven advance) -- fail silently, the text is
            // already visible via the typewriter effect.
            onEnded?.();
          });
        }
      }

      const cached = cacheRef.current.get(personaId);
      if (cached) {
        playUrl(cached);
        return;
      }

      const myRequestId = ++requestIdRef.current;
      try {
        const res = await fetch(apiUrl("/api/tts"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text,
            elevenlabs_voice_id: elevenLabsVoiceId,
            kokoro_voice_id: kokoroVoiceId,
          }),
        });
        // A newer request superseded this one (user already moved on) --
        // drop the result rather than playing stale/out-of-order audio.
        if (myRequestId !== requestIdRef.current) return;
        if (!res.ok) {
          if (!speakViaBrowser(text, onEnded)) {
            setUnavailable(true);
            onEnded?.();
          }
          return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        cacheRef.current.set(personaId, url);
        playUrl(url);
      } catch {
        if (myRequestId === requestIdRef.current) {
          if (!speakViaBrowser(text, onEnded)) {
            setUnavailable(true);
            onEnded?.();
          }
        }
      }
    },
    []
  );

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      cacheRef.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  // Exposed so consumers can prime synchronously inside their OWN click
  // handlers too, not just this hook's toggle(). Needed for a real gap:
  // if voice was already enabled from a previous session (persisted in
  // localStorage), toggle() never fires this session at all -- the very
  // first interaction might be clicking a per-row "speak" button
  // directly, which must still prime before its own async speak() call.
  return { enabled, toggle, speak, stop, unavailable, primeAudio };
}
