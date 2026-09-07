"use client";

import { useState } from "react";
import { GuideAvatar } from "@/components/onboarding/GuideBubble";
import { GLASSBOX_GUIDE } from "@/lib/glassboxGuide";

const SUGGESTIONS = ["Verify AAPL", "Explain Altman Z-Score", "How does GlassBox verify AI?"];

// Deliberately just the launcher SHELL -- Plan-correction.MD's Workstream
// C (real command/intent parsing, real verification runs from natural
// language) is separate, larger, not-yet-built work. Every submission
// here gets the SAME honest response regardless of what was typed,
// because there is no real execution behind it yet for a logged-out
// visitor -- the addendum is explicit: "Do not fake execution for
// logged-out users." This still delivers the actual point of the
// launcher (introduce that GlassBox is an agent you can ask things, not
// just a page you read) without pretending a command layer exists.
export function AgentLauncher() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [asked, setAsked] = useState(false);

  function handleAsk(text: string) {
    setQuery(text);
    setAsked(true);
  }

  function reset() {
    setQuery("");
    setAsked(false);
  }

  return (
    <div className="fixed bottom-sp6 right-sp6 z-40">
      {open && (
        <div className="glass-panel-raised mb-sp3 w-[320px] max-w-[86vw] overflow-hidden rounded-r3 shadow-lg2">
          <div className="flex items-center justify-between gap-sp2 border-b border-border p-sp4">
            <div className="flex items-center gap-sp2">
              <GuideAvatar size={30} />
              <div>
                <div className="text-[12px] font-extrabold text-t1">{GLASSBOX_GUIDE.name}</div>
                <div className="text-[10px] text-t3">Ask about a stock or how GlassBox works</div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                reset();
              }}
              aria-label="Close"
              className="text-[13px] text-t3 hover:text-t1"
            >
              ✕
            </button>
          </div>

          <div className="p-sp4">
            {!asked ? (
              <>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (query.trim()) handleAsk(query.trim());
                  }}
                  className="flex gap-sp2"
                >
                  <input
                    className="input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Try: Verify AAPL…"
                    autoFocus
                  />
                  <button type="submit" className="btn btn-primary shrink-0 px-sp3" disabled={!query.trim()}>
                    →
                  </button>
                </form>
                <div className="mt-sp3 flex flex-wrap gap-sp2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => handleAsk(s)}
                      className="rounded-r4 border border-border px-sp3 py-1 text-[11px] text-t2 hover:border-teal hover:text-teal"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <div>
                <p className="mb-sp1 text-[11px] font-semibold uppercase tracking-wide text-t4">You asked</p>
                <p className="mb-sp4 text-[13px] text-t2">&ldquo;{query}&rdquo;</p>
                <div className="rounded-r2 border border-teal/20 bg-teal-dim p-sp3">
                  <p className="mb-sp3 text-[13px] leading-relaxed text-t1">
                    I can do that once your workspace is set up. Create a free account and I&apos;ll run this for
                    real, on your own dashboard.
                  </p>
                  <a href="/signup" className="btn btn-primary inline-block w-full px-sp4 py-2 text-center text-[13px]">
                    Get started free →
                  </a>
                </div>
                <button
                  type="button"
                  onClick={reset}
                  className="mt-sp3 text-[11.5px] font-semibold text-t3 hover:text-t1"
                >
                  ← Ask something else
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? "Close GlassBox Agent" : "Ask GlassBox"}
        className="flex items-center gap-sp2 rounded-full border border-teal/30 bg-teal px-sp5 py-sp3 text-[13px] font-bold text-bg shadow-teal transition-transform hover:-translate-y-px"
      >
        <span aria-hidden>{open ? "✕" : "✓"}</span>
        {open ? "Close" : "Ask GlassBox"}
      </button>
    </div>
  );
}
