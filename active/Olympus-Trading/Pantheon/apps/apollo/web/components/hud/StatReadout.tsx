"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

type StatReadoutProps = {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: "cyan" | "gold" | "ok" | "warn" | "danger" | "mute";
  size?: "md" | "lg" | "xl";
  className?: string;
};

const accentClass: Record<NonNullable<StatReadoutProps["accent"]>, string> = {
  cyan: "text-cyan text-glow-cyan",
  gold: "text-gold text-glow-gold",
  ok: "text-signal-ok",
  warn: "text-signal-warn",
  danger: "text-signal-danger",
  mute: "text-signal-mute",
};

const sizeClass: Record<NonNullable<StatReadoutProps["size"]>, string> = {
  md: "text-2xl",
  lg: "text-4xl",
  xl: "text-6xl md:text-7xl",
};

export function StatReadout({
  label,
  value,
  sub,
  accent = "cyan",
  size = "md",
  className = "",
}: StatReadoutProps) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div className="font-mono text-[10px] uppercase tracking-widestmax text-white/55">
        {label}
      </div>
      <motion.div
        key={String(value)}
        initial={{ opacity: 0.5, y: 2 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.24 }}
        className={`font-mono ${sizeClass[size]} font-semibold tabular-nums ${accentClass[accent]}`}
      >
        {value}
      </motion.div>
      {sub && <div className="font-mono text-[11px] tracking-wider text-white/45">{sub}</div>}
    </div>
  );
}
