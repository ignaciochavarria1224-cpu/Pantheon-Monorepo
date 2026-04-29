"""
components/sidebar.py — Navigation sidebar with icons and section groupings.
"""
from __future__ import annotations

import reflex as rx

from BlackBook.state.app_state import (
    AppState,
    PAGE_LABELS,
    PAGE_ICONS,
    PAGES_CORE,
    PAGES_INTEL,
)


def nav_item(page: str) -> rx.Component:
    return rx.el.button(
        rx.el.span(PAGE_ICONS[page], class_name="nav-icon"),
        rx.el.span(PAGE_LABELS[page]),
        class_name=rx.cond(
            AppState.page == page,
            "bb-nav-item active",
            "bb-nav-item",
        ),
        on_click=AppState.set_page(page),
    )


def sidebar() -> rx.Component:
    return rx.el.aside(
        # Brand
        rx.el.div(
            rx.el.div("Black Book", class_name="bb-sidebar-brand"),
            rx.el.div("Personal OS — 2026", class_name="bb-sidebar-year"),
        ),
        rx.el.div(class_name="bb-sidebar-divider"),

        # Core section
        rx.el.div("Core", class_name="bb-sidebar-section-label"),
        rx.el.nav(*[nav_item(p) for p in PAGES_CORE]),

        rx.el.div(class_name="bb-sidebar-divider"),

        # Intelligence section
        rx.el.div("Intelligence", class_name="bb-sidebar-section-label"),
        rx.el.nav(*[nav_item(p) for p in PAGES_INTEL]),

        # Footer
        rx.el.div(
            rx.el.span("v2 · Reflex"),
            rx.el.br(),
            rx.el.span("Powered by Claude"),
            class_name="bb-sidebar-footer",
        ),
        class_name="bb-sidebar",
    )
