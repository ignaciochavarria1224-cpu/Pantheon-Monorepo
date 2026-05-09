"""
Phase 2: Sample trade-by-trade reconciliation against Alpaca.
For 25 randomly selected trades, compare local DB prices vs Alpaca fill prices.
"""

import sqlite3
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

# Bootstrap: make `olympus/` importable
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

    # Get 25 random trades with a fixed seed for reproducibility
    random.seed(42)  # Fixed seed
    trades = conn.execute("""
        SELECT trade_id, symbol, direction, entry_time, exit_time,
               entry_price, exit_price, size, realized_pnl
        FROM trades
        ORDER BY RANDOM()
        LIMIT 25
    """).fetchall()

    print(f"Sampled {len(trades)} trades for analysis")
    print()

    # Initialize Alpaca client
    client = AlpacaClient()

    results = []
    for trade in trades:
        trade_id = trade['trade_id']
        symbol = trade['symbol']
        direction = trade['direction']
        entry_time = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
        exit_time = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))
        db_entry_price = trade['entry_price']
        db_exit_price = trade['exit_price']
        size = trade['size']
        db_pnl = trade['realized_pnl']

        print(f"Trade {trade_id[:8]}: {direction.upper()} {symbol} {size} shares")
        print(f"  DB entry: ${db_entry_price:.2f} at {entry_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  DB exit:  ${db_exit_price:.2f} at {exit_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  DB PnL:  ${db_pnl:.2f}")

        # Get Alpaca orders for this symbol around the trade times
        # Look back 1 hour before entry, forward 1 hour after exit
        after = entry_time.replace(tzinfo=timezone.utc) if entry_time.tzinfo is None else entry_time
        after = after - timedelta(hours=1)
        until = exit_time.replace(tzinfo=timezone.utc) if exit_time.tzinfo is None else exit_time
        until = until + timedelta(hours=1)

        # First try with time filter
        orders = client.get_orders(symbol=symbol, after=after, until=until)

        # If no orders found, try without time filter to see if orders exist at all
        if not orders:
            orders = client.get_orders(symbol=symbol, limit=100)
            print(f"  Found {len(orders)} orders for {symbol} without time filter")
        else:
            print(f"  Found {len(orders)} orders for {symbol} in time window")
        for order in orders[:3]:  # Show first 3 orders
            print(f"    Order: {order.get('side')} {order.get('qty')} @ {order.get('submitted_at')} status={order.get('status')}")

        # Find entry order: same side as direction, submitted around entry_time
        entry_side = 'buy' if direction == 'long' else 'sell'
        exit_side = 'sell' if direction == 'long' else 'buy'

        entry_order = None
        exit_order = None

        for order in orders:
            submitted = order.get('submitted_at')
            if submitted:
                submitted_dt = datetime.fromisoformat(submitted.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
                time_diff_entry = abs((submitted_dt - entry_time).total_seconds())
                time_diff_exit = abs((submitted_dt - exit_time).total_seconds())

                # Less strict matching: just check side and time proximity
                if (order.get('side') == entry_side and time_diff_entry < 300):  # Within 5 minutes
                    entry_order = order
                elif (order.get('side') == exit_side and time_diff_exit < 300):  # Within 5 minutes
                    exit_order = order

        # Analyze entry leg
        if entry_order:
            alpaca_entry_price = entry_order.get('filled_avg_price')
            entry_status = entry_order.get('status', 'unknown')
            entry_filled_qty = entry_order.get('filled_qty', 0)

            print(f"  Alpaca entry: ${alpaca_entry_price:.2f} (status: {entry_status}, filled: {entry_filled_qty}/{size})")

            if alpaca_entry_price:
                entry_diff = alpaca_entry_price - db_entry_price
                entry_bp = (entry_diff / db_entry_price) * 10000  # basis points
                print(f"    Entry price diff: ${entry_diff:.2f} ({entry_bp:+.0f} bp)")
            else:
                print("    Entry: NO FILL PRICE FROM ALPACA")
        else:
            print("    Entry: NO MATCHING ORDER FOUND")

        # Analyze exit leg
        if exit_order:
            alpaca_exit_price = exit_order.get('filled_avg_price')
            exit_status = exit_order.get('status', 'unknown')
            exit_filled_qty = exit_order.get('filled_qty', 0)

            print(f"  Alpaca exit:  ${alpaca_exit_price:.2f} (status: {exit_status}, filled: {exit_filled_qty}/{size})")

            if alpaca_exit_price:
                exit_diff = alpaca_exit_price - db_exit_price
                exit_bp = (exit_diff / db_exit_price) * 10000  # basis points
                print(f"    Exit price diff: ${exit_diff:.2f} ({exit_bp:+.0f} bp)")
            else:
                print("    Exit: NO FILL PRICE FROM ALPACA")
        else:
            print("    Exit: NO MATCHING ORDER FOUND")

        # Calculate true PnL
        true_entry = entry_order.get('filled_avg_price') if entry_order else db_entry_price
        true_exit = exit_order.get('filled_avg_price') if exit_order else db_exit_price

        if direction == 'long':
            true_pnl = (true_exit - true_entry) * size
        else:
            true_pnl = (true_entry - true_exit) * size

        pnl_diff = true_pnl - db_pnl
        print(f"  True PnL: ${true_pnl:.2f} (diff: ${pnl_diff:.2f})")

        # Check for issues
        issues = []
        if not entry_order:
            issues.append("Entry order not found")
        elif entry_order.get('status') != 'filled':
            issues.append(f"Entry order status: {entry_order.get('status')}")
        elif entry_order.get('filled_qty', 0) != size:
            issues.append(f"Entry partial fill: {entry_order.get('filled_qty', 0)}/{size}")

        if not exit_order:
            issues.append("Exit order not found")
        elif exit_order.get('status') != 'filled':
            issues.append(f"Exit order status: {exit_order.get('status')}")
        elif exit_order.get('filled_qty', 0) != size:
            issues.append(f"Exit partial fill: {exit_order.get('filled_qty', 0)}/{size}")

        if issues:
            print(f"  ISSUES: {', '.join(issues)}")

        results.append({
            'trade_id': trade_id,
            'symbol': symbol,
            'direction': direction,
            'db_pnl': db_pnl,
            'true_pnl': true_pnl,
            'pnl_diff': pnl_diff,
            'entry_order_found': entry_order is not None,
            'exit_order_found': exit_order is not None,
            'entry_status': entry_order.get('status') if entry_order else None,
            'exit_status': exit_order.get('status') if exit_order else None,
            'issues': issues
        })

        print()

    # Summary statistics
    pnl_diffs = [r['pnl_diff'] for r in results]
    print("SUMMARY STATISTICS:")
    print(f"  Sample size: {len(results)}")
    print(f"  Mean PnL difference: ${sum(pnl_diffs)/len(pnl_diffs):.2f}")
    print(f"  Median PnL difference: ${sorted(pnl_diffs)[len(pnl_diffs)//2]:.2f}")
    print(f"  Std dev PnL difference: ${ (sum((x - sum(pnl_diffs)/len(pnl_diffs))**2 for x in pnl_diffs)/len(pnl_diffs))**0.5 :.2f}")
    print(f"  Total PnL difference: ${sum(pnl_diffs):.2f}")

    # Issue breakdown
    entry_not_found = sum(1 for r in results if not r['entry_order_found'])
    exit_not_found = sum(1 for r in results if not r['exit_order_found'])
    entry_not_filled = sum(1 for r in results if r['entry_status'] and r['entry_status'] != 'filled')
    exit_not_filled = sum(1 for r in results if r['exit_status'] and r['exit_status'] != 'filled')

    print()
    print("ISSUES FOUND:")
    print(f"  Entry orders not found: {entry_not_found}")
    print(f"  Exit orders not found: {exit_not_found}")
    print(f"  Entry orders not fully filled: {entry_not_filled}")
    print(f"  Exit orders not fully filled: {exit_not_filled}")

    conn.close()

if __name__ == "__main__":
    main()