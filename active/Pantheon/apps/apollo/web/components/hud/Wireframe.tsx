"use client";

import { ReactNode } from "react";
import { useAppStore } from "@/lib/store";

type WireframeRingProps = {
  size?: number; // px
  thickness?: number; // px
  color?: string;
  rotate?: "slow" | "slower" | "none";
  dashed?: boolean;
  ticks?: number; // number of tick marks around the ring
  /** When true, the ring brightens + speeds up with audioLevel from the store. */
  audioReactive?: boolean;
  className?: string;
  children?: ReactNode;
};

export function WireframeRing({
  size = 320,
  thickness = 1,
  color = "rgba(0, 229, 255, 0.42)",
  rotate = "slow",
  dashed = false,
  ticks = 12,
  audioReactive = false,
  className = "",
  children,
}: WireframeRingProps) {
  // We only subscribe when explicitly opted in — keeps the static rings cheap.
  const audio = useAppStore((s) => (audioReactive ? s.audioLevel : 0));

  const animation =
    rotate === "slow"
      ? "animate-spin-slow"
      : rotate === "slower"
        ? "animate-spin-slower"
        : "";
  const radius = size / 2 - thickness * 2;

  // Brighten + nudge rotation speed with audio (CSS animation duration override)
  const opacity = audioReactive ? Math.min(1, 0.55 + audio * 0.55) : 1;
  const speedScale = audioReactive ? Math.max(0.35, 1 - audio * 0.7) : 1;
  const animDuration =
    rotate === "slower"
      ? `${48 * speedScale}s`
      : rotate === "slow"
        ? `${22 * speedScale}s`
        : undefined;

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size, opacity }}
    >
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        className={`absolute inset-0 ${animation}`}
        style={animDuration ? { animationDuration: animDuration } : undefined}
        aria-hidden
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeDasharray={dashed ? "4 6" : undefined}
        />
        {Array.from({ length: ticks }).map((_, i) => {
          const angle = (i / ticks) * Math.PI * 2;
          const inner = radius - 4 - (audioReactive ? audio * 6 : 0);
          const outer = radius + 4 + (audioReactive ? audio * 8 : 0);
          const x1 = size / 2 + Math.cos(angle) * inner;
          const y1 = size / 2 + Math.sin(angle) * inner;
          const x2 = size / 2 + Math.cos(angle) * outer;
          const y2 = size / 2 + Math.sin(angle) * outer;
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={color}
              strokeWidth={thickness}
            />
          );
        })}
      </svg>
      {children}
    </div>
  );
}
