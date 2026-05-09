"""
Gap 2: Per-trade price comparison (slippage check).
Analyzes price slippage on 100 randomly selected trades (excluding April 20).
Uses heuristic matching since no direct linkage exists.
"""

import sqlite3
import random
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

    # Get 100 random trades excluding April 20, with fixed seed
    random.seed(42)  # Fixed seed for reproducibility
    trades = conn.execute("""
        SELECT trade_id, symbol, direction, entry_time, exit_time,
               entry_price, exit_price, size, realized_pnl
        FROM trades
        WHERE entry_time NOT LIKE '2026-04-20%'
        ORDER BY RANDOM()
        LIMIT 100
    """).fetchall()

    print(f"Sampled {len(trades)} trades for slippage analysis (excluding April 20)")
    print("NOTE: Using heuristic matching (symbol + side + qty + time ±60s) since no direct linkage exists")
    print()

    # Get all Alpaca fills (from March 1 to be safe)
    client = AlpacaClient()
    after = datetime(2026, 3, 1, tzinfo=timezone.utc)
    activities = client.get_activities(after=after)
    fills = [a for a in activities if a.get('activity_type') == 'FILL']

    print(f"Total Alpaca fills available: {len(fills)}")

    # Group fills by symbol for faster lookup
    fills_by_symbol = defaultdict(list)
    for fill in fills:
        symbol = fill.get('symbol')
        fills_by_symbol[symbol].append(fill)

    results = []
    matched_both_legs = 0
    matched_one_leg = 0
    matched_zero_legs = 0

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

        # Determine expected sides
        entry_side = 'buy' if direction == 'long' else 'sell'
        exit_side = 'sell' if direction == 'long' else 'buy'

        # Find matching fills using heuristic
        symbol_fills = fills_by_symbol.get(symbol, [])

        entry_fill = None
        exit_fill = None

        for fill in symbol_fills:
            fill_time_str = fill.get('transaction_time')
            if not fill_time_str:
                continue
            fill_time = datetime.fromisoformat(fill_time_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
            fill_qty = int(fill.get('qty', 0))
            fill_side = fill.get('side')
            fill_price = float(fill.get('price', 0))

            # Check entry leg match
            if (fill_side == entry_side and
                fill_qty == size and
                abs((fill_time - entry_time).total_seconds()) <= 60):  # Within 60 seconds
                entry_fill = fill

            # Check exit leg match
            if (fill_side == exit_side and
                fill_qty == size and
                abs((fill_time - exit_time).total_seconds()) <= 60):  # Within 60 seconds
                exit_fill = fill

        # Count matches
        entry_matched = entry_fill is not None
        exit_matched = exit_fill is not None

        if entry_matched and exit_matched:
            matched_both_legs += 1
        elif entry_matched or exit_matched:
            matched_one_leg += 1
        else:
            matched_zero_legs += 1

        # Calculate slippage for matched legs
        entry_slippage_dollars = 0.0
        entry_slippage_bp = 0.0
        exit_slippage_dollars = 0.0
        exit_slippage_bp = 0.0
        pnl_delta = 0.0

        if entry_matched:
            alpaca_entry_price = float(entry_fill.get('price', 0))
            entry_slippage_dollars = alpaca_entry_price - db_entry_price
            entry_slippage_bp = (entry_slippage_dollars / db_entry_price) * 10000

        if exit_matched:
            alpaca_exit_price = float(exit_fill.get('price', 0))
            exit_slippage_dollars = alpaca_exit_price - db_exit_price
            exit_slippage_bp = (exit_slippage_dollars / db_exit_price) * 10000

        # Calculate true PnL delta if both legs matched
        if entry_matched and exit_matched:
            alpaca_entry_price = float(entry_fill.get('price', 0))
            alpaca_exit_price = float(exit_fill.get('price', 0))

            if direction == 'long':
                alpaca_pnl = (alpaca_exit_price - alpaca_entry_price) * size
            else:
                alpaca_pnl = (alpaca_entry_price - alpaca_exit_price) * size

            pnl_delta = alpaca_pnl - db_pnl

        results.append({
            'trade_id': trade_id,
            'symbol': symbol,
            'direction': direction,
            'entry_matched': entry_matched,
            'exit_matched': exit_matched,
            'entry_slippage_dollars': entry_slippage_dollars,
            'entry_slippage_bp': entry_slippage_bp,
            'exit_slippage_dollars': exit_slippage_dollars,
            'exit_slippage_bp': exit_slippage_bp,
            'pnl_delta': pnl_delta
        })

    # Summary statistics
    matched_trades = [r for r in results if r['entry_matched'] or r['exit_matched']]
    fully_matched_trades = [r for r in results if r['entry_matched'] and r['exit_matched']]

    print("=== MATCHING RESULTS ===")
    print(f"Trades with both legs matched: {matched_both_legs}")
    print(f"Trades with one leg matched: {matched_one_leg}")
    print(f"Trades with zero legs matched: {matched_zero_legs}")
    print(f"Total trades analyzed: {len(results)}")

    if fully_matched_trades:
        print("\n=== SLIPPAGE STATISTICS (fully matched trades only) ===")
        entry_slippages = [r['entry_slippage_dollars'] for r in fully_matched_trades]
        exit_slippages = [r['exit_slippage_dollars'] for r in fully_matched_trades]
        pnl_deltas = [r['pnl_delta'] for r in fully_matched_trades]

        print("Entry slippage:")
        print(f"  Mean: ${sum(entry_slippages)/len(entry_slippages):.2f}")
        print(f"  Median: ${sorted(entry_slippages)[len(entry_slippages)//2]:.2f}")
        print(f"  Std dev: ${ (sum((x - sum(entry_slippages)/len(entry_slippages))**2 for x in entry_slippages)/len(entry_slippages))**0.5 :.2f}")

        print("Exit slippage:")
        print(f"  Mean: ${sum(exit_slippages)/len(exit_slippages):.2f}")
        print(f"  Median: ${sorted(exit_slippages)[len(exit_slippages)//2]:.2f}")
        print(f"  Std dev: ${ (sum((x - sum(exit_slippages)/len(exit_slippages))**2 for x in exit_slippages)/len(exit_slippages))**0.5 :.2f}")

        print("PnL delta:")
        print(f"  Mean: ${sum(pnl_deltas)/len(pnl_deltas):.2f}")
        print(f"  Median: ${sorted(pnl_deltas)[len(pnl_deltas)//2]:.2f}")
        print(f"  Std dev: ${ (sum((x - sum(pnl_deltas)/len(pnl_deltas))**2 for x in pnl_deltas)/len(pnl_deltas))**0.5 :.2f}")

        total_pnl_delta = sum(pnl_deltas)
        print(f"Sum of PnL deltas: ${total_pnl_delta:.2f}")

        # Extrapolate to full dataset
        extrapolated_slippage = (total_pnl_delta / len(fully_matched_trades)) * 1538
        print(f"Extrapolated dataset-wide slippage: ${extrapolated_slippage:.2f}")
    else:
        print("\nNo trades had both legs matched - cannot calculate slippage statistics")

    conn.close()

if __name__ == "__main__":
    main()