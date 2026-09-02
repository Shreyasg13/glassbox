"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AgentConfig, OrchestrationConfig, OrchestrationMode } from "@/lib/types";
import { JobOutputPanel } from "./JobOutputPanel";

const MODES: OrchestrationMode[] = ["sequential", "parallel", "committee_vote"];

export function OrchestrationForm({ initial }: { initial: OrchestrationConfig }) {
  const { token } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [orch, setOrch] = useState<OrchestrationConfig>(initial);
  const [error, setError] = useState<string | null>(null);
  const isEdit = Boolean(initial.id);

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => apiFetch<AgentConfig[]>("/admin/agents", { token: token ?? undefined }),
    enabled: !!token,
  });

  const save = useMutation({
    mutationFn: async () => {
      if (isEdit && orch.id) {
        return apiFetch<OrchestrationConfig>(`/admin/orchestrations/${orch.id}`, {
          method: "PUT",
          body: JSON.stringify(orch),
          token: token ?? undefined,
        });
      }
      return apiFetch<OrchestrationConfig>("/admin/orchestrations", {
        method: "POST",
        body: JSON.stringify(orch),
        token: token ?? undefined,
      });
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ["orchestrations"] });
      router.replace(`/admin/orchestrations/${saved.id}`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Save failed"),
  });

  const remove = useMutation({
    mutationFn: async () => {
      if (!orch.id) return;
      await apiFetch(`/admin/orchestrations/${orch.id}`, {
        method: "DELETE",
        token: token ?? undefined,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orchestrations"] });
      router.replace("/admin/orchestrations");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Delete failed"),
  });

  function toggleAgent(id: string) {
    setOrch((prev) => ({
      ...prev,
      agent_ids: prev.agent_ids.includes(id)
        ? prev.agent_ids.filter((a) => a !== id)
        : [...prev.agent_ids, id],
    }));
  }

  return (
    <div className="flex flex-col gap-sp6">
      <div className="glass-panel flex flex-col gap-sp4 p-sp5">
        <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
          Name
          <input
            className="input"
            value={orch.name}
            onChange={(e) => setOrch({ ...orch, name: e.target.value })}
            placeholder="e.g. Daily Pre-Market Committee"
          />
        </label>

        <div className="flex items-center gap-sp4">
          <span className="text-[12px] font-semibold text-t3">Mode</span>
          <div className="flex gap-sp2">
            {MODES.map((m) => (
              <button
                key={m}
                type="button"
                className={`btn ${orch.mode === m ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOrch({ ...orch, mode: m })}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        <div>
          <span className="mb-sp2 block text-[12px] font-semibold text-t3">Agents</span>
          <div className="flex flex-col gap-sp2 rounded-r2 border border-border bg-bg2 p-sp3">
            {(agents ?? []).length === 0 && (
              <p className="text-[12px] text-t3">No agents yet — create one first.</p>
            )}
            {agents?.map((a) => (
              <label key={a.id} className="flex items-center gap-sp2 text-[13px] text-t1">
                <input
                  type="checkbox"
                  checked={orch.agent_ids.includes(a.id!)}
                  onChange={() => toggleAgent(a.id!)}
                />
                {a.name}
                <span className="text-[11px] text-t3">({a.type})</span>
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-sp4">
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Coordinator
            <input
              className="input"
              value={orch.coordinator}
              onChange={(e) => setOrch({ ...orch, coordinator: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Schedule (cron, optional)
            <input
              className="input"
              value={orch.schedule ?? ""}
              onChange={(e) => setOrch({ ...orch, schedule: e.target.value })}
              placeholder="e.g. 0 8 * * 1-5"
            />
          </label>
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Per-agent timeout (seconds)
            <input
              className="input"
              type="number"
              min={1}
              step={1}
              value={orch.agent_timeout_s}
              onChange={(e) => setOrch({ ...orch, agent_timeout_s: Number(e.target.value) })}
            />
          </label>
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Run budget (seconds)
            <input
              className="input"
              type="number"
              min={1}
              step={1}
              value={orch.run_budget_s}
              onChange={(e) => setOrch({ ...orch, run_budget_s: Number(e.target.value) })}
            />
          </label>
        </div>

        {error && <p className="text-[12px] font-semibold text-red">{error}</p>}

        <div className="flex gap-sp3">
          <button
            className="btn btn-primary"
            disabled={save.isPending || !orch.name || orch.agent_ids.length === 0}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : isEdit ? "Save Changes" : "Create Orchestration"}
          </button>
          {isEdit && (
            <button
              className="btn btn-danger"
              disabled={remove.isPending}
              onClick={() => {
                if (confirm(`Delete orchestration "${orch.name}"?`)) remove.mutate();
              }}
            >
              Delete
            </button>
          )}
        </div>
      </div>

      {isEdit && orch.id && (
        <div className="glass-panel p-sp5">
          <h2 className="mb-sp4 text-[13px] font-bold uppercase tracking-wide text-t3">Run Now</h2>
          <JobOutputPanel
            startUrl={`/admin/orchestrations/${orch.id}/run`}
            buildBody={(input) => (input ? { input } : {})}
            showInput
            inputPlaceholder="Optional context to pass into this run…"
            runLabel="Run Orchestration"
          />
        </div>
      )}
    </div>
  );
}
