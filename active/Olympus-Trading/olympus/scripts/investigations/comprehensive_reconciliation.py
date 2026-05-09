"""
Phase 5: Comprehensive reconciliation - calculate the true PnL impact of all discrepancies.
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
from collections import defaultdict

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

    # Calculate total PnL from DB trades
    db_total_pnl = sum(trade['realized_pnl'] for trade in all_trades)
    print(f"Total PnL from DB trades: ${db_total_pnl:.2f}")

    # Get all Alpaca fills
    client = AlpacaClient()
    after = datetime(2026, 3, 1, tzinfo=timezone.utc)  # From March 1 to be safe
    activities = client.get_activities(after=after)
    fills = [a for a in activities if a.get('activity_type') == 'FILL']

    print(f"Total fills in Alpaca: {len(fills)}")

    # Calculate net position and cash flow from Alpaca fills
    # This is a simplified approach - in reality we'd need to track positions over time
    symbol_positions = defaultdict(int)
    total_cash_flow = 0.0

    for fill in fills:
        symbol = fill.get('symbol')
        qty = int(fill.get('qty', 0))
        price = float(fill.get('price', 0))
        side = fill.get('side')

        if side == 'buy':
            symbol_positions[symbol] += qty
            total_cash_flow -= qty * price  # Money out
        elif side == 'sell':
            symbol_positions[symbol] -= qty
            total_cash_flow += qty * price  # Money in
        elif side == 'sell_short':
            symbol_positions[symbol] -= qty  # Short position
            total_cash_flow += qty * price  # Money in (borrowing)

    print(f"Net cash flow from Alpaca fills: ${total_cash_flow:.2f}")

    # Check if positions are closed
    open_positions = {sym: pos for sym, pos in symbol_positions.items() if pos != 0}
    print(f"Open positions: {len(open_positions)}")
    if open_positions:
        print("Symbols with open positions:")
        for sym, pos in sorted(open_positions.items())[:10]:  # Show first 10
            print(f"  {sym}: {pos} shares")

    # Calculate what the "true" equity should be
    # This is approximate - we'd need current market prices for open positions
    print("\n=== RECONCILIATION SUMMARY ===")
    print(f"DB-recorded PnL: ${db_total_pnl:.2f}")
    print(f"Alpaca cash flow: ${total_cash_flow:.2f}")
    print(f"Difference: ${db_total_pnl - total_cash_flow:.2f}")

    # Check for the specific April 20 issue
    april_20_trades = [t for t in all_trades if '2026-04-20' in t['entry_time']]
    april_20_pnl = sum(t['realized_pnl'] for t in april_20_trades)
    print(f"\nApril 20 DB PnL: ${april_20_pnl:.2f} (from {len(april_20_trades)} trades)")

    # Get April 20 Alpaca fills
    april_20_fills = [f for f in fills if '2026-04-20' in f.get('transaction_time', '')]
    april_20_cash_flow = 0.0
    for fill in april_20_fills:
        qty = int(fill.get('qty', 0))
        price = float(fill.get('price', 0))
        side = fill.get('side')
        if side == 'buy':
            april_20_cash_flow -= qty * price
        elif side in ['sell', 'sell_short']:
            april_20_cash_flow += qty * price

    print(f"April 20 Alpaca cash flow: ${april_20_cash_flow:.2f} (from {len(april_20_fills)} fills)")
    print(f"April 20 discrepancy: ${april_20_pnl - april_20_cash_flow:.2f}")

    conn.close()

if __name__ == "__main__":
    main()