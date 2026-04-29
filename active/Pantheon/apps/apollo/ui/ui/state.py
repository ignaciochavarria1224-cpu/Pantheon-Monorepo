from __future__ import annotations

from datetime import datetime
from typing import List

import reflex as rx
import requests
from pydantic import BaseModel

APOLLO_API = "http://localhost:8001"


class Message(BaseModel):
    role: str
    content: str
    timestamp: str = ""


class BalanceItem(BaseModel):
    id: int = 0
    name: str
    balance: str
    account_type: str = ""
    is_debt: bool = False


class TransactionItem(BaseModel):
    date: str
    description: str
    category: str
    account: str
    amount: str
    tx_type: str


class SpendingItem(BaseModel):
    category: str
    total: str
    count: str


class ThemeItem(BaseModel):
    title: str
    preview: str
    updated_at: str


class QuestionItem(BaseModel):
    question: str
    context: str = ""


class HoldingItem(BaseModel):
    symbol: str
    display_name: str
    asset_type: str
    account: str
    quantity: str
    price: str
    value: str
    pnl: str
    pnl_pct: str
    is_positive: bool


class JournalEntry(BaseModel):
    id: int
    entry_date: str
    tag: str
    body: str


class TradeItem(BaseModel):
    symbol: str
    direction: str
    realized_pnl: str
    exit_reason: str
    exit_time: str


class AuditItem(BaseModel):
    timestamp: str
    system: str
    action: str
    detail: str = ""


def _format_timestamp(raw: str | None) -> str:
    if not raw:
        return "Unknown"
    try:
        return datetime.fromisoformat(raw).strftime("%b %d, %H:%M")
    except ValueError:
        return raw


def _truncate(text: str, limit: int) -> str:
    clean = (text or "").strip()
    return clean if len(clean) <= limit else f"{clean[: limit - 1].rstrip()}..."


