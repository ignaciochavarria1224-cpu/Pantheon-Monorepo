import os
import sys
os.environ["BLACKBOOK_DB_PATH"] = r"C:\Users\Ignac\Dropbox\TBD\Pantheon\data\blackbook.db"
sys.path.insert(0, r"C:\Users\Ignac\Dropbox\BlackBook")
from BlackBook.db.queries import load_accounts, load_transactions, calculate_account_balances
accounts = load_accounts()
txns = load_transactions(limit=5000)
balances = calculate_account_balances(accounts, txns)
total_assets = sum(b["balance"] for b in balances if not b["is_debt"])
total_debt = sum(abs(b["balance"]) for b in balances if b["is_debt"])
for b in balances:
    print(f"  {b['name']:<15} ${b['balance']:>10,.2f}  ({b['account_type']})")
print(f"\n  Net Worth: ${total_assets - total_debt:,.2f}  Assets: ${total_assets:,.2f}  Debt: ${total_debt:,.2f}")
