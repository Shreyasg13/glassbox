"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type DigestPrefs = {
  enabled: boolean;
  email: string | null;
  verified: boolean;
  frequency: "daily" | "weekly";
  last_sent: string | null;
  last_error: string | null;
  tickers: string[];
  confirmation?: { ok: boolean; detail: string } | null;
};

/** Opt-in email digest of the user's own watchlist stance. A typed-in address must be confirmed
 * by link before anything is sent (so this can't be used to mail strangers). */
export function DigestPanel() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["my-digest"],
    queryFn: () => apiFetch<DigestPrefs>("/api/me/digest", { token: token ?? undefined }),
    enabled: !!token,
    staleTime: 60 * 1000,
    retry: false,
  });
  const [enabled, setEnabled] = useState(false);
  const [email, setEmail] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "weekly">("daily");
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (q.data) {
      setEnabled(q.data.enabled);
      setEmail(q.data.email ?? "");
      setFrequency(q.data.frequency);
    }
  }, [q.data]);

  const save = useMutation({
    mutationFn: () =>
      apiFetch<DigestPrefs>("/api/me/digest", {
        method: "PUT",
        token: token ?? undefined,
        body: JSON.stringify({ enabled, email: email.trim() || null, frequency }),
      }),
    onSuccess: (d) => {
      qc.setQueryData(["my-digest"], d);
      setNote(
        !d.enabled
          ? "Digest is off."
          : d.verified
            ? "Saved. Your digest is on."
            : d.confirmation?.ok
              ? `Saved. We sent a confirmation link to ${d.email}: click it to start receiving the digest.`
              : d.confirmation
                ? `Saved, but the confirmation email failed: ${d.confirmation.detail}`
                : `Saved. Waiting for you to confirm ${d.email}: check your inbox.`,
      );
    },
    onError: (e) => setNote(e instanceof ApiError ? e.message : "Could not save"),
  });

  const preview = useMutation({
    mutationFn: () => apiFetch<{ ok: boolean; detail: string }>("/api/me/digest/preview", { method: "POST", token: token ?? undefined }),
    onSuccess: (r) => setNote(r.ok ? `Preview ${r.detail}` : r.detail),
    onError: (e) => setNote(e instanceof ApiError ? e.message : "Could not send preview"),
  });

  if (!token || q.isError || q.isPending) return null; // dev accounts and signed-out users get a 400/401: hide the card

  const d = q.data;
  const watch = d.tickers.length ? d.tickers.join(", ") : "the full GlassBox universe";
  return (
    <section className="glass-panel p-sp4" aria-label="Email digest">
      <div className="flex flex-wrap items-baseline justify-between gap-sp2">
        <h2 className="text-[15px] font-bold text-t1">Email digest</h2>
        <span className="text-[11px] text-t3">Your stance on {watch}, in your inbox</span>
      </div>
      <div className="mt-sp3 flex flex-col gap-sp3 sm:flex-row sm:items-end">
        <label className="flex items-center gap-sp2 text-[13px] text-t2">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Send me the digest
        </label>
        <label className="flex min-w-0 flex-1 flex-col gap-1 text-[11px] text-t3">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            maxLength={254}
            className="min-w-0 rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[13px] text-t1"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-t3">
          How often
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as "daily" | "weekly")}
            className="rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[13px] text-t1"
          >
            <option value="daily">Every trading day</option>
            <option value="weekly">Fridays only</option>
          </select>
        </label>
      </div>
      <div className="mt-sp3 flex flex-wrap items-center gap-sp3">
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending}
          className="rounded-r1 bg-teal px-sp4 py-sp2 text-[12px] font-bold text-bg disabled:opacity-60"
        >
          {save.isPending ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => preview.mutate()}
          disabled={preview.isPending || !d.verified}
          title={d.verified ? undefined : "Confirm your email address first"}
          className="rounded-r1 border border-border px-sp4 py-sp2 text-[12px] font-semibold text-t2 disabled:opacity-50"
        >
          {preview.isPending ? "Sending…" : "Send me one now"}
        </button>
        {d.email && (
          <span className={`text-[11px] ${d.verified ? "text-teal" : "text-t3"}`}>
            {d.verified ? "✓ address confirmed" : "address not confirmed yet"}
          </span>
        )}
        {d.last_sent && <span className="text-[11px] text-t3">last sent for {d.last_sent}</span>}
      </div>
      {note && (
        <p role="status" className="mt-sp2 text-[12px] text-t2">
          {note}
        </p>
      )}
      {d.last_error && <p className="mt-sp2 text-[11px] text-red">Last send failed ({d.last_error}). We&rsquo;ll retry on the next run.</p>}
      <p className="mt-sp2 text-[10px] text-t3">Simulated research, not investment advice. Every email has an unsubscribe link.</p>
    </section>
  );
}
