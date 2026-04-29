"use client";

type PulseIndicatorProps = {
  status: "ok" | "warn" | "danger" | "idle";
  label?: string;
  size?: "sm" | "md";
  className?: string;
};

const statusColor: Record<PulseIndicatorProps["status"], string> = {
  ok: "bg-signal-ok",
  warn: "bg-signal-warn",
  danger: "bg-signal-danger",
  idle: "bg-white/30",
};

export function PulseIndicator({
  status,
  label,
  size = "sm",
  className = "",
}: PulseIndicatorProps) {
  const dim = size === "md" ? "h-2.5 w-2.5" : "h-1.5 w-1.5";
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="relative inline-flex">
        <span className={`relative inline-block rounded-full ${dim} ${statusColor[status]}`} />
        {status !== "idle" && (
          <span
            className={`absolute inset-0 rounded-full ${statusColor[status]} opacity-70 animate-pulse-cyan`}
          />
        )}
      </span>
      {label && (
        <span className="font-mono text-[10px] uppercase tracking-widestmax text-white/65">
          {label}
        </span>
      )}
    </span>
  );
}
