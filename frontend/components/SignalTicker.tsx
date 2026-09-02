"use client";

import { memo, useEffect, useRef, useState } from "react";

export type Signal = {
  symbol: string;
  name?: string;
  sector?: string;
  current_price?: number;
  signal: "BUY" | "SELL" | "HOLD" | string;
  confidence?: number;
  data_date?: string;
  [key: string]: unknown;
};

type SignalsEnvelope = {
  type: "signals" | string;
  data: { signals: Signal[] };
};

type ConnState = "connecting" | "open" | "closed";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/signals";
const RECONNECT_DELAY_MS = 2000;

const signalColor: Record<string, string> = {
  BUY: "text-teal",
  SELL: "text-red",
  HOLD: "text-t3",
};

/**
 * One signal row. Memoized so a 3s broadcast tick only re-renders rows
 * whose symbol/signal/price actually changed, not the whole list.
 */
const SignalRow = memo(
  function SignalRow({ s }: { s: Signal }) {
    return (
      <li className="flex items-center justify-between rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[13px]">
        <span className="mono font-semibold text-t1">{s.symbol}</span>
        <span className={`mono font-bold ${signalColor[s.signal] ?? "text-t2"}`}>{s.signal}</span>
        <span className="mono text-t3">
          {s.current_price != null ? `$${s.current_price.toFixed(2)}` : ""}
        </span>
        <span className="text-t3">{s.confidence != null ? `${s.confidence.toFixed(0)}%` : ""}</span>
      </li>
    );
  },
  (prev, next) =>
    prev.s.symbol === next.s.symbol &&
    prev.s.signal === next.s.signal &&
    prev.s.current_price === next.s.current_price
);

export function SignalTicker({ initialSignals = [] }: { initialSignals?: Signal[] }) {
  const [signals, setSignals] = useState<Signal[]>(initialSignals);
  const [state, setState] = useState<ConnState>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      setState("connecting");
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setState("open");

      ws.onmessage = (event) => {
        try {
          const msg: SignalsEnvelope = JSON.parse(event.data);
          if (msg.type === "signals" && Array.isArray(msg.data?.signals)) {
            setSignals(msg.data.signals);
          }
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        setState("closed");
        if (!cancelled) {
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="glass-panel">
      <div className="mb-sp4 flex items-center justify-between">
        <h2 className="text-[13px] font-bold uppercase tracking-wide text-t3">
          Live Signals
        </h2>
        <span className="flex items-center gap-sp2 text-[11px] font-semibold text-t3">
          <span
            className={`h-[7px] w-[7px] rounded-full ${
              state === "open" ? "bg-teal" : state === "connecting" ? "bg-gold" : "bg-red"
            }`}
          />
          {state === "open" ? "Connected" : state === "connecting" ? "Connecting…" : "Reconnecting…"}
        </span>
      </div>

      {signals.length === 0 ? (
        <p className="py-sp6 text-center text-[13px] text-t3">
          Waiting for signals from {WS_URL}
        </p>
      ) : (
        <ul className="flex flex-col gap-sp2">
          {signals.map((s) => (
            <SignalRow key={s.symbol} s={s} />
          ))}
        </ul>
      )}
    </div>
  );
}
