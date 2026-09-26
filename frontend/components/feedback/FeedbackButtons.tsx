"use client";

import { useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type FeedbackTarget = "signal" | "answer" | "notification" | "committee" | "general";

/** A quiet thumbs up / down with an optional comment. Feedback is stored for the maintainer to review; it never
 * changes the committee automatically (see backend/app/feedback.py). */
export function FeedbackButtons({ type, refId = "", symbol = "", label = "Was this useful?" }: { type: FeedbackTarget; refId?: string; symbol?: string; label?: string }) {
  const { token } = useAuth();
  const [rating, setRating] = useState<-1 | 0 | 1>(0);
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function send(nextRating: -1 | 0 | 1, text: string) {
    setStatus(null);
    try {
      await apiFetch("/api/me/feedback", { method: "POST", token: token ?? undefined, body: JSON.stringify({ target_type: type, target_ref: refId, rating: nextRating, comment: text, symbol }) });
      setRating(nextRating);
      setStatus(text ? "Thanks, sent." : "Thanks!");
      if (text) setOpen(false);
    } catch (e) {
      setStatus(e instanceof ApiError ? e.message : "Could not send feedback");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-sp2 text-[11px] text-t3">
      <span>{label}</span>
      {([1, -1] as const).map((r) => (
        <button
          key={r}
          type="button"
          onClick={() => send(r, "")}
          aria-pressed={rating === r}
          aria-label={r === 1 ? "Helpful" : "Not helpful"}
          className={`rounded-r1 border px-sp2 py-0.5 ${rating === r ? (r === 1 ? "border-teal/60 bg-teal-dim text-teal" : "border-red/60 text-red") : "border-border hover:bg-bg3"}`}
        >
          {r === 1 ? "👍" : "👎"}
        </button>
      ))}
      <button type="button" onClick={() => setOpen((o) => !o)} className="underline decoration-dotted hover:text-t1">
        {open ? "cancel" : "add a comment"}
      </button>
      {status && <span role="status" className="text-t2">{status}</span>}
      {open && (
        <div className="mt-1 flex w-full flex-col gap-sp2">
          <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={1000} rows={3} placeholder="What would make this better for you?" className="w-full rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 text-[12px] text-t1" />
          <div>
            <button type="button" disabled={!comment.trim()} onClick={() => send(rating, comment.trim())} className="rounded-r1 bg-teal px-sp3 py-sp1 text-[11px] font-bold text-bg disabled:opacity-50">
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
