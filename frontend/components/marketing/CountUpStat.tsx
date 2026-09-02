"use client";

import { useCountUp } from "@/lib/useCountUp";

export function CountUpStat({
  target,
  decimals,
  suffix,
  label,
  color,
}: {
  target: number;
  decimals: number;
  suffix: string;
  label: string;
  color: string;
}) {
  const { ref, display } = useCountUp(target, { decimals });

  return (
    <div ref={ref}>
      <div className={`mono text-[24px] font-extrabold ${color}`}>
        {display}
        {suffix}
      </div>
      <div className="text-[11.5px] text-t3">{label}</div>
    </div>
  );
}
