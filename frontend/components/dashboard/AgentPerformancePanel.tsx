import { GlassPanel } from "@/components/GlassPanel";

export type AgentPerformance = {
  name: string;
  call_count: number;
  success_rate: number;
  avg_duration_ms: number | null;
  last_active_at: string | null;
};

function successColor(rate: number): string {
  if (rate >= 90) return "bg-teal";
  if (rate >= 70) return "bg-gold";
  return "bg-red";
}

export function AgentPerformancePanel({ data }: { data: AgentPerformance[] }) {
  return (
    <GlassPanel variant="frost">
      <div className="mb-sp1 flex items-center justify-between">
        <h2 className="text-[15px] font-bold text-t1">Agent Performance</h2>
        <span className="text-[10.5px] text-t3">real call stats</span>
      </div>
      <p className="mb-sp4 text-[11.5px] text-t3">
        Call volume and reliability per agent, from the real run log. Not a trading win-rate --
        this doesn&apos;t track whether a signal was later profitable, only whether the agent&apos;s
        call itself succeeded.
      </p>

      {data.length === 0 && (
        <p className="text-[13px] text-t3">No agent calls logged yet -- run a test-run or an orchestration to populate this.</p>
      )}

      <div className="flex flex-col gap-sp3">
        {data.map((a) => (
          <div key={a.name}>
            <div className="mb-1 flex items-center justify-between text-[12px]">
              <span className="font-semibold text-t1">{a.name}</span>
              <span className="mono text-t3">
                {a.call_count} calls · {a.success_rate.toFixed(0)}% ok
                {a.avg_duration_ms != null ? ` · ${Math.round(a.avg_duration_ms)}ms avg` : ""}
              </span>
            </div>
            <div className="h-[6px] w-full overflow-hidden rounded-full bg-panel">
              <div
                className={`h-full rounded-full ${successColor(a.success_rate)}`}
                style={{ width: `${Math.min(100, Math.max(2, a.success_rate))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
