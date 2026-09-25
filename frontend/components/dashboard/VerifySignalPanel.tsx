"use client";

import { useCallback, useEffect, useState } from "react";
import { GlassPanel } from "@/components/GlassPanel";
import { useAuth } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api";

type LiveSignal = {
  symbol: string;
  name: string;
  sector: string;
  current_price: number;
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;
  rsi: number;
  ma_cross: "BULLISH" | "BEARISH" | "NEUTRAL";
  data_date: string;
};

type Entitlements = { limit: number; used: number; remaining: number };

type VerifiedSignalResponse = {
  signal: LiveSignal;
  verified_at: string;
  entitlements: Entitlements;
  disclaimer: string;
};

const SIGNAL_COLOR: Record<LiveSignal["signal"], string> = {
  BUY: "text-teal",
  SELL: "text-red",
  HOLD: "text-t3",
};

// Real 15-symbol universe this account's plan actually covers today
// (backend/app/data_source.py's STOCK_INFO) -- quick-pick chips, not an
// exhaustive ticker search (that doesn't exist yet).
const QUICK_PICK = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "SPY", "QQQ"];

/**
 * The real, backend-enforced counterpart to the marketing site's "5 free
 * verified signals" pitch (Plan-correction.MD) -- this is where that
 * quota actually lives and gets spent, via POST /api/me/verify/:ticker
 * (backend/app/routers/me.py). Each verification returns GlassBox's
 * real deterministic signal (RSI/moving-average-cross computed from
 * real historical prices), not the fuller narrated A6 audit trail --
 * that's still Phase 7, not built, so this deliberately doesn't claim
 * more than it delivers (see the response's own `disclaimer`).
 */
export function VerifySignalPanel() {
  const { token } = useAuth();
  const [ticker, setTicker] = useState("");
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [result, setResult] = useState<VerifiedSignalResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<Entitlements>("/api/me/entitlements", { token })
      .then(setEntitlements)
      .catch(() => setEntitlements(null));
  }, [token]);

  const verify = useCallback(
    async (symbol: string) => {
      if (!token || !symbol.trim()) return;
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<VerifiedSignalResponse>(`/api/me/verify/${symbol.trim().toUpperCase()}`, {
          method: "POST",
          token,
        });
        setResult(data);
        setEntitlements(data.entitlements);
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.status === 402
              ? "You've used all 5 free verified signals. Upgrade to keep verifying holdings."
              : err.message
            : "Verification failed"
        );
      } finally {
        setLoading(false);
      }
    },
    [token]
  );

  const atLimit = entitlements !== null && entitlements.remaining <= 0;

  return (
    <GlassPanel variant="frost">
      <div className="mb-sp1 flex items-center justify-between">
        <h2 className="text-[15px] font-bold text-t1">Verify a Signal</h2>
        {entitlements && (
          <span className={`mono text-[10.5px] ${atLimit ? "text-gold" : "text-t3"}`}>
            {entitlements.remaining} of {entitlements.limit} free left
          </span>
        )}
      </div>
      <p className="mb-sp4 text-[11.5px] text-t3">
        Real signal, real data: RSI and moving-average cross computed from historical prices for
        any of GlassBox&apos;s covered symbols.
      </p>

      {atLimit ? (
        <div className="rounded-r2 border border-gold/20 bg-gold-dim p-sp4 text-[12.5px] text-t2">
          You&apos;ve used all {entitlements!.limit} free verified signals. Upgrade for unlimited
          verification.
        </div>
      ) : (
        <>
          <div className="mb-sp3 flex flex-wrap gap-sp2">
            {QUICK_PICK.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => {
                  setTicker(s);
                  verify(s);
                }}
                disabled={loading}
                className="mono rounded-r4 border border-border bg-bg2 px-sp3 py-1 text-[12px] font-bold text-t3 hover:border-teal hover:text-teal"
              >
                {s}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              verify(ticker);
            }}
            className="mb-sp4 flex gap-sp2"
          >
            <input
              className="input"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="Ticker symbol…"
            />
            <button type="submit" className="btn btn-primary shrink-0" disabled={loading || !ticker.trim()}>
              {loading ? "Verifying…" : "Verify →"}
            </button>
          </form>
        </>
      )}

      {error && <p className="mb-sp3 text-[12px] font-semibold text-red">{error}</p>}

      {result && (
        <div className="rounded-r2 border border-border bg-bg2 p-sp4">
          <div className="mb-sp3 flex items-center justify-between">
            <div>
              <div className="text-[14px] font-extrabold text-t1">
                {result.signal.name} · <span className="mono">{result.signal.symbol}</span>
              </div>
              <div className="text-[11px] text-t3">{result.signal.sector}</div>
            </div>
            <div className="text-right">
              <div className={`text-[16px] font-black ${SIGNAL_COLOR[result.signal.signal]}`}>
                {result.signal.signal}
              </div>
              <div className="mono text-[11px] text-t3">{result.signal.confidence.toFixed(0)}% confidence</div>
            </div>
          </div>
          <div className="mb-sp3 grid grid-cols-3 gap-sp2 text-center">
            <div className="rounded-r1 border border-border bg-panel p-sp2">
              <div className="mono text-[13px] font-bold text-t1">${result.signal.current_price.toFixed(2)}</div>
              <div className="text-[9.5px] uppercase tracking-wide text-t4">Price</div>
            </div>
            <div className="rounded-r1 border border-border bg-panel p-sp2">
              <div className="mono text-[13px] font-bold text-t1">{result.signal.rsi.toFixed(1)}</div>
              <div className="text-[9.5px] uppercase tracking-wide text-t4">RSI</div>
            </div>
            <div className="rounded-r1 border border-border bg-panel p-sp2">
              <div className="mono text-[13px] font-bold text-t1">{result.signal.ma_cross}</div>
              <div className="text-[9.5px] uppercase tracking-wide text-t4">MA Cross</div>
            </div>
          </div>
          <p className="text-[10.5px] leading-relaxed text-t4">{result.disclaimer}</p>
        </div>
      )}
    </GlassPanel>
  );
}
