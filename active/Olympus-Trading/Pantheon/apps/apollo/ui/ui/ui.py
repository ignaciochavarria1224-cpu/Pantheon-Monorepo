"""Apollo command center UI."""

from __future__ import annotations

import reflex as rx

from .components import dashboard_layout
from .state import State


def index() -> rx.Component:
    return dashboard_layout()


app = rx.App(
    style={
        "background": "#f5efe2",
        "color": "#221b14",
        "font_family": "'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', serif",
    }
)
app.add_page(index, route="/", title="Apollo / Pantheon", on_load=State.load_dashboard)
