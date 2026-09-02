"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Provider } from "@/lib/types";
import { JobOutputPanel } from "./JobOutputPanel";

const PROVIDERS: Provider[] = ["vllm", "ollama", "gemini", "claude"];

export function ReportGenerateForm() {
  const router = useRouter();
  const [date, setDate] = useState("");
  const [provider, setProvider] = useState<Provider>("ollama");
  const [model, setModel] = useState("");

  return (
    <div className="glass-panel flex flex-col gap-sp4 p-sp5">
      <div className="grid grid-cols-3 gap-sp4">
        <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
          Date (optional)
          <input
            className="input"
            placeholder="YYYYMMDD, latest if blank"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
          Provider
          <select className="select" value={provider} onChange={(e) => setProvider(e.target.value as Provider)}>
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
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="e.g. llama3.1:8b"
          />
        </label>
      </div>

      <JobOutputPanel
        startUrl="/reports/generate"
        showInput={false}
        runLabel="Generate Report"
        buildBody={() => ({
          date: date || undefined,
          provider,
          model,
        })}
        onDone={(result) => {
          const id = result?.id as string | undefined;
          if (id) router.push(`/reports/${id}`);
        }}
      />
    </div>
  );
}
