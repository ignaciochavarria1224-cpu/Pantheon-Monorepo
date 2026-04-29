"use client";

import { ReactNode } from "react";

type ListRowProps = {
  primary: ReactNode;
  secondary?: ReactNode;
  trailing?: ReactNode;
  className?: string;
};

export function ListRow({ primary, secondary, trailing, className = "" }: ListRowProps) {
  return (
    <div
      className={`flex items-center justify-between gap-3 border-b border-cyan/10 py-2.5 last:border-b-0 ${className}`}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate font-mono text-[13px] tracking-wider text-white/85">{primary}</div>
        {secondary && (
          <div className="truncate font-mono text-[10px] uppercase tracking-widestmax text-white/40">
            {secondary}
          </div>
        )}
      </div>
      {trailing && <div className="font-mono text-[13px] tabular-nums text-cyan/85">{trailing}</div>}
    </div>
  );
}
