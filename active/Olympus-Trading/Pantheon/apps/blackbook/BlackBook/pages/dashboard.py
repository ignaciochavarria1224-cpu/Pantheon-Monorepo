"""
pages/dashboard.py — Dashboard: net worth, account cards, recent transactions.
"""
from __future__ import annotations

import reflex as rx

from BlackBook.state.dashboard_state import DashboardState, TxSummary, AccountBalance


def recent_tx_row(tx: TxSummary) -> rx.Component:
    return rx.el.tr(
        rx.el.td(tx.date),
        rx.el.td(tx.description),
        rx.el.td(tx.category),
        rx.el.td(tx.account),
        rx.el.td(rx.el.span(tx.sign, tx.amount_display, class_name=tx.amount_css)),
    )


def account_card(acct: AccountBalance) -> rx.Component:
    return rx.el.div(
        rx.el.div(acct.name, class_name="bb-acct-name"),
        rx.el.div(acct.balance_display, class_name=rx.cond(
            acct.is_debt, "bb-acct-value debt", "bb-acct-value"
        )),
        rx.el.div(acct.account_type, class_name="bb-acct-type"),
        rx.el.button(
            "hide",
            class_name="bb-acct-hide-btn",
            on_click=DashboardState.toggle_account(acct.id),
        ),
        class_name="bb-acct-card",
    )


def hidden_account_pill(acct: AccountBalance) -> rx.Component:
    return rx.el.button(
        "+ ", acct.name,
        class_name="bb-add-acct-btn",
        on_click=DashboardState.toggle_account(acct.id),
    )


def dashboard_page() -> rx.Component:
    return rx.fragment(
        # Header
        rx.el.div(
            rx.el.h1("Dashboard", class_name="bb-title"),
            rx.el.p("PERSONAL FINANCIAL OS · REAL-TIME INTELLIGENCE", class_name="bb-subtitle"),
            class_name="bb-page-header",
        ),

        rx.cond(
            DashboardState.loading,
            rx.el.div(
                rx.el.span("◌ ", style={"color": "var(--cy)"}),
                rx.el.span("Syncing data..."),
                style={"font_family": "'JetBrains Mono', monospace", "font_size": "0.7rem", "color": "var(--t2)", "margin_bottom": "1rem"},
            ),
        ),
        rx.cond(
            DashboardState.error != "",
            rx.el.div(DashboardState.error, class_name="bb-error"),
        ),

        # ── KPI row ──
        rx.el.div(
            rx.el.div(
                rx.el.div("Net Worth", class_name="bb-stat-label"),
                rx.el.div(
                    DashboardState.net_worth_display,
                    class_name=rx.cond(
                        DashboardState.net_worth >= 0, "bb-stat-value cyan", "bb-stat-value neg"
                    ),
                ),
                class_name="bb-stat",
            ),
            rx.el.div(
                rx.el.div("Total Assets", class_name="bb-stat-label"),
                rx.el.div(DashboardState.assets_display, class_name="bb-stat-value pos"),
                class_name="bb-stat",
            ),
            rx.el.div(
                rx.el.div("Total Debt", class_name="bb-stat-label"),
                rx.el.div(DashboardState.debt_display, class_name="bb-stat-value neg"),
                class_name="bb-stat",
            ),
            class_name="bb-stat-grid",
        ),

        # ── Account balance cards ──
        rx.el.div("Accounts", class_name="bb-section"),
        rx.el.div(
            rx.foreach(DashboardState.visible_accounts, account_card),
            class_name="bb-acct-grid",
        ),

        # Hidden accounts — re-add pills
        rx.cond(
            DashboardState.hidden_accounts.length() > 0,
            rx.el.div(
                rx.el.span(
                    "Hidden: ",
                    style={"font_family": "'JetBrains Mono', monospace", "font_size": "0.46rem",
                           "letter_spacing": "0.2em", "color": "var(--t2)", "text_transform": "uppercase",
                           "margin_right": "0.4rem"},
                ),
                rx.foreach(DashboardState.hidden_accounts, hidden_account_pill),
                class_name="bb-hidden-accts",
            ),
        ),

        # ── Recent activity (compact) ──
        rx.el.div("Recent Activity", class_name="bb-section"),
        rx.el.div(
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        rx.el.th("Date"),
                        rx.el.th("Description"),
                        rx.el.th("Category"),
                        rx.el.th("Account"),
                        rx.el.th("Amount"),
                    )
                ),
                rx.el.tbody(
                    rx.foreach(DashboardState.recent_txns, recent_tx_row),
                ),
                class_name="bb-table bb-table-compact",
            ),
            class_name="bb-table-wrap",
        ),

        on_mount=DashboardState.load,
    )
