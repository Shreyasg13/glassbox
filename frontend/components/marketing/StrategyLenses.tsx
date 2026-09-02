"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import { Reveal } from "@/components/Reveal";
import { useLensVoice } from "@/lib/useLensVoice";
import { LENS_FILTERS, LENS_PERSONAS, type LensFilter, type LensPersona } from "./lensData";
import { LensPortrait } from "./lensPortrait";

const AUTOPLAY_MS = 4200;
const TYPE_MS_PER_CHAR = 18;

function growthColor(growth: number): string {
  if (growth >= 70) return "text-green";
  if (growth >= 50) return "text-gold";
  return "text-t3";
}
function riskColor(risk: number): string {
  if (risk <= 25) return "text-green";
  if (risk <= 45) return "text-gold";
  return "text-red";
}
function barBg(colorClass: string): string {
  // matches growthColor/riskColor text-* tokens to a bg-* fill
  if (colorClass === "text-green") return "bg-green";
  if (colorClass === "text-gold") return "bg-gold";
  if (colorClass === "text-red") return "bg-red";
  return "bg-t3";
}

export function StrategyLenses() {
  const reduceMotion = useReducedMotion();
  const [filter, setFilter] = useState<"all" | LensFilter>("all");
  const [cur, setCur] = useState(0);
  const [autoplay, setAutoplay] = useState(true);
  const [typedText, setTypedText] = useState("");
  const typeTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const dragStartX = useRef<number | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const voice = useLensVoice();

  const view = filter === "all" ? LENS_PERSONAS : LENS_PERSONAS.filter((a) => a.cls === filter);
  const active: LensPersona | undefined = view[cur];

  // reset to first card whenever the filtered set changes
  useEffect(() => {
    setCur(0);
  }, [filter]);

  // typewriter effect for the active persona's story
  useEffect(() => {
    if (typeTimer.current) clearInterval(typeTimer.current);
    if (!active) return;
    if (reduceMotion) {
      setTypedText(active.story);
      return;
    }
    setTypedText("");
    let i = 0;
    typeTimer.current = setInterval(() => {
      i += 1;
      setTypedText(active.story.slice(0, i));
      if (i >= active.story.length && typeTimer.current) {
        clearInterval(typeTimer.current);
      }
    }, TYPE_MS_PER_CHAR);
    return () => {
      if (typeTimer.current) clearInterval(typeTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.id, reduceMotion]);

  // voice playback, loosely synced with the typewriter above -- starts
  // around the same time the text starts revealing, no word-level sync
  useEffect(() => {
    if (!active || !voice.enabled) return;
    voice.speak(active.id, active.story, active.voiceId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.id, voice.enabled]);

  // autoplay
  useEffect(() => {
    if (!autoplay || view.length <= 1) return;
    const id = setInterval(() => {
      setCur((c) => (c + 1) % view.length);
    }, AUTOPLAY_MS);
    return () => clearInterval(id);
  }, [autoplay, view.length]);

  // keyboard nav
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") {
        setCur((c) => (c + 1) % view.length);
        setAutoplay(false);
      } else if (e.key === "ArrowLeft") {
        setCur((c) => (c - 1 + view.length) % view.length);
        setAutoplay(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view.length]);

  function goTo(i: number) {
    setCur(i);
    setAutoplay(false);
  }
  function next() {
    setCur((c) => (c + 1) % view.length);
    setAutoplay(false);
  }
  function prev() {
    setCur((c) => (c - 1 + view.length) % view.length);
    setAutoplay(false);
  }

  function onPointerDown(e: React.PointerEvent) {
    dragStartX.current = e.clientX;
  }
  function onPointerUp(e: React.PointerEvent) {
    if (dragStartX.current === null) return;
    const dx = e.clientX - dragStartX.current;
    if (Math.abs(dx) > 60) (dx < 0 ? next() : prev());
    dragStartX.current = null;
  }

  return (
    <section id="strategy-lenses" className="scroll-mt-20 px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mx-auto max-w-[640px] text-center">
          <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-teal">The Strategy Lenses</div>
          <h2 className="mb-sp2 text-[32px] font-extrabold leading-tight tracking-tight text-t1">
            Eight legendary lenses. One audited score.
          </h2>
          <p className="text-[15px] leading-relaxed text-t2">
            Each lens is pretrained on a legendary investor&apos;s documented strategy and reads your holdings for
            growth and risk — every view traces back to the same audited data. Lenses inform; they never advise.
          </p>
        </div>
      </Reveal>

      {/* voice toggle -- off by default, never autoplays without this */}
      <div className="mt-sp6 flex justify-center">
        <button
          type="button"
          onClick={voice.toggle}
          aria-pressed={voice.enabled}
          className={`flex items-center gap-sp2 rounded-r4 border px-sp4 py-2 text-[12.5px] font-semibold transition-colors duration-200 ease-glass ${
            voice.enabled
              ? "border-transparent bg-teal text-bg shadow-teal"
              : "border-border bg-panel text-t2 hover:border-border2 hover:text-t1"
          }`}
        >
          <span aria-hidden>{voice.enabled ? "\u{1F50A}" : "\u{1F507}"}</span>
          {voice.enabled ? "Voices on" : "Enable voices"}
        </button>
      </div>
      {voice.enabled && voice.unavailable && (
        <p className="mono mt-sp2 text-center text-[11px] text-t4">Voice playback unavailable right now.</p>
      )}

      {/* filter chips */}
      <div className="mb-sp5 mt-sp5 flex flex-wrap justify-center gap-sp2">
        {LENS_FILTERS.map((f) => {
          const count = f.value === "all" ? LENS_PERSONAS.length : LENS_PERSONAS.filter((a) => a.cls === f.value).length;
          return (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilter(f.value)}
              className={`rounded-r4 border px-sp4 py-2 text-[13px] font-semibold transition-colors duration-200 ease-glass ${
                filter === f.value
                  ? "border-transparent bg-teal text-bg shadow-teal"
                  : "border-border bg-panel text-t2 hover:border-border2 hover:text-t1"
              }`}
            >
              {f.label} <span className="mono ml-1 text-[10px] opacity-70">{count}</span>
            </button>
          );
        })}
      </div>

      {/* progress dots */}
      <div className="mb-sp6 flex justify-center gap-sp2">
        {view.map((a, i) => (
          <button
            key={a.id}
            type="button"
            aria-label={`Go to ${a.name}`}
            onClick={() => goTo(i)}
            className={`h-[8px] rounded-full transition-all duration-300 ${
              i === cur ? "w-[28px] bg-teal" : "w-[8px] bg-raised hover:bg-panel2"
            }`}
          />
        ))}
      </div>

      {/* 3D carousel stage */}
      <div
        ref={stageRef}
        className="relative mt-sp3 select-none"
        style={{ perspective: "1600px", height: 520 }}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
      >
        <div className="relative h-full w-full" style={{ transformStyle: "preserve-3d" }}>
          {view.map((a, i) => {
            const n = view.length;
            let off = i - cur;
            if (off > n / 2) off -= n;
            if (off < -n / 2) off += n;
            const abs = Math.abs(off);
            const x = off * 150;
            const z = -abs * 220;
            const ry = off * -34;
            const opacity = abs > 2 ? 0 : 1 - abs * 0.28;
            const scale = 1 - abs * 0.06;
            const isActive = off === 0;
            const gCol = growthColor(a.growth);
            const rCol = riskColor(a.risk);
            const acVar = `var(--c-${a.color})`;

            return (
              <div
                key={a.id}
                onClick={() => goTo(i)}
                className="absolute left-1/2 top-1/2 w-[300px] cursor-pointer"
                style={{
                  transformStyle: "preserve-3d",
                  transform: `translate(-50%, -50%) translateX(${x}px) translateZ(${z}px) rotateY(${ry}deg) scale(${scale})`,
                  opacity,
                  zIndex: 100 - abs,
                  filter: abs ? `brightness(${1 - abs * 0.18})` : "none",
                  transition: reduceMotion
                    ? "opacity .3s ease"
                    : "transform .7s var(--ease), opacity .6s var(--ease), filter .6s var(--ease)",
                }}
              >
                <div
                  className={`glass-panel-raised relative overflow-hidden p-sp5 ${isActive ? "shadow-lg2" : ""}`}
                  style={{ borderColor: acVar }}
                >
                  {a.rank && (
                    <div className="absolute left-3 top-3 rounded-r1 border border-border bg-black/45 px-sp2 py-[3px] text-[10px] font-extrabold text-t2">
                      {a.rank}
                    </div>
                  )}
                  {a.lead && (
                    <div className="absolute right-0 top-0 rounded-bl-r2 bg-teal px-sp3 py-1 text-[9px] font-bold text-bg">
                      LEAD LENS
                    </div>
                  )}

                  <div className="relative mx-auto mb-sp3 mt-sp2 h-[120px] w-[120px]">
                    <LensPortrait id={a.id} look={a.look} colorToken={a.color} />
                    <div className="absolute bottom-1 right-3 grid h-[26px] w-[26px] place-items-center rounded-full border-2 border-panel bg-teal text-[12px] font-black text-bg">
                      ✓
                    </div>
                  </div>

                  <div className="text-center text-[20px] font-black text-t1">{a.name}</div>
                  <div className="mono mt-sp1 text-center text-[10px] font-bold uppercase tracking-wide" style={{ color: acVar }}>
                    {a.title}
                  </div>

                  <div className="mt-sp3 rounded-r2 bg-black/25 p-sp3 text-center text-[11px] text-t3">
                    Pretrained on <b className="text-t2">{a.inspiredName}</b>
                    <br />
                    <span className="font-semibold" style={{ color: acVar }}>
                      {a.firm}
                    </span>{" "}
                    · {a.strat}
                    <div className="mono mt-sp1 text-[11px] font-bold text-green">📈 {a.track}</div>
                  </div>

                  <div className="mt-sp4 flex flex-col gap-sp1">
                    <div className="flex items-center gap-sp2 text-[11px]">
                      <span className="mono w-[48px] shrink-0 text-[9px] uppercase text-t3">Growth</span>
                      <span className="h-[6px] flex-1 overflow-hidden rounded-full bg-white/[.06]">
                        <span
                          className={`block h-full rounded-full transition-[width] duration-1000 ease-glass ${barBg(gCol)}`}
                          style={{ width: isActive ? `${a.growth}%` : "0%" }}
                        />
                      </span>
                      <span className={`mono w-[26px] shrink-0 text-right text-[11px] font-bold ${gCol}`}>{a.growth}</span>
                    </div>
                    <div className="flex items-center gap-sp2 text-[11px]">
                      <span className="mono w-[48px] shrink-0 text-[9px] uppercase text-t3">Risk</span>
                      <span className="h-[6px] flex-1 overflow-hidden rounded-full bg-white/[.06]">
                        <span
                          className={`block h-full rounded-full transition-[width] duration-1000 ease-glass ${barBg(rCol)}`}
                          style={{ width: isActive ? `${a.risk}%` : "0%" }}
                        />
                      </span>
                      <span className={`mono w-[26px] shrink-0 text-right text-[11px] font-bold ${rCol}`}>{a.risk}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* speech bubble */}
        {active && (
          <div
            className="absolute left-1/2 z-20 w-[340px] max-w-[86vw] -translate-x-1/2 rounded-r3 border p-sp4 shadow-lg2"
            style={{
              bottom: "-4px",
              transform: "translate(-50%, calc(100% + 14px))",
              borderColor: `var(--c-${active.color})`,
              background: "linear-gradient(160deg, rgba(23,32,53,.96), rgba(13,20,34,.96))",
            }}
          >
            <div className="mb-sp2 flex items-center gap-sp2">
              <div
                className="mono grid h-[26px] w-[26px] shrink-0 place-items-center rounded-r2 text-[13px] font-extrabold"
                style={{ background: `var(--c-${active.color}-dim)`, color: `var(--c-${active.color})` }}
              >
                {active.code}
              </div>
              <div className="text-[12px] font-extrabold text-t1">
                {active.inspiredName} — {active.title}
              </div>
            </div>
            <p className="min-h-[60px] text-[13px] italic leading-relaxed text-t1">
              {typedText}
              <span className="ml-[1px] inline-block h-[14px] w-[2px] animate-pulse bg-current align-middle" />
            </p>
          </div>
        )}
      </div>

      {/* nav controls */}
      <div className="mt-[130px] flex justify-center gap-sp4">
        <button
          type="button"
          onClick={prev}
          aria-label="Previous lens"
          className="grid h-[46px] w-[46px] place-items-center rounded-full border border-border2 bg-panel text-[18px] text-t1 transition-all duration-200 ease-glass hover:scale-105 hover:border-teal hover:text-teal"
        >
          ‹
        </button>
        <button
          type="button"
          onClick={() => setAutoplay((p) => !p)}
          className="mono flex items-center gap-sp2 rounded-full border border-border2 bg-panel px-sp4 text-[12px] font-bold text-t1 transition-all duration-200 ease-glass hover:border-teal hover:text-teal"
        >
          {autoplay ? "⏸ auto" : "▶ play"}
        </button>
        <button
          type="button"
          onClick={next}
          aria-label="Next lens"
          className="grid h-[46px] w-[46px] place-items-center rounded-full border border-border2 bg-panel text-[18px] text-t1 transition-all duration-200 ease-glass hover:scale-105 hover:border-teal hover:text-teal"
        >
          ›
        </button>
      </div>
      <p className="mono mt-sp5 text-center text-[12px] text-t4">
        click a lens to hear its story · drag / arrows to slide · filter to spin the desk
      </p>

      {/* mandatory disclaimer -- see docs/design-reference/README.md */}
      <div className="mx-auto mt-sp8 max-w-[960px] rounded-r3 border border-gold/20 bg-gold-dim p-sp4 text-[11.5px] leading-relaxed text-t2">
        <b className="text-gold">⚠ Important:</b> Glass Box is a financial research and data-verification tool. It
        does <b>not</b> constitute investment advice; all scores are informational. The Strategy Lenses are{" "}
        <b>original AI archetypes</b> that study the publicly documented philosophies of well-known investors —
        named as <b>inspiration only</b>. Glass Box is <b>not affiliated with, endorsed by, or representing</b> any
        named investor or firm, and portraits are original illustrations, <b>not likenesses</b>. Track-record
        figures are historical facts about each investor&apos;s public record, not a promise of Glass Box
        performance.
      </div>
    </section>
  );
}
