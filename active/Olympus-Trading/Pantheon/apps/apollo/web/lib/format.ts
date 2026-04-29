export function fmtUSD(value: number | null | undefined, opts: { signed?: boolean; cents?: boolean } = {}): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return "$—";
  const abs = Math.abs(n);
  const fractionDigits = opts.cents === false ? 0 : 2;
  const formatted = abs.toLocaleString("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
  const sign = opts.signed && n > 0 ? "+" : n < 0 ? "-" : "";
  return `${sign}$${formatted}`;
}

export function fmtNumber(value: number | null | undefined, decimals = 0): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtPct(value: number | null | undefined, decimals = 1): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return "—";
  return `${n.toFixed(decimals)}%`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = Date.now() - d.getTime();
  const sec = Math.round(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  return `${day}d ago`;
}
