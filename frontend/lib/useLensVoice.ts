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
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cacheRef = useRef<Map<string, string>>(new Map()); // speakerId -> object URL
  const requestIdRef = useRef(0);

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
    if (!next) {
      audioRef.current?.pause();
    }
    setSharedEnabled(next);
  }, []);

  const stop = useCallback(() => {
    audioRef.current?.pause();
  }, []);

  const speak = useCallback(async (personaId: string, text: string, voiceId: string, onEnded?: () => void) => {
    audioRef.current?.pause();
    setUnavailable(false);

    const cached = cacheRef.current.get(personaId);
    if (cached) {
      const audio = new Audio(cached);
      if (onEnded) {
        audio.addEventListener("ended", onEnded);
        audio.addEventListener("pause", onEnded);
      }
      audioRef.current = audio;
      audio.play().catch(() => {
        // Autoplay can still be blocked by the browser even after an
        // earlier user gesture enabled the toggle -- fail silently,
        // the text is already visible via the typewriter effect.
        onEnded?.();
      });
      return;
    }

    const myRequestId = ++requestIdRef.current;
    try {
      const res = await fetch(apiUrl("/api/tts"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice_id: voiceId }),
      });
      // A newer request superseded this one (user already moved on) --
      // drop the result rather than playing stale/out-of-order audio.
      if (myRequestId !== requestIdRef.current) return;
      if (!res.ok) {
        setUnavailable(true);
        onEnded?.();
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      cacheRef.current.set(personaId, url);
      const audio = new Audio(url);
      if (onEnded) {
        audio.addEventListener("ended", onEnded);
        audio.addEventListener("pause", onEnded);
      }
      audioRef.current = audio;
      audio.play().catch(() => onEnded?.());
    } catch {
      if (myRequestId === requestIdRef.current) {
        setUnavailable(true);
        onEnded?.();
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      cacheRef.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  return { enabled, toggle, speak, stop, unavailable };
}
