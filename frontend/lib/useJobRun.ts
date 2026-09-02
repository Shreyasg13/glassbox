"use client";

import { useCallback, useRef, useState } from "react";
import { apiFetch, jobWsUrl } from "./api";
import type { JobStatus } from "./types";

type LogFrame = { type: "log"; data: { message: string; ts: string } };
type TokenFrame = { type: "token"; data: { text: string } };
type StatusFrame = { type: "status"; data: JobStatus };
type Frame = LogFrame | TokenFrame | StatusFrame;

const POLL_INTERVAL_MS = 2000;

/**
 * Drives a background job (agent test-run, orchestration run, report
 * generate): POSTs to `startUrl`, then follows /ws/jobs/{job_id} for live
 * log/token frames with a REST polling fallback in case the socket never
 * opens (mirrors SignalTicker's reconnect-resilience posture).
 */
export function useJobRun(token: string | null) {
  const [lines, setLines] = useState<string[]>([]);
  const [streamText, setStreamText] = useState("");
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [running, setRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const finish = useCallback(
    (final: JobStatus) => {
      setStatus(final);
      setRunning(false);
      stopPolling();
      wsRef.current?.close();
    },
    [stopPolling]
  );

  const applyFrame = useCallback(
    (frame: Frame) => {
      if (frame.type === "log") {
        setLines((prev) => [...prev, `[${frame.data.ts}] ${frame.data.message}`]);
      } else if (frame.type === "token") {
        setStreamText((prev) => prev + frame.data.text);
      } else if (frame.type === "status") {
        if (frame.data.status === "done" || frame.data.status === "error") {
          finish(frame.data);
        } else {
          setStatus(frame.data);
        }
      }
    },
    [finish]
  );

  const pollStatus = useCallback(
    (jobId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const s = await apiFetch<JobStatus>(`/admin/jobs/${jobId}`, {
            token: token ?? undefined,
          });
          if (s.status === "done" || s.status === "error") {
            finish(s);
          } else {
            setStatus(s);
          }
        } catch {
          // transient — keep polling, don't fail the job over a blip
        }
      }, POLL_INTERVAL_MS);
    },
    [finish, stopPolling, token]
  );

  const run = useCallback(
    async (startUrl: string, body: unknown) => {
      setLines([]);
      setStreamText("");
      setStatus(null);
      setRunning(true);

      try {
        const { job_id } = await apiFetch<{ job_id: string }>(startUrl, {
          method: "POST",
          body: JSON.stringify(body),
          token: token ?? undefined,
        });

        pollStatus(job_id);

        const ws = new WebSocket(jobWsUrl(job_id));
        wsRef.current = ws;
        ws.onmessage = (event) => {
          try {
            applyFrame(JSON.parse(event.data) as Frame);
          } catch {
            // ignore malformed frames
          }
        };
        ws.onerror = () => ws.close();
      } catch (err) {
        finish({
          job_id: "",
          kind: "agent_test_run",
          status: "error",
          created_at: new Date().toISOString(),
          error: err instanceof Error ? err.message : "Failed to start job",
        });
      }
    },
    [applyFrame, finish, pollStatus, token]
  );

  return { run, lines, streamText, status, running };
}
