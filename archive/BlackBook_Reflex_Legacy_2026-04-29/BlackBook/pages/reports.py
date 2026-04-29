"""
pages/reports.py — Daily financial snapshots with full detail.
"""
from __future__ import annotations

import reflex as rx

from BlackBook.db import queries


class ReportDisplay(rx.Base):
    report_date: str = ""
    # Net worth
    nw_display: str = ""
    nw_css: str = ""
    # Assets & debt
    assets_display: str = ""
    debt_display: str = ""
    # Portfolio
    portfolio_display: str = ""
    portfolio_pnl_display: str = ""
    portfolio_pnl_css: str = ""
    # Transactions
    txn_count: str = ""
    income_display: str = ""
    spending_display: str = ""
    # Daily food
    food_display: str = ""


class ReportsState(rx.State):
    reports: list[ReportDisplay] = []
    loading: bool = False
    error: str = ""

    @rx.event
    async def load(self) -> None:
        self.loading = True
        try:
            raw = queries.load_daily_reports(limit=30)
            self.reports = [_to_display(r) for r in raw]
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    @rx.event
    async def delete_report(self, report_date: str) -> None:
        try:
            queries.delete_daily_report(report_date)
            raw = queries.load_daily_reports(limit=30)
            self.reports = [_to_display(r) for r in raw]
        except Exception as e:
            self.error = str(e)


def _fmt(val: object, prefix: str = "$") -> str:
    try:
        return f"{prefix}{float(val):,.2f}"
    except Exception:
        return "—"


def _to_display(r: dict) -> ReportDisplay:
    nw = float(r.get("net_worth") or 0)
    pnl = float(r.get("portfolio_pnl") or 0)
    return ReportDisplay(
        report_date=str(r.get("report_date", "")),
        nw_display=_fmt(nw),
        nw_css="pos" if nw >= 0 else "neg",
        assets_display=_fmt(r.get("total_assets") or r.get("assets") or 0),
        debt_display=_fmt(r.get("total_debt") or r.get("debt") or 0),
        portfolio_display=_fmt(r.get("portfolio_value") or 0),
        portfolio_pnl_display=(("+" if pnl >= 0 else "") + _fmt(pnl)),
        portfolio_pnl_css="pos" if pnl >= 0 else "neg",
        txn_count=str(r.get("txn_count") or "—"),
        income_display=_fmt(r.get("income_total") or r.get("income") or 0),
        spending_display=_fmt(r.get("expense_total") or r.get("spending") or r.get("expenses") or 0),
        food_display=_fmt(r.get("food_spend") or r.get("daily_food") or 0),
    )


def _row(label: str, value: str, css: str = "") -> rx.Component:
    return rx.el.div(
        rx.el.span(label, style={"color": "var(--t2)", "font_size": "0.56rem", "letter_spacing": "0.12em"}),
        rx.el.span(value, class_name=css, style={"font_family": "'Syne',sans-serif", "font_weight": "600"}),
        style={
            "display": "flex",
            "justify_content": "space-between",
            "align_items": "center",
            "padding": "0.28rem 0",
            "border_bottom": "1px solid var(--b1)",
        },
    )


def report_card(r: ReportDisplay) -> rx.Component:
    return rx.el.div(
        # Header
        rx.el.div(
            rx.el.span(
                r.report_date,
                style={"font_family": "'Syne', sans-serif", "font_size": "0.95rem", "font_weight": "700", "color": "var(--t0)"},
            ),
            rx.el.button(
                "✕",
                class_name="bb-btn bb-btn-danger",
                on_click=ReportsState.delete_report(r.report_date),
            ),
            style={"display": "flex", "justify_content": "space-between", "align_items": "center", "margin_bottom": "0.8rem"},
        ),

        # Two-column detail grid
        rx.el.div(
            # Left: balance sheet
            rx.el.div(
                rx.el.div(
                    "Balance Sheet",
                    style={"font_size": "0.44rem", "letter_spacing": "0.28em", "text_transform": "uppercase",
                           "color": "var(--cy)", "opacity": "0.7", "margin_bottom": "0.4rem"},
                ),
                _row("Net Worth", r.nw_display, r.nw_css),
                _row("Total Assets", r.assets_display, "pos"),
                _row("Total Debt", r.debt_display, "neg"),
                style={"flex": "1"},
            ),
            # Right: activity
            rx.el.div(
                rx.el.div(
                    "Activity",
                    style={"font_size": "0.44rem", "letter_spacing": "0.28em", "text_transform": "uppercase",
                           "color": "var(--mg)", "opacity": "0.7", "margin_bottom": "0.4rem"},
                ),
                _row("Portfolio Value", r.portfolio_display),
                _row("Portfolio P&L", r.portfolio_pnl_display, r.portfolio_pnl_css),
                _row("Transactions", r.txn_count),
                _row("Income", r.income_display, "pos"),
                _row("Spending", r.spending_display, "neg"),
                _row("Food Spend", r.food_display),
                style={"flex": "1"},
            ),
            style={
                "display": "flex",
                "gap": "1.5rem",
                "font_family": "'JetBrains Mono', monospace",
                "font_size": "0.72rem",
                "color": "var(--t1)",
            },
        ),

        class_name="bb-card",
        style={"margin_bottom": "0.9rem"},
    )


def reports_page() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            rx.el.h1("Reports", class_name="bb-title"),
            rx.el.p("DAILY SNAPSHOTS · FINANCIAL HISTORY", class_name="bb-subtitle"),
            class_name="bb-page-header",
        ),

        rx.cond(ReportsState.error != "", rx.el.div(ReportsState.error, class_name="bb-error")),
        rx.cond(
            ReportsState.loading,
            rx.el.div("Loading...", style={"color": "var(--t2)", "font_size": "0.72rem"}),
            rx.cond(
                ReportsState.reports.length() == 0,
                rx.el.div(
                    "No reports yet. Reports are auto-generated daily.",
                    style={"color": "var(--t2)", "font_size": "0.8rem"},
                ),
                rx.foreach(ReportsState.reports, report_card),
            ),
        ),
        on_mount=ReportsState.load,
    )
