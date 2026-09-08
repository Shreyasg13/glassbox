"use client";

import { useState } from "react";
import { ExplainTooltip } from "@/components/ExplainTooltip";

// Brand-colored monogram badges, not the real logo artwork -- embedding the
// actual trademarked logo files would be a real reproduction risk for a
// project like this. Using each broker's well-known primary brand color
// with a simple letterform is the same nominative-fair-use pattern most
// fintech onboarding mockups use when they can't ship official assets.
const brokers = [
  { name: "Fidelity", letter: "F", color: "#00754A" },
  { name: "Schwab", letter: "S", color: "#00A0DF" },
  { name: "TD Ameritrade", letter: "TD", color: "#5AA220" },
  { name: "Robinhood", letter: "R", color: "#00C805" },
];

export function StepPortfolio({
  tickers,
  onTickersChange,
}: {
  tickers: string[];
  onTickersChange: (tickers: string[]) => void;
}) {
  const [mode, setMode] = useState<"search" | "connect">("search");
  const [input, setInput] = useState("");
  const [comingSoonBroker, setComingSoonBroker] = useState<string | null>(null);

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
      <div className="mb-1 text-[17px] font-bold text-t1">Choose what GlassBox should monitor</div>
      <div className="mb-sp4 text-[13px] text-t3">
        Search and add investments manually, or preview broker connections coming soon.
      </div>

      <div className="mb-sp4 flex gap-sp1 rounded-r2 border border-border bg-bg2 p-1">
        <button
          type="button"
          onClick={() => setMode("search")}
          className={`flex-1 rounded-r1 py-sp2 text-[12.5px] font-bold transition-colors ${
            mode === "search" ? "bg-teal/[0.1] text-teal" : "text-t3"
          }`}
        >
          🔎 Search manually
        </button>
        <button
          type="button"
          onClick={() => setMode("connect")}
          className={`flex flex-1 items-center justify-center gap-1 rounded-r1 py-sp2 text-[12.5px] font-bold transition-colors ${
            mode === "connect" ? "bg-teal/[0.1] text-teal" : "text-t3"
          }`}
        >
          Connect portfolio
          <ExplainTooltip
            tag="Coming soon"
            title="Connecting a brokerage"
            desc="Direct broker connections are on the roadmap, likely through a broker-aggregator provider so one integration covers many brokers. Your brokerage login would never touch GlassBox's servers -- it would be entered on the brokerage's own page, and you could disconnect anytime. For now, search and add tickers manually."
          />
        </button>
      </div>

      {mode === "search" ? (
        <>
          <div className="mb-sp2 flex gap-sp2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addTicker()}
              placeholder="Type ticker + press Enter (e.g. AAPL)"
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
            {tickers.length} holdings detected. GlassBox will verify all in the next step
          </div>
        </>
      ) : (
        <div className="rounded-r2 border border-border bg-bg2 p-sp4">
          <div className="mb-sp3 grid grid-cols-2 gap-sp2 sm:grid-cols-4">
            {brokers.map((broker) => {
              const showingComingSoon = comingSoonBroker === broker.name;
              return (
                <button
                  key={broker.name}
                  type="button"
                  onClick={() => setComingSoonBroker(broker.name)}
                  className="flex flex-col items-center gap-sp2 rounded-r2 border border-border bg-panel p-sp3 text-center transition-colors hover:border-border2"
                >
                  <div
                    className="grid h-[30px] w-[30px] place-items-center rounded-r1 text-[11px] font-extrabold text-white"
                    style={{ background: broker.color }}
                  >
                    {broker.letter}
                  </div>
                  <div className="text-[12.5px] font-semibold text-t1">{broker.name}</div>
                  <div className="text-[10px] font-semibold text-t3">
                    {showingComingSoon ? "Coming soon" : "Not yet connected"}
                  </div>
                </button>
              );
            })}
          </div>
          <p className="text-[11.5px] text-t3">
            Broker connections aren&apos;t live yet -- search and add tickers manually for now.
          </p>
        </div>
      )}
    </div>
  );
}
