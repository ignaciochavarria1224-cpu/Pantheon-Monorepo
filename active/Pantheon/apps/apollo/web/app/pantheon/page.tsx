"use client";

import { GlowPanel } from "@/components/hud/GlowPanel";
import { StatReadout } from "@/components/hud/StatReadout";
import { ListRow } from "@/components/hud/ListRow";
import { PulseIndicator } from "@/components/hud/PulseIndicator";
import {
  useBlackBookSnapshot,
  useMaridianSnapshot,
  useOlympusSnapshot,
  useRunMaridianCycle,
  useMaridianCycleStatus,
} from "@/lib/hooks";
import { fmtUSD, fmtNumber, fmtPct, fmtRelative } from "@/lib/format";

export default function PantheonPage() {
  const bb = useBlackBookSnapshot();
  const maridian = useMaridianSnapshot();
  const olympus = useOlympusSnapshot();
  const cycleStatus = useMaridianCycleStatus(maridian.data?.locked ?? false);
  const runCycle = useRunMaridianCycle();

  return (
    <div className="mx-auto grid w-full max-w-[1440px] gap-6 lg:grid-cols-3">
      {/* BlackBook */}
      <GlowPanel
        eyebrow="Subsystem · 01"
        title="BlackBook"
        action={
          <PulseIndicator
            status={
              bb.isError ? "danger" : bb.data?.connected ? "ok" : bb.isLoading ? "idle" : "warn"
            }
            label={bb.isLoading ? "syncing" : bb.data?.connected ? "online" : "offline"}
          />
        }
      >
        <div className="flex flex-col gap-5">
          <StatReadout
            label="Net worth"
            value={fmtUSD(bb.data?.net_worth)}
            sub={`Assets ${fmtUSD(bb.data?.total_assets, { cents: false })} · Debt ${fmtUSD(bb.data?.total_debt, { cents: false })}`}
            accent="gold"
            size="lg"
          />
          <div className="grid grid-cols-2 gap-4">
            <StatReadout label="Runway" value={`${fmtNumber(bb.data?.runway_days)}d`} />
            <StatReadout
              label="Lifetime surplus"
              value={fmtUSD(bb.data?.lifetime_surplus, { cents: false })}
              accent="ok"
            />
            <StatReadout
              label="Daily food left"
              value={fmtUSD(bb.data?.daily_food_left, { cents: false })}
            />
            <StatReadout label="Tx today" value={fmtNumber(bb.data?.txns_today)} />
          </div>

          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-widestmax text-white/45">
              Recent transactions
            </div>
            <div>
              {(bb.data?.recent_transactions ?? []).slice(0, 6).map((tx) => (
                <ListRow
                  key={tx.id}
                  primary={tx.description || tx.category}
                  secondary={`${tx.account} · ${tx.category} · ${tx.date}`}
                  trailing={
                    <span className={tx.type === "income" ? "text-signal-ok" : "text-gold"}>
                      {tx.type === "income" ? "+" : "−"}
                      {fmtUSD(Math.abs(Number(tx.amount)), { cents: false }).replace("$", "$")}
                    </span>
                  }
                />
              ))}
              {(bb.data?.recent_transactions ?? []).length === 0 && (
                <div className="py-3 font-mono text-[11px] tracking-wider text-white/35">
                  No transactions yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </GlowPanel>

      {/* Maridian */}
      <GlowPanel
        eyebrow="Subsystem · 02"
        title="Maridian"
        action={
          <PulseIndicator
            status={
              maridian.data?.locked
                ? "warn"
                : maridian.data?.connected
                  ? "ok"
                  : maridian.isLoading
                    ? "idle"
                    : "danger"
            }
            label={maridian.data?.locked ? "running" : maridian.data?.connected ? "idle" : "offline"}
          />
        }
      >
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-4">
            <StatReadout label="Cycle" value={fmtNumber(maridian.data?.cycle_count)} />
            <StatReadout label="Entries" value={fmtNumber(maridian.data?.entries_processed)} />
          </div>

          <StatReadout
            label="Last cycle"
            value={fmtRelative(maridian.data?.last_cycle ?? null)}
            sub={maridian.data?.last_cycle ?? "never"}
            size="md"
          />

          <button
            type="button"
            onClick={() => runCycle.mutate()}
            disabled={runCycle.isPending || maridian.data?.locked}
            className="flex items-center justify-between rounded border border-cyan/40 px-3 py-2 font-mono text-[12px] uppercase tracking-wider text-cyan transition hover:border-glow-cyan-strong hover:text-glow-cyan disabled:cursor-not-allowed disabled:opacity-40"
          >
            <span>
              {maridian.data?.locked
                ? "cycle running…"
                : runCycle.isPending
                  ? "starting…"
                  : "run cycle"}
            </span>
            <span className="text-white/45">
              {cycleStatus.data?.last_result ?? "—"}
            </span>
          </button>

          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-widestmax text-white/45">
              Today&apos;s questions
            </div>
            <div>
              {(maridian.data?.today_questions ?? []).slice(0, 5).map((q, i) => {
                const text = typeof q === "string" ? q : q.question;
                return (
                  <ListRow
                    key={i}
                    primary={text}
                    secondary={typeof q === "string" ? "" : q.tag ?? ""}
                  />
                );
              })}
              {(maridian.data?.today_questions ?? []).length === 0 && (
                <div className="py-3 font-mono text-[11px] tracking-wider text-white/35">
                  No questions generated yet today.
                </div>
              )}
            </div>
          </div>

          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-widestmax text-white/45">
              Top themes
            </div>
            <div>
              {(maridian.data?.top_themes ?? []).slice(0, 4).map((theme) => (
                <ListRow
                  key={theme.path}
                  primary={theme.title}
                  secondary={fmtRelative(theme.updated_at)}
                />
              ))}
            </div>
          </div>
        </div>
      </GlowPanel>

      {/* Olympus */}
      <GlowPanel
        eyebrow="Subsystem · 03"
        title="Olympus"
        action={
          <PulseIndicator
            status={
              olympus.data?.connected ? "ok" : olympus.isLoading ? "idle" : "danger"
            }
            label={olympus.data?.connected ? "online" : "offline"}
          />
        }
      >
        <div className="flex flex-col gap-5">
          <StatReadout
            label="Total PnL"
            value={fmtUSD(olympus.data?.performance.total_pnl, { signed: true })}
            sub={`${fmtNumber(olympus.data?.performance.total_trades)} trades · win ${fmtPct(olympus.data?.performance.win_rate_pct)}`}
            accent={
              (olympus.data?.performance.total_pnl ?? 0) > 0
                ? "ok"
                : (olympus.data?.performance.total_pnl ?? 0) < 0
                  ? "warn"
                  : "gold"
            }
            size="lg"
          />

          <div className="grid grid-cols-2 gap-4">
            <StatReadout
              label="Avg R"
              value={fmtNumber(olympus.data?.performance.avg_r_multiple, 2)}
            />
            <StatReadout
              label="Avg PnL"
              value={fmtUSD(olympus.data?.performance.avg_pnl)}
            />
          </div>

          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-widestmax text-white/45">
              Top longs
            </div>
            <div>
              {(olympus.data?.latest_cycle?.top_longs ?? []).slice(0, 5).map((row) => (
                <ListRow
                  key={`L-${row.symbol}`}
                  primary={row.symbol}
                  secondary={`rank #${row.rank}`}
                  trailing={fmtNumber(row.score, 1)}
                />
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-widestmax text-white/45">
              Top shorts
            </div>
            <div>
              {(olympus.data?.latest_cycle?.top_shorts ?? []).slice(0, 5).map((row) => (
                <ListRow
                  key={`S-${row.symbol}`}
                  primary={row.symbol}
                  secondary={`rank #${row.rank}`}
                  trailing={fmtNumber(row.score, 1)}
                />
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-widestmax text-white/45">
              Recent trades
            </div>
            <div>
              {(olympus.data?.recent_trades ?? []).slice(0, 4).map((tr, i) => (
                <ListRow
                  key={`${tr.symbol}-${i}`}
                  primary={`${tr.symbol} ${tr.direction.toUpperCase()}`}
                  secondary={`${tr.exit_reason} · ${fmtRelative(tr.exit_time)}`}
                  trailing={
                    <span className={tr.realized_pnl >= 0 ? "text-signal-ok" : "text-signal-danger"}>
                      {fmtUSD(tr.realized_pnl, { signed: true })}
                    </span>
                  }
                />
              ))}
            </div>
          </div>
        </div>
      </GlowPanel>
    </div>
  );
}
