"use client";

import { OrchestrationForm } from "@/components/admin/OrchestrationForm";
import { emptyOrchestration } from "@/lib/types";

export default function NewOrchestrationPage() {
  return (
    <div className="flex flex-col gap-sp5">
      <h1 className="text-[18px] font-bold text-t1">New Orchestration</h1>
      <OrchestrationForm initial={emptyOrchestration()} />
    </div>
  );
}
