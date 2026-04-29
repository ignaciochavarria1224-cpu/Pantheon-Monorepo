"""
state/dashboard_state.py — Dashboard metrics, account balances, toggle visibility.
"""
from __future__ import annotations

import reflex as rx

from BlackBook.db import queries


class TxSummary(rx.Base):
    date: str = ""
    description: str = ""
    category: str = ""
    account: str = ""
    sign: str = ""
    amount_display: str = ""
    amount_css: str = ""


class AccountBalance(rx.Base):
    id: int = 0
    name: str = ""
    account_type: str = ""
    is_debt: bool = False
    balance: float = 0.0
    balance_display: str = ""
    balance_css: str = ""


class DashboardState(rx.State):
    accounts: list[dict] = []
    recent_txns: list[TxSummary] = []
    account_balances: list[AccountBalance] = []
    hidden_account_ids: list[int] = []
    settings: dict[str, str] = {}
    net_worth: float = 0.0
    total_assets: float = 0.0
    total_debt: float = 0.0
    daily_reports: list[dict] = []
    loading: bool = False
    error: str = ""

    @rx.event
    async def load(self) -> None:
        self.loading = True
        self.error = ""
        try:
            self.accounts = queries.load_accounts()
            raw_txns = queries.load_transactions(limit=10)
            self.settings = queries.get_settings()
            self.daily_reports = queries.load_daily_reports(limit=7)
            self.recent_txns = [
                TxSummary(
                    date=str(t.get("date") or ""),
                    description=str(t.get("description") or ""),
                    category=str(t.get("category") or ""),
                    account=str(t.get("account") or ""),
                    sign="+" if str(t.get("type")) == "income" else "-",
                    amount_display=f"${abs(float(t.get('amount') or 0)):.2f}",
                    amount_css="pos" if str(t.get("type")) == "income" else "neg",
                )
                for t in raw_txns
            ]
            txns = queries.load_transactions(limit=5000)
            self._compute_balances(txns)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def _compute_balances(self, txns: list[dict]) -> None:
        assets = 0.0
        debt = 0.0
        acct_balances: list[AccountBalance] = []

        for acct in queries.calculate_account_balances(self.accounts, txns):
            bal = float(acct.get("balance") or 0.0)
            is_debt = bool(acct.get("is_debt"))

            if is_debt:
                debt += abs(bal)
                css = "debt"
                display = f"-${abs(bal):,.2f}"
            else:
                assets += bal
                css = "pos" if bal >= 0 else "neg"
                display = f"${bal:,.2f}"

            acct_balances.append(AccountBalance(
                id=int(acct["id"]),
                name=str(acct.get("name") or ""),
                account_type=str(acct.get("account_type") or ""),
                is_debt=is_debt,
                balance=round(bal, 2),
                balance_display=display,
                balance_css=css,
            ))

        self.account_balances = acct_balances
        self.total_assets = round(assets, 2)
        self.total_debt = round(debt, 2)
        self.net_worth = round(assets - debt, 2)

    def toggle_account(self, account_id: int) -> None:
        """Hide or re-show an account card on the dashboard."""
        if account_id in self.hidden_account_ids:
            self.hidden_account_ids = [i for i in self.hidden_account_ids if i != account_id]
        else:
            self.hidden_account_ids = self.hidden_account_ids + [account_id]

    @rx.var
    def visible_accounts(self) -> list[AccountBalance]:
        return [a for a in self.account_balances if a.id not in self.hidden_account_ids]

    @rx.var
    def hidden_accounts(self) -> list[AccountBalance]:
        return [a for a in self.account_balances if a.id in self.hidden_account_ids]

    @rx.var
    def net_worth_display(self) -> str:
        return f"${self.net_worth:,.2f}"

    @rx.var
    def assets_display(self) -> str:
        return f"${self.total_assets:,.2f}"

    @rx.var
    def debt_display(self) -> str:
        return f"${self.total_debt:,.2f}"
