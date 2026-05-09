"""
Phase 3: Investigate April 20, 2026 anomaly specifically.
April 20 had 156 trades but 0 ranking cycles.
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

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

    # Get all trades on April 20, 2026
    april_20_start = "2026-04-20T00:00:00"
    april_20_end = "2026-04-20T23:59:59"

    trades = conn.execute("""
        SELECT trade_id, symbol, direction, entry_time, exit_time,
               entry_price, exit_price, size, realized_pnl
        FROM trades
        WHERE entry_time >= ? AND entry_time < ?
        ORDER BY entry_time
    """, (april_20_start, april_20_end)).fetchall()

    print(f"Trades on April 20, 2026: {len(trades)}")

    # Check ranking cycles on April 20
    cycles = conn.execute("""
        SELECT cycle_id, cycle_timestamp, scored_count, error_count
        FROM ranking_cycles
        WHERE cycle_timestamp >= ? AND cycle_timestamp < ?
        ORDER BY cycle_timestamp
    """, (april_20_start, april_20_end)).fetchall()

    print(f"Ranking cycles on April 20, 2026: {len(cycles)}")

    if cycles:
        for cycle in cycles:
            print(f"  Cycle {cycle['cycle_id'][:8]}: {cycle['scored_count']} scored, {cycle['error_count']} errors")

    # Calculate total PnL for April 20
    total_pnl = sum(trade['realized_pnl'] for trade in trades)
    print(f"Total realized PnL on April 20: ${total_pnl:.2f}")

    # Get Alpaca activities for April 20
    client = AlpacaClient()
    after = datetime(2026, 4, 20, tzinfo=timezone.utc)
    until = datetime(2026, 4, 21, tzinfo=timezone.utc)

    activities = client.get_activities(after=after)
    april_activities = [a for a in activities if a.get('transaction_time', '').startswith('2026-04-20')]

    fills = [a for a in april_activities if a.get('activity_type') == 'FILL']
    non_fills = [a for a in april_activities if a.get('activity_type') != 'FILL']

    print(f"Alpaca activities on April 20: {len(april_activities)}")
    print(f"  Fills: {len(fills)}")
    print(f"  Non-fills: {len(non_fills)}")

    # Calculate net cash flow from activities
    net_cash_flow = 0.0
    for activity in april_activities:
        net_amount = activity.get('net_amount')
        if net_amount:
            try:
                net_cash_flow += float(net_amount)
            except (ValueError, TypeError):
                pass

    print(f"Net cash flow from activities: ${net_cash_flow:.2f}")

    # Sample some trades
    print("\nSample trades from April 20:")
    for i, trade in enumerate(trades[:10]):
        print(f"  {i+1}. {trade['symbol']} {trade['direction'].upper()} {trade['size']} shares: ${trade['realized_pnl']:.2f} PnL")

    # Check for trades with extreme PnL
    extreme_trades = [t for t in trades if abs(t['realized_pnl']) > 100]
    print(f"\nTrades with |PnL| > $100: {len(extreme_trades)}")
    for trade in extreme_trades[:5]:
        print(f"  {trade['symbol']} {trade['direction'].upper()}: ${trade['realized_pnl']:.2f}")

    conn.close()

if __name__ == "__main__":
    main()