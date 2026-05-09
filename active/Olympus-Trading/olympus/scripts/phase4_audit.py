"""Phase 4 dataset audit -- read-only diagnostics gate for Phase 5 (Apex).

Verifies that the post-repair Phase 4 dataset is sound enough to build
interpretation logic on top of. Reports schema integrity, trade dataset
health, feature completeness, regime distribution, and recent operational
continuity. Strictly read-only -- no schema changes, no data fixes, no
migrations. Output is a printed report to stdout.

Usage (from the olympus/ working directory):
    python scripts/phase4_audit.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, '.')

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import os
try:
    from config.settings import load_settings
    _DEFAULT = str(load_settings().DB_PATH)
except Exception:
    _DEFAULT = 'data/olympus.db'
DB_PATH = Path(os.environ.get('OLYMPUS_AUDIT_DB', _DEFAULT))

EXPECTED_TABLES = (
    'ingestion_runs',
    'ranking_cycles',
    'cycle_rankings',
    'trades',
    'trade_features',
    'system_events',
    'apex_reports',
    'pantheon_conclusions',
)

# The set of columns in trade_features that count as "feature data".
# Identifier-only columns (trade_id, symbol, captured_at, created_at,
# updated_at) are excluded.
EXPECTED_FEATURE_COLUMNS = (
    'roc_5',
    'roc_10',
    'roc_20',
    'acceleration',
    'rvol_at_entry',
    'vwap_deviation_at_entry',
    'range_position_at_entry',
    'raw_score',
    'score_at_entry',
    'close_at_entry',
    'volume_at_entry',
    'vwap_at_entry',
    'atr_at_entry',
    'high_20',
    'low_20',
    'bar_count_used',
)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def fail(msg: str) -> None:
    print()
    print('AUDIT FAILED: ' + msg)
    sys.exit(1)


def header(title: str) -> None:
    print()
    print('=' * 78)
    print(title)
    print('=' * 78)


def subheader(title: str) -> None:
    print()
    print('-- ' + title)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def open_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        fail(f'Database file not found: {db_path.resolve()}')
    uri = f'file:{db_path.as_posix()}?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fetchone(conn: sqlite3.Connection, sql: str, params: Iterable = ()):
    return conn.execute(sql, tuple(params)).fetchone()


def fetchall(conn: sqlite3.Connection, sql: str, params: Iterable = ()):
    return conn.execute(sql, tuple(params)).fetchall()


def require_columns(conn: sqlite3.Connection, table: str,
                    expected: Iterable[str]) -> list[str]:
    rows = fetchall(conn, f'PRAGMA table_info("{table}")')
    if not rows:
        fail(f"Expected table '{table}' is missing or has no columns.")
    actual = [r[1] for r in rows]
    missing = [c for c in expected if c not in actual]
    if missing:
        fail(f"Expected columns missing from {table}: {missing}")
    return actual


# ---------------------------------------------------------------------------
# Section 1 -- Schema & integrity
# ---------------------------------------------------------------------------

def section_1_schema(conn: sqlite3.Connection) -> bool:
    header('SECTION 1 -- SCHEMA & INTEGRITY VERIFICATION')

    flags: list[bool] = []

    # trade_features FK
    row = fetchone(
        conn,
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name='trade_features'",
    )
    if row is None:
        fail("Expected table 'trade_features' is missing.")
    create_sql = row['sql'] or ''
    references_old = 'trades_old' in create_sql
    references_trades = bool(
        re.search(r'REFERENCES\s+"?trades"?\s*\(', create_sql)
    )
    fk_ok = references_trades and not references_old
    flags.append(fk_ok)
    print('trade_features FK references trades (not trades_old): '
          + ('PASS' if fk_ok else 'FAIL'))
    if not fk_ok:
        print('   raw CREATE SQL:')
        print('   ' + create_sql.replace('\n', '\n   '))

    # PRAGMA foreign_key_check
    fk_violations = fetchall(conn, 'PRAGMA foreign_key_check')
    fk_check_ok = len(fk_violations) == 0
    flags.append(fk_check_ok)
    print(f'PRAGMA foreign_key_check: '
          f'{"PASS" if fk_check_ok else "FAIL"} '
          f'(violations: {len(fk_violations)})')
    for v in fk_violations:
        print('   ' + str(dict(v)))

    # PRAGMA integrity_check
    integ_rows = fetchall(conn, 'PRAGMA integrity_check')
    integ_text = '; '.join(str(r[0]) for r in integ_rows)
    integrity_ok = integ_text.strip().lower() == 'ok'
    flags.append(integrity_ok)
    print(f'PRAGMA integrity_check: '
          f'{"PASS" if integrity_ok else "FAIL"} ({integ_text})')

    # Tables with row counts
    subheader('Tables and row counts')
    table_rows = fetchall(
        conn,
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name",
    )
    table_names = [r['name'] for r in table_rows]
    missing = [t for t in EXPECTED_TABLES if t not in table_names]
    if missing:
        fail(f'Expected tables missing from database: {missing}')
    print(f'Total user tables present: {len(table_names)}')
    for t in table_names:
        n = fetchone(conn, f'SELECT COUNT(*) AS n FROM "{t}"')['n']
        print(f'  {t:<25} {n:>10,}')

    # Index count
    idx_count = fetchone(
        conn,
        "SELECT COUNT(*) AS n FROM sqlite_master "
        "WHERE type='index' AND name NOT LIKE 'sqlite_%'",
    )['n']
    subheader('Indexes')
    print(f'Indexes present (excluding auto-indexes): {idx_count}')

    return all(flags)


# ---------------------------------------------------------------------------
# Section 2 -- Trade dataset health
# ---------------------------------------------------------------------------

def section_2_trade_health(conn: sqlite3.Connection) -> int:
    header('SECTION 2 -- TRADE DATASET HEALTH')

    require_columns(
        conn,
        'trades',
        ('trade_id', 'entry_time', 'exit_time', 'realized_pnl', 'regime'),
    )

    total = fetchone(conn, 'SELECT COUNT(*) AS n FROM trades')['n']
    match_note = 'matches' if total == 1527 else 'differs'
    print(f'Total trades: {total:,}  (expected 1,527 -- {match_note})')

    completed = fetchone(
        conn,
        'SELECT COUNT(*) AS n FROM trades '
        'WHERE entry_time IS NOT NULL AND exit_time IS NOT NULL',
    )['n']
    print(f'Completed trades (entry + exit timestamps present): '
          f'{completed:,}')

    incomplete = fetchone(
        conn,
        'SELECT COUNT(*) AS n FROM trades '
        'WHERE entry_time IS NULL OR exit_time IS NULL',
    )['n']
    print(f'Open / incomplete trades (missing entry or exit): '
          f'{incomplete:,}')

    rng = fetchone(
        conn,
        'SELECT MIN(entry_time) AS first_entry, '
        '       MAX(entry_time) AS last_entry, '
        '       MIN(exit_time)  AS first_exit, '
        '       MAX(exit_time)  AS last_exit '
        'FROM trades',
    )
    print(f'Earliest entry_time: {rng["first_entry"]}  (UTC)')
    print(f'Latest   entry_time: {rng["last_entry"]}  (UTC)')
    print(f'Earliest exit_time : {rng["first_exit"]}  (UTC)')
    print(f'Latest   exit_time : {rng["last_exit"]}  (UTC)')

    subheader('Trades per calendar month (by entry_time, UTC)')
    monthly = fetchall(
        conn,
        "SELECT substr(entry_time, 1, 7) AS month, COUNT(*) AS n "
        "FROM trades "
        "WHERE entry_time IS NOT NULL "
        "GROUP BY month ORDER BY month",
    )
    if not monthly:
        print('  (no trades)')
    for r in monthly:
        print(f'  {r["month"]}  {r["n"]:>6,}')

    subheader('Basic PnL sanity (completed trades)')
    pnl = fetchone(
        conn,
        'SELECT COUNT(*) AS n, '
        '       COALESCE(SUM(realized_pnl), 0) AS total_pnl, '
        '       COALESCE(AVG(realized_pnl), 0) AS mean_pnl, '
        '       SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS winners, '
        '       SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) AS losers, '
        '       SUM(CASE WHEN realized_pnl = 0 THEN 1 ELSE 0 END) AS scratches, '
        '       COALESCE(SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl '
        '                         ELSE 0 END), 0) AS gross_win, '
        '       COALESCE(SUM(CASE WHEN realized_pnl < 0 THEN realized_pnl '
        '                         ELSE 0 END), 0) AS gross_loss '
        'FROM trades '
        'WHERE entry_time IS NOT NULL AND exit_time IS NOT NULL',
    )
    n = pnl['n'] or 0
    win_rate = (pnl['winners'] / n * 100.0) if n else 0.0
    if pnl['gross_loss'] != 0:
        pf_str = f'{pnl["gross_win"] / abs(pnl["gross_loss"]):>14.3f}'
    else:
        pf_str = '           inf  (no losing trades)'
    print(f'  Total PnL:        {pnl["total_pnl"]:>14,.2f}')
    print(f'  Mean PnL/trade:   {pnl["mean_pnl"]:>14,.4f}')
    print(f'  Winners:          {pnl["winners"]:>14,}')
    print(f'  Losers:           {pnl["losers"]:>14,}')
    print(f'  Scratch (PnL=0):  {pnl["scratches"]:>14,}')
    print(f'  Win rate:         {win_rate:>13.2f}%')
    print(f'  Gross win:        {pnl["gross_win"]:>14,.2f}')
    print(f'  Gross loss:       {pnl["gross_loss"]:>14,.2f}')
    print(f'  Profit factor:   {pf_str}')

    return total


# ---------------------------------------------------------------------------
# Section 3 -- Feature completeness
# ---------------------------------------------------------------------------

def section_3_features(conn: sqlite3.Connection) -> dict:
    header('SECTION 3 -- FEATURE COMPLETENESS (CRITICAL GAP CHECK)')

    require_columns(conn, 'trade_features',
                    ('trade_id', 'symbol', 'captured_at'))
    require_columns(conn, 'trade_features', EXPECTED_FEATURE_COLUMNS)

    feature_cols = list(EXPECTED_FEATURE_COLUMNS)
    quoted_cols = [f'"{c}"' for c in feature_cols]
    all_nn = ' AND '.join(f'{c} IS NOT NULL' for c in quoted_cols)
    any_null = ' OR '.join(f'{c} IS NULL' for c in quoted_cols)
    # Some feature columns share names with columns on `trades`
    # (e.g. score_at_entry). Use the tf-qualified variant for any
    # query that joins both tables.
    tf_all_nn = ' AND '.join(f'tf."{c}" IS NOT NULL' for c in feature_cols)

    total_feat = fetchone(
        conn, 'SELECT COUNT(*) AS n FROM trade_features',
    )['n']
    print(f'Total rows in trade_features: {total_feat:,}')

    complete = fetchone(
        conn,
        f'SELECT COUNT(*) AS n FROM trade_features WHERE {all_nn}',
    )['n']
    any_null_count = fetchone(
        conn,
        f'SELECT COUNT(*) AS n FROM trade_features WHERE {any_null}',
    )['n']
    print(f'Rows with ALL feature columns populated: {complete:,}')
    print(f'Rows with ANY feature column NULL:        {any_null_count:,}')

    subheader('Per-column NULL counts (trade_features)')
    for c in feature_cols:
        n = fetchone(
            conn,
            f'SELECT COUNT(*) AS n FROM trade_features WHERE "{c}" IS NULL',
        )['n']
        print(f'  {c:<28} {n:>8,}')

    orphans = fetchone(
        conn,
        'SELECT COUNT(*) AS n FROM trades t '
        'LEFT JOIN trade_features tf ON t.trade_id = tf.trade_id '
        'WHERE tf.trade_id IS NULL',
    )['n']
    print(f'\nOrphan trades (in trades but missing trade_features row): '
          f'{orphans:,}')

    earliest = fetchone(
        conn,
        'SELECT MIN(t.entry_time) AS first_complete '
        'FROM trades t '
        'JOIN trade_features tf ON t.trade_id = tf.trade_id '
        f'WHERE {tf_all_nn}',
    )
    earliest_complete = earliest['first_complete'] if earliest else None
    earliest_date = earliest_complete[:10] if earliest_complete else None
    print(f'Earliest trade with complete features: {earliest_complete}  (UTC)')
    if earliest_date:
        print(f'Earliest complete-feature date (YYYY-MM-DD): {earliest_date}')
    else:
        print('Earliest complete-feature date: <none -- no complete-feature '
              'trades exist>')

    pool = 0
    if earliest_date:
        pool = fetchone(
            conn,
            'SELECT COUNT(*) AS n FROM trades '
            'WHERE substr(entry_time, 1, 10) >= ?',
            (earliest_date,),
        )['n']
    print(f'Apex-usable training/interpretation pool '
          f'(trades from earliest complete-feature date forward): {pool:,}')

    return {
        'total_feat': total_feat,
        'complete': complete,
        'any_null': any_null_count,
        'orphans': orphans,
        'earliest_complete_date': earliest_date,
        'pool_size': pool,
        'all_nn': all_nn,
        'tf_all_nn': tf_all_nn,
        'feature_cols': feature_cols,
    }


# ---------------------------------------------------------------------------
# Section 4 -- Regime / condition distribution
# ---------------------------------------------------------------------------

def _print_distribution(label: str, rows: list, total: int) -> tuple[str, float]:
    """Print a (bucket, count) distribution and return the dominant bucket."""
    print(f'\n  {label}:')
    if total == 0 or not rows:
        print('    (no rows)')
        return ('<none>', 0.0)
    top_bucket = '<none>'
    top_pct = 0.0
    for r in rows:
        bucket = r['bucket'] if r['bucket'] is not None else '<NULL>'
        n = r['n']
        pct = (n / total) * 100.0
        if pct > top_pct:
            top_pct = pct
            top_bucket = str(bucket)
        print(f'    {str(bucket):<22} {n:>6,}  {pct:>6.2f}%')
    return top_bucket, top_pct


def section_4_regime(conn: sqlite3.Connection, ctx: dict) -> tuple[bool, str]:
    header('SECTION 4 -- REGIME / CONDITION DISTRIBUTION '
           '(complete-feature trades only)')

    tf_all_nn = ctx['tf_all_nn']
    base_where = (
        'FROM trades t '
        'JOIN trade_features tf ON t.trade_id = tf.trade_id '
        f'WHERE {tf_all_nn}'
    )

    total = fetchone(
        conn,
        f'SELECT COUNT(*) AS n {base_where}',
    )['n']
    print(f'Complete-feature trades available for distribution: {total:,}')

    # 4a -- regime (categorical, from trades.regime)
    regime_rows = fetchall(
        conn,
        f'SELECT t.regime AS bucket, COUNT(*) AS n '
        f'{base_where} GROUP BY t.regime ORDER BY n DESC',
    )
    regime_top_bucket, regime_top_pct = _print_distribution(
        'Regime (trades.regime)', regime_rows, total,
    )

    # 4b -- direction
    dir_rows = fetchall(
        conn,
        f'SELECT t.direction AS bucket, COUNT(*) AS n '
        f'{base_where} GROUP BY t.direction ORDER BY n DESC',
    )
    _print_distribution('Direction (long / short)', dir_rows, total)

    # 4c -- exit_reason
    ex_rows = fetchall(
        conn,
        f'SELECT t.exit_reason AS bucket, COUNT(*) AS n '
        f'{base_where} GROUP BY t.exit_reason ORDER BY n DESC',
    )
    _print_distribution('Exit reason', ex_rows, total)

    # 4d -- rvol_at_entry quintiles (computed from the complete-feature pool)
    rvol_rows = fetchall(
        conn,
        f'SELECT tf.rvol_at_entry AS v {base_where} '
        f'AND tf.rvol_at_entry IS NOT NULL ORDER BY tf.rvol_at_entry',
    )
    rvol_vals = [r['v'] for r in rvol_rows]
    if len(rvol_vals) >= 5:
        n_v = len(rvol_vals)
        cuts = [rvol_vals[int(n_v * p)] for p in (0.2, 0.4, 0.6, 0.8)]
        labels = [
            f'q1 <= {cuts[0]:.3f}',
            f'q2 ({cuts[0]:.3f}, {cuts[1]:.3f}]',
            f'q3 ({cuts[1]:.3f}, {cuts[2]:.3f}]',
            f'q4 ({cuts[2]:.3f}, {cuts[3]:.3f}]',
            f'q5 > {cuts[3]:.3f}',
        ]
        counts = [0, 0, 0, 0, 0]
        for v in rvol_vals:
            if v <= cuts[0]:
                counts[0] += 1
            elif v <= cuts[1]:
                counts[1] += 1
            elif v <= cuts[2]:
                counts[2] += 1
            elif v <= cuts[3]:
                counts[3] += 1
            else:
                counts[4] += 1
        print('\n  rvol_at_entry quintiles:')
        for lbl, c in zip(labels, counts):
            pct = (c / n_v) * 100.0 if n_v else 0.0
            print(f'    {lbl:<28} {c:>6,}  {pct:>6.2f}%')
    else:
        print('\n  rvol_at_entry quintiles:')
        print('    (insufficient data -- fewer than 5 rows)')

    # 4e -- time-of-day buckets (UTC hour of entry_time)
    tod_rows = fetchall(
        conn,
        f'''
        SELECT
            CASE
                WHEN CAST(substr(t.entry_time, 12, 2) AS INTEGER) <  14 THEN 'pre_1400_utc'
                WHEN CAST(substr(t.entry_time, 12, 2) AS INTEGER) <  15 THEN '1400_1459_utc'
                WHEN CAST(substr(t.entry_time, 12, 2) AS INTEGER) <  17 THEN '1500_1659_utc'
                WHEN CAST(substr(t.entry_time, 12, 2) AS INTEGER) <  19 THEN '1700_1859_utc'
                WHEN CAST(substr(t.entry_time, 12, 2) AS INTEGER) <  21 THEN '1900_2059_utc'
                ELSE 'post_2100_utc'
            END AS bucket,
            COUNT(*) AS n
        {base_where}
        GROUP BY bucket
        ORDER BY n DESC
        ''',
    )
    _print_distribution('Time-of-day (entry_time hour, UTC)', tod_rows, total)

    # 4f -- momentum bucket (roc_20)
    mom_rows = fetchall(
        conn,
        f'''
        SELECT
            CASE
                WHEN tf.roc_20 >  5 THEN 'strong_momentum_up'
                WHEN tf.roc_20 >  0 THEN 'mild_momentum_up'
                WHEN tf.roc_20 > -5 THEN 'mild_weakness'
                ELSE                     'strong_weakness'
            END AS bucket,
            COUNT(*) AS n
        {base_where}
        GROUP BY bucket
        ORDER BY n DESC
        ''',
    )
    _print_distribution('Momentum bucket (roc_20)', mom_rows, total)

    # Concentration risk: any single regime bucket >70%
    concentration_risk = regime_top_pct > 70.0
    return concentration_risk, regime_top_bucket


# ---------------------------------------------------------------------------
# Section 5 -- Recent operational continuity
# ---------------------------------------------------------------------------

def section_5_continuity(conn: sqlite3.Connection) -> tuple[bool, dict]:
    header('SECTION 5 -- RECENT OPERATIONAL CONTINUITY')

    require_columns(conn, 'ranking_cycles', ('cycle_timestamp',))

    # Anchor on the most recent trade entry_time (UTC). This makes the
    # check meaningful regardless of when the audit is run, and matches
    # the intent of "one clean trading week since the FK repair."
    anchor_row = fetchone(
        conn,
        'SELECT MAX(substr(entry_time, 1, 10)) AS d FROM trades '
        'WHERE entry_time IS NOT NULL',
    )
    anchor_str = anchor_row['d'] if anchor_row else None
    if anchor_str is None:
        print('No trades in dataset -- recent-continuity check skipped.')
        return False, {'anchor': None, 'gaps': ['<no trades>']}
    print(f'Anchor (most recent entry_time date, UTC): {anchor_str}')

    # 7-day window: anchor minus 6 days .. anchor (inclusive)
    anchor_date = date.fromisoformat(anchor_str)
    window_start = anchor_date - timedelta(days=6)
    window_dates = [
        anchor_date - timedelta(days=i) for i in range(6, -1, -1)
    ]
    print(f'Window: {window_start.isoformat()} .. {anchor_date.isoformat()} '
          f'(7 calendar days, inclusive)')

    trades_n = fetchone(
        conn,
        'SELECT COUNT(*) AS n FROM trades '
        'WHERE substr(entry_time, 1, 10) BETWEEN ? AND ?',
        (window_start.isoformat(), anchor_date.isoformat()),
    )['n']
    cycles_n = fetchone(
        conn,
        'SELECT COUNT(*) AS n FROM ranking_cycles '
        'WHERE substr(cycle_timestamp, 1, 10) BETWEEN ? AND ?',
        (window_start.isoformat(), anchor_date.isoformat()),
    )['n']
    print(f'Trades in last 7 days:          {trades_n:,}')
    print(f'Ranking cycles in last 7 days:  {cycles_n:,}')

    # Per-day breakdown: for each day in window, count trades and cycles.
    trades_by_day = {
        r['d']: r['n'] for r in fetchall(
            conn,
            'SELECT substr(entry_time, 1, 10) AS d, COUNT(*) AS n FROM trades '
            'WHERE substr(entry_time, 1, 10) BETWEEN ? AND ? '
            'GROUP BY d',
            (window_start.isoformat(), anchor_date.isoformat()),
        )
    }
    cycles_by_day = {
        r['d']: r['n'] for r in fetchall(
            conn,
            'SELECT substr(cycle_timestamp, 1, 10) AS d, COUNT(*) AS n '
            'FROM ranking_cycles '
            'WHERE substr(cycle_timestamp, 1, 10) BETWEEN ? AND ? '
            'GROUP BY d',
            (window_start.isoformat(), anchor_date.isoformat()),
        )
    }

    subheader('Per-day breakdown (UTC)')
    print(f'  {"date":<12} {"weekday":<10} {"trades":>8} {"cycles":>8}')
    weekday_gaps: list[str] = []
    for d in window_dates:
        ds = d.isoformat()
        wd = d.strftime('%a')
        is_weekday = d.weekday() < 5  # Mon=0..Fri=4
        t_n = trades_by_day.get(ds, 0)
        c_n = cycles_by_day.get(ds, 0)
        marker = ''
        if is_weekday and t_n == 0 and c_n == 0:
            marker = '  <-- GAP (weekday, no trades or cycles)'
            weekday_gaps.append(ds)
        print(f'  {ds:<12} {wd:<10} {t_n:>8,} {c_n:>8,}{marker}')

    clean_week = len(weekday_gaps) == 0
    print()
    if clean_week:
        print('Clean week: PASS (every weekday in window has trades '
              'or ranking cycles)')
    else:
        print(f'Clean week: FAIL (weekday gaps: {weekday_gaps})')

    return clean_week, {
        'anchor': anchor_str,
        'gaps': weekday_gaps,
        'trades_n': trades_n,
        'cycles_n': cycles_n,
    }


# ---------------------------------------------------------------------------
# Section 6 -- Summary verdict block
# ---------------------------------------------------------------------------

def section_6_verdict(
    schema_ok: bool,
    total: int,
    feat: dict,
    concentration_risk: bool,
    concentration_bucket: str,
    clean_week: bool,
) -> None:
    header('SECTION 6 -- SUMMARY VERDICT')

    pool = feat['pool_size']
    pct = (pool / total * 100.0) if total else 0.0
    earliest_date = feat['earliest_complete_date'] or '<none>'
    orphans = feat['orphans']

    print(f'  Schema integrity:                            '
          f'{"PASS" if schema_ok else "FAIL"}')
    print(f'  Total trades:                                {total:,}')
    print(f'  Apex-usable trades (complete features):      {pool:,}')
    print(f'  Apex-usable percentage:                      {pct:.2f}%')
    print(f'  Earliest complete-feature trade date:        {earliest_date}')
    print(f'  Clean week confirmed since FK repair:        '
          f'{"YES" if clean_week else "NO"}')
    risk_str = 'YES' if concentration_risk else 'NO'
    print(f'  Regime concentration risk (>70% one bucket): '
          f'{risk_str}  (top: {concentration_bucket})')
    print(f'  Orphan trades (trades w/o trade_features):   {orphans:,}')
    print('=' * 78)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print('Olympus Phase 4 dataset audit (read-only diagnostics)')
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    print(f'Run timestamp (UTC): {now_utc.isoformat()}')
    print(f'Database: {DB_PATH.resolve()}')

    conn = open_readonly(DB_PATH)
    try:
        schema_ok = section_1_schema(conn)
        total = section_2_trade_health(conn)
        feat = section_3_features(conn)
        concentration_risk, conc_bucket = section_4_regime(conn, feat)
        clean_week, _continuity = section_5_continuity(conn)
        section_6_verdict(
            schema_ok=schema_ok,
            total=total,
            feat=feat,
            concentration_risk=concentration_risk,
            concentration_bucket=conc_bucket,
            clean_week=clean_week,
        )
    finally:
        conn.close()


if __name__ == '__main__':
    main()
