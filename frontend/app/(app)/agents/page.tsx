"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { GlassPanel } from "@/components/GlassPanel";
import { JobOutputPanel } from "@/components/admin/JobOutputPanel";

type AgentSummary = {
  id: string;
  name: string;
  role: string;
  type: "deterministic" | "llm";
  enabled: boolean;
};

type AgentSubscriptions = { agent_ids: string[] };

/**
 * Self-service agent subscriptions + "run my report" -- any logged-in
 * role (viewer or admin), unlike everything under /admin/* which is
 * admin-gated. Backs the "only my subscribed agents run my report"
 * feature (backend/app/routers/me.py): no subscription set means every
 * agent in the seeded committee runs (the same default behavior as
 * before this feature existed), same fallback convention the /dashboard
 * watchlist personalization already uses.
 */
export default function MyAgentsPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const { data: agents } = useQuery({
    queryKey: ["me-agents"],
    queryFn: () => apiFetch<AgentSummary[]>("/api/me/agents", { token: token ?? undefined }),
    enabled: !!token,
  });

  const { data: subscriptions } = useQuery({
    queryKey: ["me-agent-subscriptions"],
    queryFn: () => apiFetch<AgentSubscriptions>("/api/me/agent-subscriptions", { token: token ?? undefined }),
    enabled: !!token,
  });

  // One-time hydration of local checkbox state once the real
  // subscription list arrives -- avoids clobbering in-progress edits
  // on every background refetch.
  useEffect(() => {
    if (subscriptions && !hydrated) {
      setSelected(new Set(subscriptions.agent_ids));
      setHydrated(true);
    }
  }, [subscriptions, hydrated]);

  const save = useMutation({
    mutationFn: () =>
      apiFetch<AgentSubscriptions>("/api/me/agent-subscriptions", {
        method: "PUT",
        body: JSON.stringify({ agent_ids: Array.from(selected) }),
        token: token ?? undefined,
      }),
    onSuccess: () => {
      setSaveError(null);
      qc.invalidateQueries({ queryKey: ["me-agent-subscriptions"] });
    },
    onError: (err) => setSaveError(err instanceof ApiError ? err.message : "Save failed"),
  });

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (!token) {
    return (
      <GlassPanel>
        <p className="text-[13px] text-t3">Sign in to manage which agents run your reports.</p>
      </GlassPanel>
    );
  }

  return (
    <div className="flex flex-col gap-sp5">
      <div>
        <h1 className="text-[18px] font-bold text-t1">My Agents</h1>
        <p className="mt-sp1 text-[12.5px] text-t3">
          Choose which agents run when you generate a report. Leave everything unchecked to run the
          full committee (the default).
        </p>
      </div>

      <GlassPanel variant="accent">
        <div className="flex flex-col gap-sp2">
          {(agents ?? []).map((a) => (
            <label
              key={a.id}
              className="flex cursor-pointer items-center gap-sp3 rounded-r2 bg-panel px-sp3 py-sp2"
            >
              <input
                type="checkbox"
                checked={selected.has(a.id)}
                onChange={() => toggle(a.id)}
                className="h-4 w-4"
              />
              <div className="flex-1">
                <div className="text-[13px] font-semibold text-t1">{a.name}</div>
                <div className="text-[11px] text-t3">{a.role}</div>
              </div>
              <span className="text-[10.5px] uppercase tracking-wide text-t4">{a.type}</span>
            </label>
          ))}
          {agents && agents.length === 0 && <p className="text-[13px] text-t3">No agents available yet.</p>}
        </div>

        <div className="mt-sp4 flex items-center gap-sp3">
          <button className="btn btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save Subscriptions"}
          </button>
          {selected.size > 0 && (
            <span className="text-[12px] text-t3">{selected.size} agent(s) selected</span>
          )}
          {saveError && <span className="text-[12px] font-semibold text-red">{saveError}</span>}
        </div>
      </GlassPanel>

      <GlassPanel variant="accent">
        <h2 className="mb-sp1 text-[15px] font-bold text-t1">Run My Report</h2>
        <p className="mb-sp4 text-[11.5px] text-t3">
          Runs the Investment Committee orchestration using only your saved subscriptions above (or
          the full committee if you haven&apos;t saved any).
        </p>
        <JobOutputPanel
          startUrl="/api/me/run-report"
          jobStatusBasePath="/api/me/jobs"
          showInput={false}
          runLabel="Run My Report"
        />
      </GlassPanel>
    </div>
  );
}
