"use client";

import { useState } from "react";
import { Reveal } from "@/components/Reveal";

// No backend endpoint exists yet to persist this rating -- it's real,
// interactive UI (click to rate, visual feedback) but the result only
// lives in this component's local state. Don't imply it was saved
// anywhere durable until a real endpoint is wired up.
export function ScoreFeedback() {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [submitted, setSubmitted] = useState(false);

  function rate(n: number) {
    setRating(n);
    setSubmitted(true);
  }

  return (
    <section className="px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="glass-panel mx-auto flex max-w-[760px] flex-col items-center gap-sp5 p-sp6 text-center sm:flex-row sm:items-center sm:justify-between sm:text-left">
          <div>
            <h3 className="mb-sp1 text-[16px] font-bold text-t1">Was this verification useful?</h3>
            <p className="max-w-[380px] text-[12.5px] leading-relaxed text-t3">
              Your rating helps us track how useful the evidence trail actually is — logged locally in this demo,
              not yet wired to a live trust-score pipeline.
            </p>
          </div>
          <div>
            <div className="flex gap-sp1 text-[24px]">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-label={`Rate ${n} star${n > 1 ? "s" : ""}`}
                  onClick={() => rate(n)}
                  onMouseEnter={() => setHover(n)}
                  onMouseLeave={() => setHover(0)}
                  className={`transition-transform duration-150 ease-glass hover:scale-110 ${
                    n <= (hover || rating) ? "text-gold" : "text-t4"
                  }`}
                >
                  ★
                </button>
              ))}
            </div>
            {submitted && (
              <div className="mono mt-sp2 text-[11px] font-semibold text-teal">
                ✓ Thanks — {rating}/5 recorded for this session.
              </div>
            )}
          </div>
        </div>
      </Reveal>
    </section>
  );
}
