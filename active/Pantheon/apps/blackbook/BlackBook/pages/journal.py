"""
pages/journal.py — Journal with permanent prompts + Meridian AI questions.
"""
from __future__ import annotations

import reflex as rx

from BlackBook.db.queries import JOURNAL_TAGS
from BlackBook.state.journal_state import JournalState, JournalEntry, PERMANENT_QUESTIONS


def entry_card(entry: JournalEntry) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(entry.entry_date, class_name="bb-journal-date"),
            rx.el.div(
                rx.el.span(entry.tag, class_name="bb-journal-tag"),
                rx.el.button(
                    "✕",
                    class_name="bb-btn bb-btn-danger",
                    on_click=JournalState.delete_entry(entry.id),
                    style={"font_size": "0.5rem"},
                ),
                style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
            ),
            class_name="bb-journal-header",
        ),
        rx.el.div(entry.body, class_name="bb-journal-body"),
        class_name="bb-journal-entry",
    )


def tag_filter_btn(tag: str) -> rx.Component:
    return rx.el.button(
        tag,
        class_name=rx.cond(
            JournalState.filter_tag == tag,
            "bb-btn bb-btn-primary",
            "bb-btn bb-btn-ghost",
        ),
        on_click=JournalState.set_filter(tag),
        style={"font_size": "0.54rem", "padding": "0.3rem 0.75rem"},
    )


def question_row(q: str, accent: str, label_color: str) -> rx.Component:
    """A question row with a Use button. accent = CSS border color string."""
    return rx.el.div(
        rx.el.span(q, class_name="bb-question-text"),
        rx.el.button(
            "Use",
            class_name="bb-btn bb-btn-ghost",
            on_click=JournalState.use_question_as_prompt(q),
            style={"font_size": "0.5rem", "padding": "0.25rem 0.65rem", "flex_shrink": "0"},
        ),
        class_name="bb-question-card",
        style={"border_left_color": accent},
    )


def meridian_question_row(q: str) -> rx.Component:
    return question_row(q, "var(--cy)", "var(--cy)")


def journal_page() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            rx.el.h1("Journal", class_name="bb-title"),
            rx.el.p("THOUGHTS · REFLECTIONS · DECISIONS", class_name="bb-subtitle"),
            class_name="bb-page-header",
        ),

        rx.cond(JournalState.error != "", rx.el.div(JournalState.error, class_name="bb-error")),
        rx.cond(JournalState.success != "", rx.el.div(JournalState.success, class_name="bb-success")),

        # ── Two-column prompts layout ──
        rx.el.div(
            # Permanent daily questions (always present)
            rx.el.div(
                rx.el.div("Daily Prompts", class_name="bb-section", style={"margin_top": "0", "margin_bottom": "0.7rem"}),
                *[
                    rx.el.div(
                        rx.el.span(q, class_name="bb-question-text"),
                        rx.el.button(
                            "Use",
                            class_name="bb-btn bb-btn-ghost",
                            on_click=JournalState.use_question_as_prompt(q),
                            style={"font_size": "0.5rem", "padding": "0.25rem 0.65rem", "flex_shrink": "0"},
                        ),
                        class_name="bb-question-card",
                        style={"border_left_color": "var(--pu)"},
                    )
                    for q in PERMANENT_QUESTIONS
                ],
                style={"flex": "1"},
            ),

            # Meridian AI questions (shown when available)
            rx.cond(
                JournalState.meridian_question_list.length() > 0,
                rx.el.div(
                    rx.el.div(
                        rx.el.span("⬡ Meridian · ", style={"color": "var(--cy)"}),
                        rx.el.span(
                            JournalState.meridian_question_date,
                            style={"font_size": "0.48rem", "letter_spacing": "0.2em", "color": "var(--t2)"},
                        ),
                        class_name="bb-section",
                        style={"margin_top": "0", "margin_bottom": "0.7rem"},
                    ),
                    rx.foreach(JournalState.meridian_question_list, meridian_question_row),
                    style={"flex": "1"},
                ),
                # Fallback when no Meridian questions
                rx.el.div(
                    rx.el.div("⬡ Meridian Questions", class_name="bb-section", style={"margin_top": "0", "margin_bottom": "0.7rem"}),
                    rx.el.div(
                        "No Meridian questions generated yet.",
                        style={"color": "var(--t2)", "font_size": "0.72rem", "line_height": "1.7"},
                    ),
                    style={"flex": "1"},
                ),
            ),

            style={"display": "grid", "grid_template_columns": "1fr 1fr", "gap": "1.5rem", "margin_bottom": "1.5rem"},
        ),

        # ── Compose ──
        rx.el.div("New Entry", class_name="bb-section", style={"margin_top": "0"}),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.label("Date", class_name="bb-label"),
                    rx.el.input(
                        type="date",
                        value=JournalState.form_date,
                        on_change=JournalState.set_form_date,
                        class_name="bb-input",
                    ),
                    class_name="bb-field",
                ),
                rx.el.div(
                    rx.el.label("Tag", class_name="bb-label"),
                    rx.el.select(
                        *[rx.el.option(t, value=t) for t in JOURNAL_TAGS],
                        value=JournalState.form_tag,
                        on_change=JournalState.set_form_tag,
                        class_name="bb-select",
                    ),
                    class_name="bb-field",
                ),
                style={"display": "grid", "grid_template_columns": "1fr 1fr", "gap": "0 1.5rem"},
            ),
            rx.el.div(
                rx.el.label("Entry", class_name="bb-label"),
                rx.el.textarea(
                    placeholder="Write freely — or click 'Use' on a prompt above...",
                    value=JournalState.form_body,
                    on_change=JournalState.set_form_body,
                    class_name="bb-input",
                    rows="6",
                    style={"resize": "vertical"},
                ),
                class_name="bb-field",
            ),
            rx.el.button(
                "Save Entry",
                class_name="bb-btn bb-btn-primary",
                on_click=JournalState.submit_entry,
            ),
            class_name="bb-journal-compose",
        ),

        # ── Filter ──
        rx.el.div("Filter", class_name="bb-section"),
        rx.el.div(
            tag_filter_btn("All"),
            *[tag_filter_btn(t) for t in JOURNAL_TAGS],
            style={"display": "flex", "flex_wrap": "wrap", "gap": "0.5rem", "margin_bottom": "1.2rem"},
        ),

        # ── Entries ──
        rx.el.div("Entries", class_name="bb-section"),
        rx.cond(
            JournalState.loading,
            rx.el.div("Loading...", style={"color": "var(--t2)", "font_size": "0.72rem"}),
            rx.cond(
                JournalState.entries.length() == 0,
                rx.el.div(
                    "No entries yet. Use a prompt above or write freely.",
                    style={"color": "var(--t2)", "font_size": "0.78rem", "padding": "1rem 0"},
                ),
                rx.foreach(JournalState.entries, entry_card),
            ),
        ),

        on_mount=JournalState.load,
    )
