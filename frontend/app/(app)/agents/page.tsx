"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { GlassPanel } from "@/components/GlassPanel";
import { JobOutputPanel } from "@/components/admin/JobOutputPanel";
import { GuideAvatar } from "@/components/onboarding/GuideBubble";
import { GLASSBOX_GUIDE } from "@/lib/glassboxGuide";

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
  const [guideOpen, setGuideOpen] = useState(false);

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
        <div className="flex items-start justify-between gap-sp3 rounded-r2 border border-teal/20 bg-teal/[0.04] p-sp3">
          <div className="flex items-start gap-sp3">
            <GuideAvatar />
            <div>
              <div className="flex items-center gap-sp2">
                <span className="text-[13.5px] font-bold text-t1">{GLASSBOX_GUIDE.name}</span>
                <span className="flex items-center gap-1 text-[10.5px] font-semibold text-teal">
                  <span className="live-dot" /> ACTIVE
                </span>
              </div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-t3">
                {GLASSBOX_GUIDE.role}
              </div>
              <p className="mt-1 max-w-[440px] text-[12px] leading-relaxed text-t2">
                {GLASSBOX_GUIDE.description}
              </p>
              {guideOpen && (
                <p className="mt-sp2 rounded-r2 border border-border bg-bg2 p-sp3 text-[11.5px] leading-relaxed text-t3">
                  GlassBox Guide explains scores, evidence, reports, and alerts -- it doesn&apos;t
                  trade or generate signals itself. Conversational Q&amp;A isn&apos;t built yet;
                  this panel is a placeholder for that, not a live chat.
                </p>
              )}
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-sp2">
            <span className="rounded-r4 bg-teal-dim px-sp2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide text-teal">
              System Agent
            </span>
            <button
              type="button"
              onClick={() => setGuideOpen((o) => !o)}
              className="text-[11.5px] font-semibold text-teal hover:underline"
            >
              {guideOpen ? "Close" : "Open →"}
            </button>
          </div>
        </div>

        <div className="mb-sp1 mt-sp5 text-[10px] font-bold uppercase tracking-wide text-t4">
          Your Committee Agents
        </div>
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
          buildBody={(input) => ({ input })}
          inputPlaceholder="Which ticker should this report analyze? e.g. AAPL"
          runLabel="Run My Report"
        />
      </GlassPanel>

      <div>
        <div className="mb-sp2 text-[10px] font-bold uppercase tracking-wide text-t4">
          Future agents
        </div>
        <div className="grid grid-cols-2 gap-sp2 sm:grid-cols-3">
          {[
            { icon: "🔍", label: "Verify Agent" },
            { icon: "⚠", label: "Risk Agent" },
            { icon: "📑", label: "Reports Agent" },
          ].map((f) => (
            <div
              key={f.label}
              className="flex flex-col items-center gap-sp1 rounded-r2 border border-dashed border-border p-sp3 text-center opacity-50"
            >
              <span className="text-[16px]">{f.icon}</span>
              <span className="text-[11px] font-semibold text-t3">{f.label}</span>
              <span className="text-[9px] uppercase tracking-wide text-t4">Not built yet</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
