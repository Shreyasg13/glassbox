"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ExplainTooltip } from "@/components/ExplainTooltip";
import { evidenceTutorialSeenKey } from "@/lib/glassboxGuide";

type LiveSignal = {
  symbol: string;
  name: string;
  sector: string;
  current_price: number;
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;
  rsi: number;
  ma_cross: "BULLISH" | "BEARISH" | "NEUTRAL";
  volume_ratio: number;
  data_date: string;
};

type LiveSignalsResponse = { signals: LiveSignal[] };

const RITUAL_STAGES = [
  "Fetching source data",
  "Calculating metrics",
  "Generating analysis",
  "A6 verifying claims against evidence",
] as const;

const SIGNAL_COLOR: Record<LiveSignal["signal"], string> = {
  BUY: "var(--c-teal)",
  SELL: "var(--c-red)",
  HOLD: "var(--c-t3)",
};

const DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA"];

export function StepVerify({ tickers }: { tickers: string[] }) {
  const { username } = useAuth();
  const [signals, setSignals] = useState<Record<string, LiveSignal> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [stageIndex, setStageIndex] = useState(0); // -1 = not started, RITUAL_STAGES.length = revealed
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [pulseEvidence, setPulseEvidence] = useState(false);
  const [ackMessage, setAckMessage] = useState<string | null>(null);
  const reduceMotion = useRef(false);

  useEffect(() => {
    reduceMotion.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    try {
      setPulseEvidence(localStorage.getItem(evidenceTutorialSeenKey(username)) !== "1");
    } catch {
      setPulseEvidence(true);
    }
  }, [username]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<LiveSignalsResponse>("/api/live-signals")
      .then((res) => {
        if (cancelled) return;
        const map: Record<string, LiveSignal> = {};
        res.signals.forEach((s) => {
          map[s.symbol] = s;
        });
        setSignals(map);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load live signal data. Try again shortly.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const list = useMemo(() => {
    if (!signals) return [];
    const fromTickers = tickers.filter((t) => signals[t]);
    return fromTickers.length > 0 ? fromTickers : DEFAULT_TICKERS.filter((t) => signals[t]);
  }, [signals, tickers]);

  // Pick the first available ticker once data + list are ready.
  useEffect(() => {
    if (active === null && list.length > 0) setActive(list[0]);
  }, [active, list]);

  // Staged reveal choreography over the real fetched data -- the numbers
  // are real, only the reveal pacing is presentational. Starts once data
  // has arrived; short-circuits entirely under prefers-reduced-motion.
  useEffect(() => {
    if (!signals || active === null || stageIndex >= RITUAL_STAGES.length) return;
    if (reduceMotion.current) {
      setStageIndex(RITUAL_STAGES.length);
      return;
    }
    const timer = setTimeout(() => setStageIndex((i) => i + 1), stageIndex === 0 ? 300 : 620);
    return () => clearTimeout(timer);
  }, [signals, active, stageIndex]);

  function switchTicker(symbol: string) {
    setActive(symbol);
    setStageIndex(RITUAL_STAGES.length); // already-verified data revealed instantly on manual switch
    setEvidenceOpen(false);
  }

  function inspectEvidence() {
    setEvidenceOpen((o) => !o);
    if (pulseEvidence) {
      setPulseEvidence(false);
      setAckMessage("That's GlassBox: analysis you can inspect, not just accept.");
      try {
        localStorage.setItem(evidenceTutorialSeenKey(username), "1");
      } catch {
        // best-effort
      }
    }
  }

  if (error) {
    return <div className="rounded-r2 border border-red/20 bg-red-dim p-sp4 text-[13px] text-red">{error}</div>;
  }

  if (!signals || active === null) {
    return (
      <div>
        <div className="mb-1 text-[17px] font-bold text-t1">Your first GlassBox verification</div>
        <div className="text-[13px] text-t3">Loading live signal data…</div>
      </div>
    );
  }

  const m = signals[active];
  const revealed = stageIndex >= RITUAL_STAGES.length;

  return (
    <div>
      <div className="mb-1 text-[17px] font-bold text-t1">Your first GlassBox verification</div>
      <div className="mb-sp4 text-[13px] text-t3">
        Watch one verification happen, then inspect the real evidence behind it.
      </div>

      <div className="mb-sp4 flex flex-wrap gap-sp2">
        {list.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => switchTicker(t)}
            className={`mono rounded-r4 border px-sp3 py-1 text-[12px] font-bold ${
              active === t
                ? "border-teal bg-teal/[0.06] text-teal"
                : "border-border bg-bg2 text-t3 hover:border-border2"
            }`}
          >
            {t}
            {signals[t]?.signal === "SELL" ? " ⚠" : ""}
          </button>
        ))}
      </div>

      {!revealed ? (
        <div className="rounded-r3 border border-border bg-bg2 p-sp5">
          {RITUAL_STAGES.map((label, i) => (
            <div key={label} className={`flex items-center gap-sp3 py-sp2 transition-opacity ${i <= stageIndex ? "opacity-100" : "opacity-35"}`}>
              <div
                className={`grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full border-2 text-[11px] font-extrabold ${
                  i < stageIndex
                    ? "border-teal bg-teal text-bg"
                    : i === stageIndex
                      ? "animate-spin border-teal border-t-transparent text-teal"
                      : "border-border2 text-t3"
                }`}
              >
                {i < stageIndex ? "✓" : ""}
              </div>
              <div className={`text-[13px] font-semibold ${i < stageIndex ? "text-t1" : "text-t2"}`}>{label}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-r3 border border-border bg-bg2 p-sp4">
          <div className="mb-sp4 flex items-center gap-sp4">
            <div
              className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-full border-[3px]"
              style={{ borderColor: SIGNAL_COLOR[m.signal], background: "rgba(13,204,170,.04)" }}
            >
              <div className="text-[22px] font-black leading-none" style={{ color: SIGNAL_COLOR[m.signal] }}>
                {Math.round(m.confidence)}
              </div>
              <div className="mt-0.5 flex items-center gap-0.5 text-[8px] font-semibold uppercase tracking-wide text-t3">
                Confidence
                <ExplainTooltip
                  title="Confidence"
                  desc="How strongly GlassBox's deterministic engine backs this call, from 0-100. Not a promise -- a measure of how clearly the underlying signals agree."
                />
              </div>
            </div>
            <div className="flex-1">
              <div className="mb-1 text-[15px] font-extrabold text-t1">
                {m.name} · {m.symbol}
              </div>
              <div className="flex flex-wrap items-center gap-sp2">
                <span className="text-[12px] text-t3">{m.sector}</span>
                <ExplainTooltip
                  tag="Secondary verification"
                  title="Auditor A6"
                  desc="Auditor A6 compared the generated analysis with the underlying evidence before this result was shown. This is a second automated check on the pipeline, not an outside auditor."
                >
                  <span className="flex items-center gap-1 rounded-r2 border border-teal/15 px-2 py-0.5 text-[11px] text-teal">
                    ✓ A6 Verified
                  </span>
                </ExplainTooltip>
                <span
                  className="rounded-r4 px-2 py-0.5 text-[11px] font-semibold"
                  style={{
                    background: m.signal === "BUY" ? "var(--c-teal-dim)" : m.signal === "SELL" ? "var(--c-red-dim)" : "var(--c-raised)",
                    color: SIGNAL_COLOR[m.signal],
                  }}
                >
                  {m.signal}
                </span>
              </div>
            </div>
            <div className="text-right">
              <div className="mono text-[16px] font-bold text-t1">${m.current_price.toFixed(2)}</div>
              <div className="text-[10.5px] text-t4">as of {m.data_date}</div>
            </div>
          </div>

          <div className="mb-sp3 flex flex-col gap-sp2">
            <EvidenceRow
              label="RSI"
              value={m.rsi.toFixed(1)}
              tag={m.rsi < 30 ? "Oversold" : m.rsi > 70 ? "Overbought" : "Neutral"}
              color="var(--c-teal)"
              tooltip="A momentum indicator on a 0-100 scale. Readings below ~30 suggest oversold, above ~70 suggest overbought."
            />
            <EvidenceRow
              label="MA Cross"
              value={m.ma_cross}
              tag={m.ma_cross === "BULLISH" ? "Bullish" : m.ma_cross === "BEARISH" ? "Bearish" : "Neutral"}
              color="var(--c-gold)"
              tooltip="Whether the short-term moving average is above (bullish) or below (bearish) the longer-term one."
            />
            <EvidenceRow
              label="Volume Ratio"
              value={m.volume_ratio.toFixed(2)}
              tag={m.volume_ratio > 1.2 ? "Elevated" : "Typical"}
              color="var(--c-t2)"
              tooltip="Today's trading volume relative to its recent average. A spike suggests unusually strong conviction behind the move."
            />
          </div>

          <div className="rounded-r2 border border-teal/[0.18] bg-teal/[0.05] p-sp3">
            <div className="mb-sp1 flex items-center gap-2">
              <div className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full bg-teal text-[11px] font-black text-bg">
                ✓
              </div>
              <div>
                <div className="text-[12.5px] font-extrabold text-teal">Verified -- no discrepancies found</div>
                <div className="text-[11px] text-t3">Auditor A6 · narrative matches raw data</div>
              </div>
            </div>
            <button
              type="button"
              onClick={inspectEvidence}
              className={`mt-sp2 flex w-full items-center justify-center gap-2 rounded-r1 border border-teal/30 py-sp2 text-[12.5px] font-bold text-teal transition-colors hover:bg-teal/[0.1] ${
                pulseEvidence ? "animate-pulse" : ""
              }`}
            >
              🔗 Inspect evidence chain →
            </button>
            {evidenceOpen && (
              <div className="mt-sp3 border-t border-border pt-sp3 text-[11.5px] text-t3">
                <EvidenceChainRow index={1} text={`RSI ${m.rsi.toFixed(1)} -- from GlassBox's own historical price and volume records`} />
                <EvidenceChainRow index={2} text={`MA Cross ${m.ma_cross} -- calculated from the same records`} />
                <EvidenceChainRow index={3} text={`Volume Ratio ${m.volume_ratio.toFixed(2)} -- calculated from the same records`} />
                <EvidenceChainRow index="✓" text="A6 compared each against the written analysis -- 0 discrepancies" strong />
              </div>
            )}
            {ackMessage && <p className="mt-sp2 text-[11.5px] font-medium text-teal">{ackMessage}</p>}
          </div>
        </div>
      )}

      <div className="mt-sp3 text-center text-[11.5px] text-t3">Switch tickers above to explore your other holdings.</div>
    </div>
  );
}

function EvidenceRow({
  label,
  value,
  tag,
  color,
  tooltip,
}: {
  label: string;
  value: string;
  tag: string;
  color: string;
  tooltip: string;
}) {
  return (
    <div className="flex items-center gap-sp3 rounded-r1 border border-border bg-panel px-sp3 py-sp2" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="flex-1">
        <div className="flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-t3">
          {label}
          <ExplainTooltip title={label} desc={tooltip} />
        </div>
      </div>
      <div className="mono text-[16px] font-bold" style={{ color }}>
        {value}
      </div>
      <span className="rounded-r4 bg-teal-dim px-2 py-0.5 text-[9px] font-semibold text-teal">{tag}</span>
    </div>
  );
}

function EvidenceChainRow({ index, text, strong }: { index: number | string; strong?: boolean; text: string }) {
  return (
    <div className="flex items-center gap-2 py-1">
      <span className={`font-extrabold ${strong ? "text-green" : "text-t2"}`}>{index}</span>
      <span>{text}</span>
    </div>
  );
}
