"use client";

import { memo, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useJobRun } from "@/lib/useJobRun";

/**
 * One log line. Memoized on its own text so appending a new line doesn't
 * re-render every prior line (perf doc §2 — memoize live widgets).
 */
const LogLine = memo(
  function LogLine({ text }: { text: string }) {
    return <div>{text}</div>;
  },
  (prev, next) => prev.text === next.text
);

export function JobOutputPanel({
  startUrl,
  buildBody,
  runLabel = "Run",
  inputPlaceholder = "Test input…",
  showInput = true,
  onDone,
}: {
  startUrl: string;
  buildBody?: (input: string) => unknown;
  runLabel?: string;
  inputPlaceholder?: string;
  showInput?: boolean;
  onDone?: (result: Record<string, unknown> | null | undefined) => void;
}) {
  const { token } = useAuth();
  const [input, setInput] = useState("");
  const { run, lines, streamText, status, running } = useJobRun(token);

  async function handleRun() {
    await run(startUrl, buildBody ? buildBody(input) : {});
  }

  const hasOutput = lines.length > 0 || streamText.length > 0 || status !== null;

  useEffect(() => {
    if (status && (status.status === "done" || status.status === "error")) {
      onDone?.(status.result);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  return (
    <div className="flex flex-col gap-sp3">
      {showInput && (
        <textarea
          className="input min-h-[80px]"
          placeholder={inputPlaceholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
      )}
      <button className="btn btn-primary self-start" disabled={running} onClick={handleRun}>
        {running ? "Running…" : runLabel}
      </button>

      {hasOutput && (
        <div className="mono max-h-[280px] overflow-y-auto rounded-r2 border border-border bg-bg2 p-sp3 text-[12px] text-t2">
          {lines.map((l, i) => (
            <LogLine key={i} text={l} />
          ))}
          {streamText && <div className="whitespace-pre-wrap text-t1">{streamText}</div>}
          {status && (
            <div
              className={`mt-sp2 border-t border-border pt-sp2 font-bold ${
                status.status === "done"
                  ? "text-teal"
                  : status.status === "error"
                    ? "text-red"
                    : "text-gold"
              }`}
            >
              {status.status === "done" && "✓ Job complete"}
              {status.status === "error" && `✗ ${status.error ?? "Job failed"}`}
              {(status.status === "queued" || status.status === "running") && "… running"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
