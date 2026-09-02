"use client";

import { useState } from "react";

const brokers = ["Fidelity", "Schwab", "TD Ameritrade", "Robinhood"];

export function StepPortfolio({
  connectedBroker,
  onConnectBroker,
  tickers,
  onTickersChange,
}: {
  connectedBroker: string | null;
  onConnectBroker: (broker: string | null) => void;
  tickers: string[];
  onTickersChange: (tickers: string[]) => void;
}) {
  const [input, setInput] = useState("");

  function addTicker() {
    const t = input.trim().toUpperCase();
    if (t && !tickers.includes(t)) onTickersChange([...tickers, t]);
    setInput("");
  }

  function removeTicker(t: string) {
    onTickersChange(tickers.filter((x) => x !== t));
  }

  return (
    <div>
      <div className="mb-1 text-[17px] font-bold text-t1">Connect your portfolio</div>
      <div className="mb-sp4 text-[13px] text-t3">
        Link your broker for auto-import, or add tickers manually. Glass Box never stores your
        credentials.
      </div>

      <div className="mb-sp4 grid grid-cols-2 gap-sp2 sm:grid-cols-4">
        {brokers.map((broker) => {
          const connected = connectedBroker === broker;
          return (
            <button
              key={broker}
              type="button"
              onClick={() => onConnectBroker(connected ? null : broker)}
              className={`flex flex-col items-center gap-1 rounded-r2 border p-sp3 text-center transition-colors ${
                connected ? "border-teal bg-bg2" : "border-border bg-bg2 hover:border-border2"
              }`}
            >
              <div className="text-[12.5px] font-semibold text-t1">{broker}</div>
              <div className={`text-[10px] font-semibold ${connected ? "text-teal" : "text-t3"}`}>
                {connected ? "Connected ✓" : "Click to connect"}
              </div>
            </button>
          );
        })}
      </div>

      <div className="mb-sp3 flex items-center gap-sp3 text-[12px] text-t3">
        <div className="h-px flex-1 bg-border" />
        or add tickers manually
        <div className="h-px flex-1 bg-border" />
      </div>

      <div className="mb-sp2 flex gap-sp2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTicker()}
          placeholder="Type ticker + press Enter — e.g. AAPL"
          className="mono flex-1 rounded-r1 border border-border2 bg-bg2 px-sp3 py-sp2 text-[14px] font-bold uppercase text-teal outline-none focus:border-teal focus:shadow-[0_0_0_3px_rgba(13,204,170,.1)]"
        />
        <button
          type="button"
          onClick={addTicker}
          className="whitespace-nowrap rounded-r1 bg-teal px-sp4 py-sp2 text-[13px] font-bold text-bg transition-colors hover:bg-teal2"
        >
          + Add
        </button>
      </div>

      <div className="mb-sp2 flex min-h-[30px] flex-wrap gap-sp2">
        {tickers.map((t) => (
          <span
            key={t}
            onClick={() => removeTicker(t)}
            className="mono cursor-pointer rounded-r4 border border-teal/20 bg-teal/[0.06] px-sp3 py-1 text-[12px] font-semibold text-teal"
          >
            {t} <span className="ml-1 opacity-60">×</span>
          </span>
        ))}
      </div>

      <div className="flex items-center gap-1 text-[11.5px] text-t3">
        <span className="font-semibold text-green">✓</span>
        {tickers.length} holdings detected — Glass Box will verify all in the next step
      </div>
    </div>
  );
}
