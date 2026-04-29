"use client";

import { PulseIndicator } from "@/components/hud/PulseIndicator";
import { useOverview } from "@/lib/hooks";
import { motion } from "framer-motion";

type TopBarProps = {
  title?: string;
};

const READY_KEYS = ["pantheon", "blackbook", "maridian", "olympus"] as const;

export function TopBar({ title = "PANTHEON" }: TopBarProps) {
  const { data } = useOverview();
  const health = data?.health ?? {};

  return (
    <header className="sticky top-0 z-30 backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-cyan/15 bg-ink/70 px-4 py-3 md:px-8">
        <div className="flex items-center gap-3">
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-2"
          >
            <span className="inline-flex h-3 w-3 rounded-full bg-cyan shadow-glow-cyan" />
            <span className="font-display text-base uppercase tracking-widest text-cyan text-glow-cyan">
              {title}
            </span>
            <span className="hidden font-mono text-[10px] uppercase tracking-widestmax text-white/45 md:inline">
              v3.0 · APOLLO HUD
            </span>
          </motion.div>
        </div>

        <div className="flex flex-wrap items-center gap-3 md:gap-5">
          {READY_KEYS.map((key) => {
            const status = (health[key] ?? "unknown").toLowerCase();
            const dot = status === "online" || status === "ok" ? "ok" : status === "degraded" ? "warn" : status === "offline" ? "danger" : "idle";
            return (
              <PulseIndicator
                key={key}
                status={dot as "ok" | "warn" | "danger" | "idle"}
                label={key}
              />
            );
          })}
        </div>
      </div>
    </header>
  );
}
