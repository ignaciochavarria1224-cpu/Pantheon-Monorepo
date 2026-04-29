"""
state/app_state.py — Root application state.
Handles navigation and top-level data seeding.
"""
from __future__ import annotations

import reflex as rx

PAGES = [
    "dashboard",
    "transactions",
    "allocation",
    "investments",
    "reports",
    "journal",
    "reconcile",
    "agenda",
    "advisor",
    "meridian",
    "settings",
]

PAGE_LABELS = {
    "dashboard":    "Dashboard",
    "transactions": "Log Transaction",
    "allocation":   "Allocation",
    "investments":  "Investments",
    "reports":      "Reports",
    "journal":      "Journal",
    "reconcile":    "Reconcile",
    "agenda":       "Agenda",
    "advisor":      "Advisor",
    "meridian":     "Meridian",
    "settings":     "Settings",
}

PAGE_ICONS = {
    "dashboard":    "◈",
    "transactions": "⊕",
    "allocation":   "◑",
    "investments":  "◎",
    "reports":      "≣",
    "journal":      "◫",
    "reconcile":    "⟳",
    "agenda":       "⊡",
    "advisor":      "◉",
    "meridian":     "⬡",
    "settings":     "⊗",
}

# Sidebar groupings
PAGES_CORE = ["dashboard", "transactions", "allocation", "investments", "reports"]
PAGES_INTEL = ["journal", "reconcile", "agenda", "advisor", "meridian", "settings"]


class AppState(rx.State):
    """Root state — tracks active page for client-side nav."""
    page: str = "dashboard"

    def set_page(self, page: str) -> None:
        self.page = page
