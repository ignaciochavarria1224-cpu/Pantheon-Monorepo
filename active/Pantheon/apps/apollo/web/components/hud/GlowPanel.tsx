"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

type GlowPanelProps = {
  title?: string;
  eyebrow?: string;
  accent?: "cyan" | "gold";
  children: ReactNode;
  className?: string;
  action?: ReactNode;
};

export function GlowPanel({
  title,
  eyebrow,
  accent = "cyan",
  children,
  className = "",
  action,
}: GlowPanelProps) {
  const accentText = accent === "gold" ? "text-gold" : "text-cyan";
  const accentGlow = accent === "gold" ? "text-glow-gold" : "text-glow-cyan";
  const borderGlow =
    accent === "gold"
      ? "border-gold/30 shadow-glow-gold"
      : "border-cyan/30 shadow-glow-cyan";

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.36, ease: "easeOut" }}
      className={`relative glass-panel border ${borderGlow} corner-clip ${className}`}
    >
      {/* corner ticks — subtle blueprint marks */}
      <span className={`pointer-events-none absolute left-2 top-2 h-2 w-2 border-l border-t ${accentText}/60`} />
      <span className={`pointer-events-none absolute right-2 top-2 h-2 w-2 border-r border-t ${accentText}/60`} />
      <span className={`pointer-events-none absolute left-2 bottom-2 h-2 w-2 border-l border-b ${accentText}/60`} />
      <span className={`pointer-events-none absolute right-2 bottom-2 h-2 w-2 border-r border-b ${accentText}/60`} />

      {(title || eyebrow || action) && (
        <header className="flex items-start justify-between border-b border-cyan/15 px-5 py-3">
          <div>
            {eyebrow && (
              <div className={`font-mono text-[10px] uppercase tracking-widestmax ${accentText}/70`}>
                {eyebrow}
              </div>
            )}
            {title && (
              <h3 className={`mt-1 font-display text-sm uppercase tracking-wider ${accentText} ${accentGlow}`}>
                {title}
              </h3>
            )}
          </div>
          {action}
        </header>
      )}

      <div className="px-5 py-4">{children}</div>
    </motion.section>
  );
}
