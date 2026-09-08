import { SignalTicker, type Signal } from "@/components/SignalTicker";
import { DashboardWelcomeNote } from "@/components/onboarding/DashboardWelcomeNote";
import { PortfolioOverviewPanel, type HoldingsData } from "@/components/dashboard/PortfolioOverviewPanel";
import { AgentPerformancePanel, type AgentPerformance } from "@/components/dashboard/AgentPerformancePanel";
import { TrackComparisonPanel, type TrackAgentsData } from "@/components/dashboard/TrackComparisonPanel";
import { StressTestPanel } from "@/components/dashboard/StressTestPanel";
import { VerifySignalPanel } from "@/components/dashboard/VerifySignalPanel";
import { SectorAllocationChart } from "@/components/dashboard/SectorAllocationChart";
import { InsightsAlertsPanel } from "@/components/dashboard/InsightsAlertsPanel";
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

async function getTrackAgents(track: "track1" | "track2"): Promise<TrackAgentsData | null> {
  try {
    const res = await fetch(apiUrl(`/api/${track}/agents`), { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as TrackAgentsData;
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const [initialSignals, holdings, agentPerformance, track1, track2] = await Promise.all([
    getInitialSignals(),
    getHoldings(),
    getAgentPerformance(),
    getTrackAgents("track1"),
    getTrackAgents("track2"),
  ]);

  return (
    <div className="grid grid-cols-1 gap-sp5 lg:grid-cols-3">
      <div className="lg:col-span-3">
        <DashboardWelcomeNote />
      </div>
      <PortfolioOverviewPanel initialData={holdings} />
      <SignalTicker initialSignals={initialSignals} />
      <div className="lg:col-span-2">
        <AgentPerformancePanel data={agentPerformance} />
      </div>
      <StressTestPanel />
      <SectorAllocationChart initialHoldings={holdings?.holdings ?? []} />
      <div className="lg:col-span-2">
        <InsightsAlertsPanel signals={initialSignals} />
      </div>
      <div className="lg:col-span-3">
        <VerifySignalPanel />
      </div>
      <div className="lg:col-span-3">
        <TrackComparisonPanel track1={track1} track2={track2} />
      </div>
    </div>
  );
}
