"use client";

/**
 * Small animated waveform shown while TTS audio is playing -- shared by
 * SignalTicker, Hero's demo card, and StrategyLenses so "something is
 * speaking" reads the same way everywhere. Pure CSS bar animation (no
 * dependency on decoding real audio levels), respects
 * prefers-reduced-motion by falling back to a static (non-animated) icon.
 */
export function SpeakingIndicator({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-end gap-[2px] ${className}`} aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className="w-[2.5px] rounded-full bg-teal motion-safe:animate-speak-wave motion-reduce:h-[6px]"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  );
}
