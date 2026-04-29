"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/apollo", label: "Apollo", code: "01" },
  { href: "/pantheon", label: "Pantheon", code: "02" },
];

export function TabSwitcher() {
  const pathname = usePathname() ?? "";
  return (
    <nav className="mx-auto mt-4 inline-flex items-center gap-1 rounded-md border border-cyan/20 bg-ink/60 p-1 backdrop-blur">
      {TABS.map((tab) => {
        const active = pathname.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className="relative flex items-center gap-2 rounded px-4 py-2 font-mono text-[12px] uppercase tracking-wider transition"
          >
            {active && (
              <motion.span
                layoutId="tab-bg"
                className="absolute inset-0 rounded bg-cyan/15 ring-1 ring-cyan/45"
                transition={{ type: "spring", stiffness: 360, damping: 28 }}
              />
            )}
            <span className={`relative ${active ? "text-cyan text-glow-cyan" : "text-white/55"}`}>
              <span className="mr-2 text-[10px] tracking-widestmax text-white/35">{tab.code}</span>
              {tab.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
