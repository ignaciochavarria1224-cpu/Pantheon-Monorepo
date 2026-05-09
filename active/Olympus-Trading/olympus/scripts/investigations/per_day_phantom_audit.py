"""
Gap 1: Full per-day phantom-trade audit.
Analyzes every calendar date with trades, comparing local DB to Alpaca fills.
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
from collections import defaultdict
import pytz

# Bootstrap
_OLYMPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_OLYMPUS_ROOT))

from config.settings import load_settings
from core.broker.alpaca import AlpacaClient

def main():
    settings = load_settings()

    # Open DB read-only
    db_path = settings.DB_PATH
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    # Get all trades from DB
    all_trades = conn.execute("""
        SELECT trade_id, symbol, direction, entry_time, exit_time,
               entry_price, exit_price, size, realized_pnl
        FROM trades
        ORDER BY entry_time
    """).fetchall()

    print(f"Total trades in local DB: {len(all_trades)}")

    # Group trades by date (UTC)
    trades_by_date = defaultdict(list)
    for trade in all_trades:
        entry_time = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
        date_key = entry_time.date()
        trades_by_date[date_key].append(trade)

    print(f"Dates with trades: {len(trades_by_date)}")

    # Get all Alpaca fills (from March 1 to be safe)
    client = AlpacaClient()
    after = datetime(2026, 3, 1, tzinfo=timezone.utc)
    activities = client.get_activities(after=after)
    fills = [a for a in activities if a.get('activity_type') == 'FILL']

    print(f"Total Alpaca fills: {len(fills)}")

    # Group fills by date (UTC)
    fills_by_date = defaultdict(list)
    for fill in fills:
        transaction_time = fill.get('transaction_time')
        if transaction_time:
            fill_time = datetime.fromisoformat(transaction_time.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
            date_key = fill_time.date()
            fills_by_date[date_key].append(fill)

    # Analyze each date
    results = []
    ny_tz = pytz.timezone('America/New_York')

    for date_key, day_trades in trades_by_date.items():
        local_trade_count = len(day_trades)
        expected_fills = local_trade_count * 2  # entry + exit

        alpaca_fills = fills_by_date.get(date_key, [])
        actual_fills = len(alpaca_fills)

        fill_deficit = expected_fills - actual_fills

        # Local PnL
        local_pnl = sum(trade['realized_pnl'] for trade in day_trades)

        # Alpaca cash flow
        alpaca_cash_flow = 0.0
        for fill in alpaca_fills:
            qty = int(fill.get('qty', 0))
            price = float(fill.get('price', 0))
            side = fill.get('side')

            if side == 'buy':
                alpaca_cash_flow -= qty * price  # Money out
            elif side == 'sell':
                alpaca_cash_flow += qty * price  # Money in
            elif side == 'sell_short':
                alpaca_cash_flow += qty * price  # Money in (short open)

        pnl_discrepancy = local_pnl - alpaca_cash_flow

        # Get weekday
        weekday = date_key.strftime('%A')

        # Convert date to NY time for display
        ny_date = ny_tz.localize(datetime.combine(date_key, datetime.min.time()))
        date_str = ny_date.strftime('%Y-%m-%d')

        results.append({
            'date': date_key,
            'date_str': date_str,
            'weekday': weekday,
            'local_trades': local_trade_count,
            'alpaca_fills': actual_fills,
            'expected_fills': expected_fills,
            'fill_deficit': fill_deficit,
            'local_pnl': local_pnl,
            'alpaca_cash_flow': alpaca_cash_flow,
            'pnl_discrepancy': pnl_discrepancy
        })

    # Sort by absolute PnL discrepancy descending
    results.sort(key=lambda x: abs(x['pnl_discrepancy']), reverse=True)

    # Print top 20 worst days
    print("\n=== TOP 20 WORST DAYS BY PnL DISCREPANCY ===")
    print("Date (NY)    | Weekday | Local Trades | Alpaca Fills | Expected Fills | Fill Deficit | Local PnL | Alpaca Cash Flow | PnL Discrepancy")
    print("-" * 140)

    for i, row in enumerate(results[:20]):
        print(f"{row['date_str']} | {row['weekday'][:3]} | {row['local_trades']:>12} | {row['alpaca_fills']:>12} | {row['expected_fills']:>14} | {row['fill_deficit']:>12} | ${row['local_pnl']:>9,.2f} | ${row['alpaca_cash_flow']:>15,.2f} | ${row['pnl_discrepancy']:>14,.2f}")

    # Summary statistics
    total_dates = len(results)
    dates_with_deficit = sum(1 for r in results if r['fill_deficit'] > 0)
    dates_majority_phantom = sum(1 for r in results if r['fill_deficit'] > r['expected_fills'] * 0.5)
    total_pnl_discrepancy = sum(r['pnl_discrepancy'] for r in results)

    print("\n=== SUMMARY STATISTICS ===")
    print(f"Total dates examined: {total_dates}")
    print(f"Dates with fill deficit > 0: {dates_with_deficit}")
    print(f"Dates where deficit > 50% of expected fills: {dates_majority_phantom}")
    print(f"Sum of PnL discrepancies: ${total_pnl_discrepancy:,.2f}")

    # Check if it matches the known gap
    known_gap = 11344.25
    delta = abs(total_pnl_discrepancy - known_gap)
    if delta <= 50:
        print(f"✓ Matches known gap of ${known_gap:,.2f} (within ${delta:.2f})")
    else:
        print(f"✗ Does not match known gap of ${known_gap:,.2f} (delta: ${delta:.2f})")

    conn.close()

if __name__ == "__main__":
    main()