import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#030712",
          deep: "#000206",
          surface: "rgba(7, 12, 22, 0.72)",
          panel: "rgba(10, 18, 32, 0.55)",
          line: "rgba(0, 229, 255, 0.18)",
          lineStrong: "rgba(0, 229, 255, 0.36)",
        },
        cyan: {
          DEFAULT: "#00e5ff",
          glow: "#5ef6ff",
          dim: "#0090a8",
          deep: "#003a44",
        },
        gold: {
          DEFAULT: "#ffb347",
          glow: "#ffd28a",
          dim: "#a96d18",
        },
        signal: {
          ok: "#3dd68c",
          warn: "#ffb347",
          danger: "#ff6868",
          mute: "rgba(255, 255, 255, 0.42)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
        display: ["var(--font-orbitron)", "var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        wider: "0.06em",
        widest: "0.12em",
        widestmax: "0.2em",
      },
      boxShadow: {
        "glow-cyan": "0 0 16px rgba(0, 229, 255, 0.42), inset 0 0 22px rgba(0, 229, 255, 0.10)",
        "glow-cyan-lg": "0 0 28px rgba(0, 229, 255, 0.55), inset 0 0 32px rgba(0, 229, 255, 0.16)",
        "glow-gold": "0 0 14px rgba(255, 179, 71, 0.55)",
      },
      backgroundImage: {
        "scanlines": "repeating-linear-gradient(180deg, rgba(0,229,255,0.04) 0px, rgba(0,229,255,0.04) 1px, transparent 1px, transparent 3px)",
        "grid-faint": "linear-gradient(rgba(0,229,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(0,229,255,0.06) 1px, transparent 1px)",
      },
      backgroundSize: {
        "grid-md": "44px 44px",
      },
      keyframes: {
        "pulse-cyan": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(0, 229, 255, 0.55)" },
          "50%": { boxShadow: "0 0 0 6px rgba(0, 229, 255, 0)" },
        },
        "spin-slow": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        "ticker": {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-50%)" },
        },
        "scan-flicker": {
          "0%, 100%": { opacity: "0.32" },
          "50%": { opacity: "0.18" },
        },
      },
      animation: {
        "pulse-cyan": "pulse-cyan 2.4s ease-out infinite",
        "spin-slow": "spin-slow 22s linear infinite",
        "spin-slower": "spin-slow 48s linear infinite",
        "ticker": "ticker 38s linear infinite",
        "scan-flicker": "scan-flicker 4.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
