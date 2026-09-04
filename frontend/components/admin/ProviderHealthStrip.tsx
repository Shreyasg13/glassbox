"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ProviderHealth } from "@/lib/types";

const PROVIDERS = ["vllm", "ollama", "gemini", "claude"] as const;

export function ProviderHealthStrip() {
  const { token } = useAuth();
  const { data } = useQuery({
    queryKey: ["provider-health"],
    queryFn: () => apiFetch<ProviderHealth[]>("/api/admin/providers/health", { token: token ?? undefined }),
    refetchInterval: 15_000,
    enabled: !!token,
  });

  const byProvider = new Map((data ?? []).map((h) => [h.provider, h]));

  return (
    <div className="flex flex-wrap gap-sp3">
      {PROVIDERS.map((p) => {
        const h = byProvider.get(p);
        const ok = h?.reachable ?? false;
        return (
          <div
            key={p}
            title={h?.detail ?? "no health data yet"}
            className="flex items-center gap-sp2 rounded-r1 border border-border bg-bg2 px-sp3 py-sp1 text-[11px] font-semibold text-t3"
          >
            <span className={`h-[7px] w-[7px] rounded-full ${ok ? "bg-teal" : "bg-red"}`} />
            <span className="uppercase">{p}</span>
          </div>
        );
      })}
    </div>
  );
}
