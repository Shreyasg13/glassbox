import { GlassPanel } from "@/components/GlassPanel";
import { SignalTicker, type Signal } from "@/components/SignalTicker";
import { apiUrl } from "@/lib/api";

/**
 * Server-fetches the first snapshot so the ticker paints with real data
 * immediately instead of showing "Waiting for signals…" until the
 * WebSocket's first frame arrives (perf doc §2 — RSC prefetch for
 * live islands). The client component takes over from here via WS.
 */
async function getInitialSignals(): Promise<Signal[]> {
  try {
    const res = await fetch(apiUrl("/api/live-signals"), { cache: "no-store" });
    if (!res.ok) return [];
    const data: { signals?: Signal[] } = await res.json();
    return data.signals ?? [];
  } catch {
    return [];
  }
}

export default async function DashboardPage() {
  const initialSignals = await getInitialSignals();

  return (
    <div className="grid grid-cols-1 gap-sp5 lg:grid-cols-3">
      <GlassPanel variant="accent" className="lg:col-span-2">
        <h1 className="mb-sp2 text-[20px] font-extrabold text-t1">Portfolio Overview</h1>
        <p className="text-[13px] text-t3">
          Server-rendered shell. Wire this panel to <code className="mono">/api/holdings</code> and{" "}
          <code className="mono">/api/track1/data</code> once the FastAPI gateway is running.
        </p>
      </GlassPanel>

      <SignalTicker initialSignals={initialSignals} />
    </div>
  );
}
