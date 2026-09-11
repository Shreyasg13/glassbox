import { GlassPanel } from "@/components/GlassPanel";

export type TrackAgent = {
  name: string;
  score: number;
  win_rate: number;
  decisions: number;
  avg_impact: number;
  color: string;
};

export type TrackAgentsData = {
  agents: TrackAgent[];
  vn_score: number;
  total_agents: number;
};

function TrackColumn({ title, subtitle, data }: { title: string; subtitle: string; data: TrackAgentsData | null }) {
  if (!data || data.agents.length === 0) {
    return (
      <div>
        <h3 className="mb-sp1 text-[13px] font-bold text-t1">{title}</h3>
        <p className="text-[12px] text-t3">No data available.</p>
      </div>
    );
  }
  return (
    <div>
      <div className="mb-sp3 flex items-baseline justify-between">
        <div>
          <h3 className="text-[13px] font-bold text-t1">{title}</h3>
          <p className="text-[11px] text-t3">{subtitle}</p>
        </div>
        <span className="mono text-[11px] text-t3">VN {data.vn_score.toFixed(2)}</span>
      </div>
      <div className="flex flex-col gap-sp2">
        {data.agents.map((a) => (
          <div key={a.name} className="flex items-center justify-between rounded-r2 bg-panel px-sp3 py-sp2">
            <span className="flex items-center gap-sp2 text-[12px] font-semibold text-t1">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: a.color }} />
              {a.name}
            </span>
            <span className="mono text-[11px] text-t3">
              {a.win_rate.toFixed(0)}% win · {a.decisions} calls
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TrackComparisonPanel({
  track1,
  track2,
}: {
  track1: TrackAgentsData | null;
  track2: TrackAgentsData | null;
}) {
  return (
    <GlassPanel variant="frost">
      <div className="mb-sp1 flex items-center justify-between">
        <h2 className="text-[15px] font-bold text-t1">Track Comparison</h2>
        <span className="text-[10.5px] text-t3">illustrative</span>
      </div>
      <p className="mb-sp4 text-[11.5px] text-t3">
        The underlying engine ships two committee configurations: a lean 3-agent deterministic
        core and the full 7-agent LLM committee. Figures here are illustrative reference points
        for the two configurations, not this account&apos;s live results.
      </p>
      <div className="grid grid-cols-1 gap-sp5 sm:grid-cols-2">
        <TrackColumn title="Track 1 · Core" subtitle="3 deterministic agents" data={track1} />
        <TrackColumn title="Track 2 · Full Committee" subtitle="7-agent LLM committee" data={track2} />
      </div>
    </GlassPanel>
  );
}
