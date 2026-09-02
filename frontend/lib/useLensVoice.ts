"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "./api";

const STORAGE_KEY = "glassbox_lens_voices_enabled";

/**
 * Text-to-speech playback for the Strategy Lenses carousel. Off by
 * default (audio must never autoplay without explicit opt-in) --
 * persists the user's choice in localStorage so it's remembered on
 * return visits. Caches fetched audio blobs per persona for the
 * session's lifetime so switching back to an already-played persona
 * doesn't re-fetch.
 */
export function useLensVoice() {
  const [enabled, setEnabled] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cacheRef = useRef<Map<string, string>>(new Map()); // personaId -> object URL
  const requestIdRef = useRef(0);

  useEffect(() => {
    try {
      setEnabled(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      // ignore inaccessible storage, default stays off
    }
  }, []);

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        // storage unavailable, session-only toggle still works
      }
      if (!next) {
        audioRef.current?.pause();
      }
      return next;
    });
  }, []);

  const stop = useCallback(() => {
    audioRef.current?.pause();
  }, []);

  const speak = useCallback(async (personaId: string, text: string, voiceId: string) => {
    audioRef.current?.pause();
    setUnavailable(false);

    const cached = cacheRef.current.get(personaId);
    if (cached) {
      const audio = new Audio(cached);
      audioRef.current = audio;
      audio.play().catch(() => {
        // Autoplay can still be blocked by the browser even after an
        // earlier user gesture enabled the toggle -- fail silently,
        // the text is already visible via the typewriter effect.
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
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      cacheRef.current.set(personaId, url);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.play().catch(() => {});
    } catch {
      if (myRequestId === requestIdRef.current) setUnavailable(true);
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
