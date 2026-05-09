"""
Check total orders vs fills in Alpaca.
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Bootstrap
_OLYMPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_OLYMPUS_ROOT))

from config.settings import load_settings
from core.broker.alpaca import AlpacaClient

def main():
    settings = load_settings()
    client = AlpacaClient()

    # Get all orders from the last 90 days
    after = datetime.now(timezone.utc) - timedelta(days=90)
    all_orders = client.get_orders(after=after, limit=1000)
    print(f"Total orders in last 90 days: {len(all_orders)}")

    # Get all activities (fills) from the last 90 days
    activities = client.get_activities(after=after)
    fills = [a for a in activities if a.get('activity_type') == 'FILL']
    print(f"Total fills in last 90 days: {len(fills)}")

    # Look at a few fills
    print("\nSample fills:")
    for i, fill in enumerate(fills[:5]):
        print(f"  Fill {i+1}: {fill.get('symbol')} {fill.get('qty')} @ {fill.get('price')} on {fill.get('transaction_time')}")

    # Check if fills have order_id
    fills_with_order_id = [f for f in fills if f.get('order_id')]
    print(f"\nFills with order_id: {len(fills_with_order_id)}/{len(fills)}")

    if fills_with_order_id:
        # Try to get one of the orders
        sample_order_id = fills_with_order_id[0].get('order_id')
        order_details = client.get_order(sample_order_id)
        print(f"Sample order lookup for {sample_order_id}: {'FOUND' if order_details else 'NOT FOUND'}")
    status_counts = {}
    for order in all_orders:
        status = order.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    print("Order status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

if __name__ == "__main__":
    main()