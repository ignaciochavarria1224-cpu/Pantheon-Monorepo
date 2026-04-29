"use client";

import { ReactNode } from "react";

type WireframeRingProps = {
  size?: number; // px
  thickness?: number; // px
  color?: string;
  rotate?: "slow" | "slower" | "none";
  dashed?: boolean;
  ticks?: number; // number of tick marks around the ring
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
  className = "",
  children,
}: WireframeRingProps) {
  const animation =
    rotate === "slow"
      ? "animate-spin-slow"
      : rotate === "slower"
        ? "animate-spin-slower"
        : "";
  const radius = size / 2 - thickness * 2;

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        className={`absolute inset-0 ${animation}`}
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
          const inner = radius - 4;
          const outer = radius + 4;
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
