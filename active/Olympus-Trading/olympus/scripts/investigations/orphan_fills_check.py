"""
Phase 4: Cross-check orphan fills (Alpaca-side trades the local DB never recorded).
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

    # Get all trades from DB
    all_trades = conn.execute("""
        SELECT trade_id, symbol, direction, entry_time, exit_time,
               entry_price, exit_price, size, realized_pnl
        FROM trades
        ORDER BY entry_time
    """).fetchall()

    print(f"Total trades in local DB: {len(all_trades)}")

    # Get all Alpaca fills
    client = AlpacaClient()
    after = datetime(2026, 3, 1, tzinfo=timezone.utc)  # From March 1 to be safe
    activities = client.get_activities(after=after)
    fills = [a for a in activities if a.get('activity_type') == 'FILL']

    print(f"Total fills in Alpaca: {len(fills)}")

    # Create a set of (symbol, timestamp, qty, side) tuples from DB trades
    # This is approximate matching since we don't have order IDs
    db_fill_signatures = set()

    for trade in all_trades:
        # Entry leg
        entry_time = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
        entry_side = 'buy' if trade['direction'] == 'long' else 'sell'
        db_fill_signatures.add((trade['symbol'], entry_time, trade['size'], entry_side))

        # Exit leg
        exit_time = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))
        exit_side = 'sell' if trade['direction'] == 'long' else 'buy'
        db_fill_signatures.add((trade['symbol'], exit_time, trade['size'], exit_side))

    print(f"Expected fill signatures from DB: {len(db_fill_signatures)}")

    # Check each Alpaca fill against DB signatures
    orphan_fills = []
    matched_fills = []

    for fill in fills:
        symbol = fill.get('symbol')
        transaction_time = fill.get('transaction_time')
        if transaction_time:
            fill_time = datetime.fromisoformat(transaction_time.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
        else:
            fill_time = None

        qty = fill.get('qty')
        side = fill.get('side')  # This might be the side that was filled

        # Try to match (with some time tolerance)
        matched = False
        if fill_time and symbol and qty and side:
            for db_symbol, db_time, db_qty, db_side in db_fill_signatures:
                time_diff = abs((fill_time - db_time).total_seconds())
                if (db_symbol == symbol and
                    db_side == side and
                    db_qty == int(qty) and
                    time_diff < 300):  # Within 5 minutes
                    matched = True
                    break

        if matched:
            matched_fills.append(fill)
        else:
            orphan_fills.append(fill)

    print(f"Matched fills: {len(matched_fills)}")
    print(f"Orphan fills: {len(orphan_fills)}")

    # Calculate dollar impact of orphan fills
    orphan_dollar_impact = 0.0
    for fill in orphan_fills:
        qty = float(fill.get('qty', 0))
        price = float(fill.get('price', 0))
        orphan_dollar_impact += qty * price

    print(f"Total dollar amount of orphan fills: ${orphan_dollar_impact:.2f}")

    # Show sample orphan fills
    print("\nSample orphan fills:")
    for i, fill in enumerate(orphan_fills[:10]):
        symbol = fill.get('symbol')
        qty = fill.get('qty')
        price = fill.get('price')
        time = fill.get('transaction_time')
        side = fill.get('side')
        print(f"  {i+1}. {symbol} {side} {qty} @ ${price} on {time}")

    conn.close()

if __name__ == "__main__":
    main()