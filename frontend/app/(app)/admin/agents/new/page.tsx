"use client";

import { AgentForm } from "@/components/admin/AgentForm";
import { emptyAgent } from "@/lib/types";

export default function NewAgentPage() {
  return (
    <div className="flex flex-col gap-sp5">
      <h1 className="text-[18px] font-bold text-t1">New Agent</h1>
      <AgentForm initial={emptyAgent()} />
    </div>
  );
}
