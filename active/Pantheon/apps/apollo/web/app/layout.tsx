import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Orbitron } from "next/font/google";
import "./globals.css";

import { QueryProvider } from "@/lib/query-provider";
import { ScanlineOverlay } from "@/components/hud/ScanlineOverlay";
import { TopBar } from "@/components/hud/TopBar";
import { TabSwitcher } from "@/components/hud/TabSwitcher";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});
const orbitron = Orbitron({
  subsets: ["latin"],
  variable: "--font-orbitron",
  weight: ["500", "700", "900"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Pantheon HUD",
  description: "Apollo voice + Pantheon subsystems — JARVIS-style HUD",
};

export const viewport = {
  themeColor: "#000206",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable} ${orbitron.variable}`}>
      <body className="font-sans antialiased">
        <QueryProvider>
          <ScanlineOverlay />
          <div className="relative z-10 flex min-h-dvh flex-col">
            <TopBar />
            <div className="flex justify-center px-2">
              <TabSwitcher />
            </div>
            <main className="relative flex-1 px-3 py-6 md:px-8 md:py-10">{children}</main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
