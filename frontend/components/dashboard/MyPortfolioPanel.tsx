"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CommitteePortfolio, type PortfolioView } from "@/components/portfolio/CommitteePortfolio";

/** The dashboard's portfolio view: the user's own paper portfolio as the Investment Committee runs it,
 * with the growth graph against engine-only and their plan, a Monte Carlo estimate, and why each stock is
 * held. Replaces the old shared portfolio series, which was identical for everyone and tied to no decision. */
export function MyPortfolioPanel() {
  const { token } = useAuth();
  const q = useQuery({
    queryKey: ["my-portfolio"],
    queryFn: () => apiFetch<PortfolioView>("/api/me/portfolio", { token: token ?? undefined }),
    enabled: !!token,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  if (!token) return null;
  return (
    <section className="glass-panel p-sp4 lg:col-span-3" aria-label="Your portfolio, run by the committee">
      <h2 className="mb-sp3 text-[15px] font-bold text-t1">Your portfolio, run by the committee</h2>
      {q.isPending && <p className="text-[12px] text-t3">Loading your portfolio…</p>}
      {q.isError && <p className="text-[12px] text-t3">{q.error instanceof ApiError ? q.error.message : "Could not load your portfolio."}</p>}
      {q.data && <CommitteePortfolio v={q.data} />}
    </section>
  );
}
