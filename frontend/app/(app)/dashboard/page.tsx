import { SignalTicker, type Signal } from "@/components/SignalTicker";
import { PortfolioOverviewPanel, type HoldingsData } from "@/components/dashboard/PortfolioOverviewPanel";
import { AgentPerformancePanel, type AgentPerformance } from "@/components/dashboard/AgentPerformancePanel";
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

async function getHoldings(): Promise<HoldingsData | null> {
  try {
    const res = await fetch(apiUrl("/api/holdings"), { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as HoldingsData;
  } catch {
    return null;
  }
}

async function getAgentPerformance(): Promise<AgentPerformance[]> {
  try {
    const res = await fetch(apiUrl("/api/agent-performance"), { cache: "no-store" });
    if (!res.ok) return [];
    return (await res.json()) as AgentPerformance[];
  } catch {
    return [];
  }
}

export default async function DashboardPage() {
  const [initialSignals, holdings, agentPerformance] = await Promise.all([
    getInitialSignals(),
    getHoldings(),
    getAgentPerformance(),
  ]);

  return (
    <div className="grid grid-cols-1 gap-sp5 lg:grid-cols-3">
      <PortfolioOverviewPanel data={holdings} />
      <SignalTicker initialSignals={initialSignals} />
      <div className="lg:col-span-3">
        <AgentPerformancePanel data={agentPerformance} />
      </div>
    </div>
  );
}
