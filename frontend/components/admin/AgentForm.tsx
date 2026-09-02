"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AgentConfig, Provider } from "@/lib/types";
import { JobOutputPanel } from "./JobOutputPanel";

const PROVIDERS: Provider[] = ["vllm", "ollama", "gemini", "claude"];

export function AgentForm({ initial }: { initial: AgentConfig }) {
  const { token } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [agent, setAgent] = useState<AgentConfig>(initial);
  const [error, setError] = useState<string | null>(null);
  const isEdit = Boolean(initial.id);

  const save = useMutation({
    mutationFn: async () => {
      const payload = { ...agent, provider: agent.type === "llm" ? agent.provider : null };
      if (isEdit && agent.id) {
        return apiFetch<AgentConfig>(`/admin/agents/${agent.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
          token: token ?? undefined,
        });
      }
      return apiFetch<AgentConfig>("/admin/agents", {
        method: "POST",
        body: JSON.stringify(payload),
        token: token ?? undefined,
      });
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      router.replace(`/admin/agents/${saved.id}`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Save failed"),
  });

  const remove = useMutation({
    mutationFn: async () => {
      if (!agent.id) return;
      await apiFetch(`/admin/agents/${agent.id}`, { method: "DELETE", token: token ?? undefined });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      router.replace("/admin/agents");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Delete failed"),
  });

  return (
    <div className="flex flex-col gap-sp6">
      <div className="glass-panel flex flex-col gap-sp4 p-sp5">
        <div className="grid grid-cols-2 gap-sp4">
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Name
            <input
              className="input"
              value={agent.name}
              onChange={(e) => setAgent({ ...agent, name: e.target.value })}
              placeholder="e.g. Macro Analyst"
            />
          </label>
          <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
            Role
            <input
              className="input"
              value={agent.role}
              onChange={(e) => setAgent({ ...agent, role: e.target.value })}
              placeholder="e.g. macro_analyst"
            />
          </label>
        </div>

        <div className="flex items-center gap-sp4">
          <span className="text-[12px] font-semibold text-t3">Type</span>
          <div className="flex gap-sp2">
            {(["deterministic", "llm"] as const).map((t) => (
              <button
                key={t}
                type="button"
                className={`btn ${agent.type === t ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setAgent({ ...agent, type: t })}
              >
                {t}
              </button>
            ))}
          </div>
          <label className="ml-auto flex items-center gap-sp2 text-[12px] font-semibold text-t3">
            <input
              type="checkbox"
              checked={agent.enabled}
              onChange={(e) => setAgent({ ...agent, enabled: e.target.checked })}
            />
            Enabled
          </label>
        </div>

        {agent.type === "llm" && (
          <>
            <div className="grid grid-cols-2 gap-sp4">
              <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
                Provider
                <select
                  className="select"
                  value={agent.provider ?? ""}
                  onChange={(e) => setAgent({ ...agent, provider: e.target.value as Provider })}
                >
                  <option value="" disabled>
                    Select…
                  </option>
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
                Model
                <input
                  className="input"
                  value={agent.model ?? ""}
                  onChange={(e) => setAgent({ ...agent, model: e.target.value })}
                  placeholder="e.g. qwen2.5-32b-instruct"
                />
              </label>
            </div>

            <div className="grid grid-cols-3 gap-sp4">
              <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
                Temperature ({agent.params.temperature.toFixed(2)})
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.05}
                  value={agent.params.temperature}
                  onChange={(e) =>
                    setAgent({
                      ...agent,
                      params: { ...agent.params, temperature: Number(e.target.value) },
                    })
                  }
                />
              </label>
              <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
                Top P ({agent.params.top_p.toFixed(2)})
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={agent.params.top_p}
                  onChange={(e) =>
                    setAgent({ ...agent, params: { ...agent.params, top_p: Number(e.target.value) } })
                  }
                />
              </label>
              <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
                Max Tokens
                <input
                  type="number"
                  className="input"
                  min={1}
                  value={agent.params.max_tokens}
                  onChange={(e) =>
                    setAgent({
                      ...agent,
                      params: { ...agent.params, max_tokens: Number(e.target.value) },
                    })
                  }
                />
              </label>
            </div>

            <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
              System Prompt
              <textarea
                className="input min-h-[120px]"
                value={agent.system_prompt ?? ""}
                onChange={(e) => setAgent({ ...agent, system_prompt: e.target.value })}
                placeholder="You are a macro-economic analyst for a trading desk…"
              />
            </label>
          </>
        )}

        {error && <p className="text-[12px] font-semibold text-red">{error}</p>}

        <div className="flex gap-sp3">
          <button
            className="btn btn-primary"
            disabled={save.isPending || !agent.name || !agent.role}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : isEdit ? "Save Changes" : "Create Agent"}
          </button>
          {isEdit && (
            <button
              className="btn btn-danger"
              disabled={remove.isPending}
              onClick={() => {
                if (confirm(`Delete agent "${agent.name}"?`)) remove.mutate();
              }}
            >
              Delete
            </button>
          )}
        </div>
      </div>

      {isEdit && agent.type === "llm" && agent.id && (
        <div className="glass-panel p-sp5">
          <h2 className="mb-sp4 text-[13px] font-bold uppercase tracking-wide text-t3">Test Run</h2>
          <JobOutputPanel
            startUrl={`/admin/agents/${agent.id}/test-run`}
            buildBody={(input) => ({ input })}
            inputPlaceholder="Ask this agent something to verify it runs end-to-end…"
          />
        </div>
      )}
    </div>
  );
}
