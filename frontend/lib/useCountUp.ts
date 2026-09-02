"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Animates a number from 0 to `target` once its element scrolls into
 * view. Returns a ref to attach to the trigger element and the current
 * formatted display value. Respects prefers-reduced-motion by jumping
 * straight to the final value.
 */
export function useCountUp(target: number, opts: { duration?: number; decimals?: number } = {}) {
  const { duration = 1200, decimals = 0 } = opts;
  const ref = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduceMotion =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || started.current) return;
        started.current = true;
        observer.disconnect();

        if (reduceMotion || target === 0) {
          setValue(target);
          return;
        }

        const start = performance.now();
        function tick(now: number) {
          const progress = Math.min((now - start) / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          setValue(target * eased);
          if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
      },
      { threshold: 0.4 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [target, duration]);

  return { ref, display: value.toFixed(decimals) };
}