class State(rx.State):
    active_tab: str = "apollo"
    pantheon_section: str = "overview"

    messages: List[Message] = []
    input_text: str = ""
    is_loading: bool = False
    context_loading: bool = False
    context_error: str = ""
    last_refreshed: str = "Never"

    latest_signal: str = "No recent system activity."
    pantheon_status: str = "Unknown"
    blackbook_status: str = "Unknown"
    maridian_status: str = "Unknown"
    olympus_status: str = "Unknown"
    doctor_current_provider: str = "Unknown"
    doctor_preferred_provider: str = "Unknown"
    doctor_blackbook_reason: str = ""
    doctor_maridian_reason: str = ""
    doctor_olympus_reason: str = ""
    anthropic_status: str = "Unknown"
    anthropic_model: str = ""
    anthropic_reason: str = ""
    ollama_status: str = "Unknown"
    ollama_model: str = ""
    ollama_reason: str = ""
    trace_items: List[AuditItem] = []

    self_model_excerpt: str = "Vault self-model loading..."

    net_worth: str = "$0.00"
    total_assets: str = "$0.00"
    total_debt: str = "$0.00"
    blackbook_balances: List[BalanceItem] = []
    blackbook_transactions: List[TransactionItem] = []
    blackbook_spending: List[SpendingItem] = []
    blackbook_accounts: List[str] = []
    blackbook_notice: str = ""

    blackbook_section: str = "accounts"

    daily_food_left: str = "$0.00"
    weekly_food_left: str = "$0.00"
    lifetime_surplus: str = "$0.00"
    runway_days: str = "0"
    daily_burn: str = "$0.00"
    txns_today: str = "0"

    expense_amount: str = ""
    expense_description: str = ""
    expense_category: str = "Other"
    expense_account: str = ""

    income_amount: str = ""
    income_description: str = ""
    income_account: str = ""

    edit_balance_account_id: int = 0
    edit_balance_name: str = ""
    edit_balance_value: str = ""
    show_edit_balance: bool = False

    holdings: List[HoldingItem] = []
    portfolio_value: str = "$0.00"
    portfolio_pnl: str = "$0.00"
    holdings_last_refresh: str = "Never"

    journal_entries: List[JournalEntry] = []
    journal_form_date: str = ""
    journal_form_tag: str = "General"
    journal_form_body: str = ""
    journal_filter_tag: str = "All"

    bb_daily_food_budget: str = "30"
    bb_pay_period_days: str = "14"
    bb_savings_pct: str = "0.30"
    bb_spending_pct: str = "0.40"
    bb_crypto_pct: str = "0.10"
    bb_taxable_pct: str = "0.10"
    bb_roth_pct: str = "0.10"
    bb_next_payday: str = ""

    maridian_locked: bool = False
    maridian_cycle_count: str = "0"
    maridian_last_cycle: str = "Never"
    maridian_entries_processed: str = "0"
    maridian_questions: List[QuestionItem] = []
    maridian_themes: List[ThemeItem] = []
    maridian_index_excerpt: str = "No current Maridian index available."
    maridian_notice: str = ""
    maridian_running: bool = False

    olympus_total_pnl: str = "$0.00"
    olympus_total_trades: str = "0"
    olympus_avg_r: str = "0.00"
    olympus_last_trade: str = "No trades yet"
    olympus_cycle_summary: str = "No cycle data yet."
    olympus_recent_trades: List[TradeItem] = []
    olympus_report_excerpt: str = "No Olympus report available."

    audit_items: List[AuditItem] = []

    spending_chart_data: List[dict] = []
    pnl_chart_data: List[dict] = []
    toast_message: str = ""
    toast_visible: bool = False
    toast_type: str = "success"

    def switch_to_apollo(self):
        self.active_tab = "apollo"

    def switch_to_pantheon(self):
        self.active_tab = "pantheon"

    def show_overview(self):
        self.pantheon_section = "overview"

    def show_blackbook(self):
        self.pantheon_section = "blackbook"

    def show_maridian(self):
        self.pantheon_section = "maridian"

    def show_olympus(self):
        self.pantheon_section = "olympus"

    def show_activity(self):
        self.pantheon_section = "activity"

    def update_input_text(self, value: str):
        self.input_text = value

    def handle_enter_key(self, key: str):
        if key == "Enter":
            return State.send_message
        return None

    def set_expense_amount(self, value: str):
        self.expense_amount = value

    def set_expense_description(self, value: str):
        self.expense_description = value

    def set_expense_category(self, value: str):
        self.expense_category = value

    def set_expense_account(self, value: str):
        self.expense_account = value

    def set_income_amount(self, value: str):
        self.income_amount = value

    def set_income_description(self, value: str):
        self.income_description = value

    def set_income_account(self, value: str):
        self.income_account = value

    def open_edit_balance(self, account_id: int, name: str, balance: str):
        self.edit_balance_account_id = account_id
        self.edit_balance_name = name
        self.edit_balance_value = balance.lstrip("$").replace(",", "")
        self.show_edit_balance = True

    def close_edit_balance(self):
        self.show_edit_balance = False
        self.edit_balance_value = ""

    def set_edit_balance_value(self, value: str):
        self.edit_balance_value = value

    def save_balance_override(self):
        if not self.edit_balance_account_id:
            return
        try:
            requests.post(
                f"{APOLLO_API}/pantheon/blackbook/accounts/{self.edit_balance_account_id}/balance",
                json={"override": float(self.edit_balance_value or "0")},
                timeout=10,
            ).raise_for_status()
            self.show_toast(f"{self.edit_balance_name} balance updated.", "success")
        except Exception as exc:
            self.show_toast(f"Failed: {exc}", "error")
        self.show_edit_balance = False
        return State.refresh_context

    def show_bb_accounts(self):
        self.blackbook_section = "accounts"

    def show_bb_holdings(self):
        self.blackbook_section = "holdings"

    def show_bb_journal(self):
        self.blackbook_section = "journal"
        return State.load_journal

    def show_bb_settings(self):
        self.blackbook_section = "settings"

    def set_journal_date(self, value: str):
        self.journal_form_date = value

    def set_journal_tag(self, value: str):
        self.journal_form_tag = value

    def set_journal_body(self, value: str):
        self.journal_form_body = value

    def set_journal_filter(self, tag: str):
        self.journal_filter_tag = tag
        return State.load_journal

    def set_bb_daily_food_budget(self, v: str):
        self.bb_daily_food_budget = v

    def set_bb_pay_period_days(self, v: str):
        self.bb_pay_period_days = v

    def set_bb_savings_pct(self, v: str):
        self.bb_savings_pct = v

    def set_bb_spending_pct(self, v: str):
        self.bb_spending_pct = v

    def set_bb_crypto_pct(self, v: str):
        self.bb_crypto_pct = v

    def set_bb_taxable_pct(self, v: str):
        self.bb_taxable_pct = v

    def set_bb_roth_pct(self, v: str):
        self.bb_roth_pct = v

    def set_bb_next_payday(self, v: str):
        self.bb_next_payday = v

    def load_dashboard(self):
        return State.refresh_context

    def refresh_context(self):
        self.context_loading = True
        self.context_error = ""
        yield

        try:
            overview = requests.get(f"{APOLLO_API}/pantheon/overview", timeout=10).json()
            blackbook = requests.get(f"{APOLLO_API}/pantheon/blackbook", timeout=10).json()
            maridian = requests.get(f"{APOLLO_API}/pantheon/maridian", timeout=10).json()
            olympus = requests.get(f"{APOLLO_API}/pantheon/olympus", timeout=10).json()
            activity = requests.get(f"{APOLLO_API}/pantheon/activity", timeout=10).json()

            health = overview.get("health", {})
            self.pantheon_status = health.get("pantheon", "unknown").title()
            self.blackbook_status = health.get("blackbook", "unknown").title()
            self.maridian_status = health.get("maridian", "unknown").title()
            self.olympus_status = health.get("olympus", "unknown").title()

            try:
                doctor = requests.get(f"{APOLLO_API}/pantheon/doctor", timeout=5).json()
                self.doctor_current_provider = doctor.get("current_provider", "none").title()
                self.doctor_preferred_provider = doctor.get("preferred_provider", "unknown").title()
                anth = doctor.get("anthropic") or {}
                self.anthropic_status = "Available" if anth.get("available") else "Unavailable"
                self.anthropic_model = anth.get("model", "")
                self.anthropic_reason = anth.get("reason", "")
                oll = doctor.get("ollama") or {}
                self.ollama_status = "Available" if oll.get("available") else "Unavailable"
                self.ollama_model = oll.get("model", "")
                self.ollama_reason = oll.get("reason", "")
                self.doctor_blackbook_reason = health.get("blackbook_reason", "")
                self.doctor_maridian_reason = health.get("maridian_reason", "")
                self.doctor_olympus_reason = health.get("olympus_reason", "")
            except Exception:
                pass
            self.latest_signal = overview.get("latest_signal", "No recent system activity.")
            self.self_model_excerpt = overview.get("vault", {}).get(
                "self_model_excerpt",
                "Self model is waiting for the first Apollo-written insight.",
            )

            self.net_worth = f"${float(blackbook.get('net_worth', 0) or 0):,.2f}"
            self.total_assets = f"${float(blackbook.get('total_assets', 0) or 0):,.2f}"
            self.total_debt = f"${float(blackbook.get('total_debt', 0) or 0):,.2f}"
            self.daily_food_left = f"${float(blackbook.get('daily_food_left', 0) or 0):,.2f}"
            self.weekly_food_left = f"${float(blackbook.get('weekly_food_left', 0) or 0):,.2f}"
            self.lifetime_surplus = f"${float(blackbook.get('lifetime_surplus', 0) or 0):,.2f}"
            self.runway_days = str(int(blackbook.get('runway_days', 0) or 0))
            self.daily_burn = f"${float(blackbook.get('daily_burn', 0) or 0):,.2f}"
            self.txns_today = str(int(blackbook.get('txns_today', 0) or 0))
            self.blackbook_balances = [
                BalanceItem(
                    id=int(item.get("id") or 0),
                    name=item.get("name", ""),
                    balance=f"${float(item.get('balance', 0) or 0):,.2f}",
                    account_type=item.get("account_type", ""),
                    is_debt=bool(item.get("is_debt")),
                )
                for item in blackbook.get("balances", [])[:8]
            ]
            self.blackbook_transactions = [
                TransactionItem(
                    date=item.get("date", ""),
                    description=_truncate(item.get("description", ""), 48),
                    category=item.get("category", ""),
                    account=item.get("account", ""),
                    amount=f"${float(item.get('amount', 0) or 0):,.2f}",
                    tx_type=item.get("type", ""),
                )
                for item in blackbook.get("recent_transactions", [])[:8]
            ]
            self.blackbook_spending = [
                SpendingItem(
                    category=item.get("category", ""),
                    total=f"${float(item.get('total', 0) or 0):,.2f}",
                    count=str(item.get("count", 0)),
                )
                for item in blackbook.get("spending_month", [])[:6]
            ]
            self.spending_chart_data = [
                {"name": item.get("category", "Other"), "amount": round(float(item.get("total", 0) or 0), 2)}
                for item in blackbook.get("spending_month", [])[:8]
            ]
            self.blackbook_accounts = [item.get("name", "") for item in blackbook.get("accounts", [])]
            if self.blackbook_accounts and not self.expense_account:
                self.expense_account = self.blackbook_accounts[0]
            if self.blackbook_accounts and not self.income_account:
                self.income_account = self.blackbook_accounts[0]

            self.maridian_locked = bool(maridian.get("locked"))
            self.maridian_cycle_count = str(maridian.get("cycle_count", 0))
            self.maridian_entries_processed = str(maridian.get("entries_processed", 0))
            self.maridian_last_cycle = _format_timestamp(maridian.get("last_cycle"))
            self.maridian_questions = [
                QuestionItem(
                    question=item.get("question", ""),
                    context=_truncate(item.get("context", ""), 90),
                )
                for item in maridian.get("today_questions", [])[:6]
            ]
            self.maridian_themes = [
                ThemeItem(
                    title=item.get("title", ""),
                    preview=_truncate(item.get("preview", ""), 120),
                    updated_at=_format_timestamp(item.get("updated_at")),
                )
                for item in maridian.get("top_themes", [])[:6]
            ]
            self.maridian_index_excerpt = maridian.get("index_excerpt") or "No current Maridian index available."

            performance = olympus.get("performance", {}) or {}
            cycle = olympus.get("latest_cycle", {}) or {}
            self.olympus_total_pnl = f"${float(performance.get('total_pnl', 0) or 0):,.2f}"
            self.olympus_total_trades = str(performance.get("total_trades", 0) or 0)
            self.olympus_avg_r = f"{float(performance.get('avg_r_multiple', 0) or 0):.2f}"
            self.olympus_last_trade = _format_timestamp(performance.get("last_trade_at"))
            self.olympus_cycle_summary = (
                f"Cycle {cycle.get('cycle_id', 'n/a')} at {_format_timestamp(cycle.get('cycle_timestamp'))} "
                f"with {cycle.get('scored_count', 0)} scored names."
            )
            self.olympus_recent_trades = [
                TradeItem(
                    symbol=item.get("symbol", ""),
                    direction=item.get("direction", ""),
                    realized_pnl=f"${float(item.get('realized_pnl', 0) or 0):,.2f}",
                    exit_reason=item.get("exit_reason", ""),
                    exit_time=_format_timestamp(item.get("exit_time")),
                )
                for item in olympus.get("recent_trades", [])[:8]
            ]
            self.pnl_chart_data = [
                {
                    "name": f"{item.get('symbol', '')} {item.get('direction', '')[:1]}",
                    "pnl": round(float(item.get("realized_pnl", 0) or 0), 2),
                }
                for item in olympus.get("recent_trades", [])[:8]
            ]
            self.olympus_report_excerpt = _truncate(olympus.get("report_excerpt", ""), 900) or "No Olympus report available."

            self.audit_items = [
                AuditItem(
                    timestamp=_format_timestamp(item.get("timestamp")),
                    system=item.get("system", ""),
                    action=item.get("action", ""),
                    detail=_truncate(item.get("detail", ""), 120),
                )
                for item in activity.get("audit", [])[:10]
            ]
            self.trace_items = self.audit_items[:8]

            try:
                holdings_data = requests.get(f"{APOLLO_API}/pantheon/blackbook/holdings", timeout=10).json()
                self.portfolio_value = f"${float(holdings_data.get('portfolio_value', 0) or 0):,.2f}"
                self.portfolio_pnl = f"${float(holdings_data.get('portfolio_pnl', 0) or 0):,.2f}"
                self.holdings_last_refresh = holdings_data.get("last_refresh") or "Never"
                self.holdings = [
                    HoldingItem(
                        symbol=item.get("symbol", ""),
                        display_name=item.get("display_name", ""),
                        asset_type=item.get("asset_type", ""),
                        account=item.get("account", ""),
                        quantity=f"{float(item.get('quantity', 0) or 0):.4f}",
                        price=f"${float(item.get('price', 0) or 0):,.2f}",
                        value=f"${float(item.get('value', 0) or 0):,.2f}",
                        pnl=f"${float(item.get('pnl', 0) or 0):,.2f}",
                        pnl_pct=f"{float(item.get('pnl_pct', 0) or 0):.1f}%",
                        is_positive=bool(item.get("is_positive", True)),
                    )
                    for item in holdings_data.get("holdings", [])
                ]
            except Exception:
                pass

            try:
                settings_data = requests.get(f"{APOLLO_API}/pantheon/blackbook/settings", timeout=10).json()
                self.bb_daily_food_budget = settings_data.get("daily_food_budget", "30")
                self.bb_pay_period_days = settings_data.get("pay_period_days", "14")
                self.bb_savings_pct = settings_data.get("savings_pct", "0.30")
                self.bb_spending_pct = settings_data.get("spending_pct", "0.40")
                self.bb_crypto_pct = settings_data.get("crypto_pct", "0.10")
                self.bb_taxable_pct = settings_data.get("taxable_investing_pct", "0.10")
                self.bb_roth_pct = settings_data.get("roth_ira_pct", "0.10")
                self.bb_next_payday = settings_data.get("next_payday", "")
            except Exception:
                pass

            self.last_refreshed = datetime.now().strftime("%H:%M:%S")
        except Exception as exc:
            self.context_error = str(exc)
        finally:
            self.context_loading = False

    def load_journal(self):
        try:
            data = requests.get(
                f"{APOLLO_API}/pantheon/blackbook/journal",
                params={"tag": self.journal_filter_tag, "limit": 50},
                timeout=10,
            ).json()
            self.journal_entries = [
                JournalEntry(
                    id=int(item.get("id", 0)),
                    entry_date=item.get("entry_date", ""),
                    tag=item.get("tag", ""),
                    body=item.get("body", ""),
                )
                for item in (data if isinstance(data, list) else [])
            ]
        except Exception:
            pass

    def submit_journal_entry(self):
        if not self.journal_form_body.strip():
            self.show_toast("Body cannot be empty.", "error")
            return
        try:
            requests.post(
                f"{APOLLO_API}/pantheon/blackbook/journal",
                json={
                    "entry_date": self.journal_form_date or None,
                    "tag": self.journal_form_tag,
                    "body": self.journal_form_body,
                },
                timeout=15,
            ).raise_for_status()
            self.show_toast("Entry saved.", "success")
            self.journal_form_body = ""
            self.journal_form_date = ""
        except Exception as exc:
            self.show_toast(f"Failed: {exc}", "error")
        return State.load_journal

    def delete_journal_entry(self, entry_id: int):
        try:
            requests.delete(
                f"{APOLLO_API}/pantheon/blackbook/journal/{entry_id}",
                timeout=10,
            ).raise_for_status()
            self.show_toast("Entry deleted.", "success")
        except Exception as exc:
            self.show_toast(f"Delete failed: {exc}", "error")
        return State.load_journal

    def save_bb_settings(self):
        try:
            requests.post(
                f"{APOLLO_API}/pantheon/blackbook/settings",
                json={"settings": {
                    "daily_food_budget": self.bb_daily_food_budget,
                    "pay_period_days": self.bb_pay_period_days,
                    "savings_pct": self.bb_savings_pct,
                    "spending_pct": self.bb_spending_pct,
                    "crypto_pct": self.bb_crypto_pct,
                    "taxable_investing_pct": self.bb_taxable_pct,
                    "roth_ira_pct": self.bb_roth_pct,
                    "next_payday": self.bb_next_payday,
                }},
                timeout=15,
            ).raise_for_status()
            self.show_toast("Settings saved.", "success")
        except Exception as exc:
            self.show_toast(f"Save failed: {exc}", "error")

    def send_message(self):
        if not self.input_text.strip():
            return

        user_msg = self.input_text.strip()
        timestamp = _format_timestamp(datetime.now().isoformat())
        self.messages.append(Message(role="user", content=user_msg, timestamp=timestamp))
        self.input_text = ""
        self.is_loading = True
        yield

        try:
            response = requests.post(
                f"{APOLLO_API}/chat",
                json={"message": user_msg, "channel": "ui"},
                timeout=180,
            )
            data = response.json()
            self.messages.append(
                Message(
                    role="apollo",
                    content=data.get("response", "Apollo returned an empty response."),
                    timestamp=_format_timestamp(datetime.now().isoformat()),
                )
            )
        except Exception as exc:
            self.messages.append(
                Message(
                    role="apollo",
                    content=f"Error: {exc}",
                    timestamp=_format_timestamp(datetime.now().isoformat()),
                )
            )
        self.is_loading = False
        yield State.refresh_context

    def clear_chat(self):
        self.messages = []
        try:
            requests.post(
                f"{APOLLO_API}/chat",
                json={"message": "", "reset_history": True},
                timeout=5,
            )
        except Exception:
            pass
        return State.refresh_context

    def show_toast(self, message: str, toast_type: str = "success"):
        self.toast_message = message
        self.toast_visible = True
        self.toast_type = toast_type

    def dismiss_toast(self):
        self.toast_visible = False

    def submit_expense(self):
        try:
            requests.post(
                f"{APOLLO_API}/pantheon/blackbook/expense",
                json={
                    "amount": float(self.expense_amount or "0"),
                    "description": self.expense_description,
                    "category": self.expense_category,
                    "account": self.expense_account,
                },
                timeout=15,
            ).raise_for_status()
            self.show_toast("Expense recorded.", "success")
            self.expense_amount = ""
            self.expense_description = ""
        except Exception as exc:
            self.show_toast(f"Expense failed: {exc}", "error")
        return State.refresh_context

    def submit_income(self):
        try:
            requests.post(
                f"{APOLLO_API}/pantheon/blackbook/income",
                json={
                    "amount": float(self.income_amount or "0"),
                    "description": self.income_description,
                    "account": self.income_account,
                },
                timeout=15,
            ).raise_for_status()
            self.show_toast("Income recorded.", "success")
            self.income_amount = ""
            self.income_description = ""
        except Exception as exc:
            self.show_toast(f"Income failed: {exc}", "error")
        return State.refresh_context

    def run_maridian_cycle(self):
        self.maridian_running = True
        yield
        try:
            requests.post(f"{APOLLO_API}/pantheon/maridian/run-cycle", timeout=320).raise_for_status()
            self.show_toast("Maridian cycle completed.", "success")
        except Exception as exc:
            self.show_toast(f"Cycle failed: {exc}", "error")
        self.maridian_running = False
        yield State.refresh_context
