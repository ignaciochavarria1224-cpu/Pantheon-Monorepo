"use client";

export function ScanlineOverlay() {
  return (
    <>
      {/* faint grid that anchors the eye */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 bg-grid-faint bg-grid-md opacity-[0.18]"
      />
      {/* horizontal scanlines */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 bg-scanlines mix-blend-overlay opacity-50 animate-scan-flicker"
      />
      {/* subtle cyan glow at top */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 top-0 z-0 h-40 bg-gradient-to-b from-cyan/10 to-transparent"
      />
      {/* subtle gold glow at bottom right */}
      <div
        aria-hidden
        className="pointer-events-none fixed bottom-0 right-0 z-0 h-72 w-72 bg-[radial-gradient(circle_at_70%_70%,rgba(255,179,71,0.18),transparent_60%)]"
      />
    </>
  );
}
