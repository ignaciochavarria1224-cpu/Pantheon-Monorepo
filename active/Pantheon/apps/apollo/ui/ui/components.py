from __future__ import annotations

import reflex as rx

from .state import AuditItem, BalanceItem, HoldingItem, JournalEntry, Message, QuestionItem, SpendingItem, State, ThemeItem, TradeItem, TransactionItem

BG = "#f5efe2"
SURFACE = "rgba(255, 251, 244, 0.92)"
SURFACE_SOFT = "rgba(252, 247, 238, 0.88)"
SURFACE_STRONG = "rgba(255, 254, 250, 0.98)"
BORDER = "rgba(137, 104, 44, 0.18)"
BORDER_STRONG = "rgba(137, 104, 44, 0.34)"
TEXT = "#221b14"
TEXT_SOFT = "rgba(34, 27, 20, 0.82)"
TEXT_MUTED = "rgba(34, 27, 20, 0.55)"
ACCENT = "#8c6a2f"
ACCENT_POS = "#2d6a4f"
ACCENT_NEG = "#9c5d38"
GRAPHITE = "#2c241d"
USER_TINT = "rgba(142, 118, 83, 0.12)"
APOLLO_TINT = "rgba(255, 255, 255, 0.72)"


def ambient_background() -> rx.Component:
    return rx.box(
        rx.box(
            position="absolute",
            inset="0",
            background=(
                "radial-gradient(circle at 50% 0%, rgba(232, 218, 190, 0.62), transparent 42%),"
                "radial-gradient(circle at 12% 18%, rgba(255, 255, 255, 0.58), transparent 24%),"
                "radial-gradient(circle at 86% 16%, rgba(216, 191, 139, 0.24), transparent 22%),"
                "linear-gradient(180deg, #fbf7ef 0%, #f4ecde 52%, #efe5d6 100%)"
            ),
        ),
        position="absolute",
        inset="0",
        overflow="hidden",
    )


def shell_frame(*children, **props) -> rx.Component:
    props.setdefault("background", SURFACE)
    return rx.box(
        *children,
        border=f"1px solid {BORDER}",
        box_shadow="0 24px 90px rgba(68, 45, 10, 0.08)",
        border_radius="28px",
        backdrop_filter="blur(18px)",
        **props,
    )


def eyebrow(text: str) -> rx.Component:
    return rx.text(
        text,
        font_size="11px",
        letter_spacing="0.22em",
        text_transform="uppercase",
        color=TEXT_MUTED,
        font_family="'IBM Plex Mono', 'Consolas', monospace",
    )


def nav_button(label: str, active, action) -> rx.Component:
    return rx.button(
        label,
        on_click=action,
        height="40px",
        padding="0 16px",
        border_radius="999px",
        border=rx.cond(active, "none", f"1px solid {BORDER}"),
        background=rx.cond(active, "linear-gradient(135deg, #9b7742 0%, #c3a46f 100%)", "rgba(255, 252, 247, 0.78)"),
        color=rx.cond(active, "#fffaf2", GRAPHITE),
        font_size="13px",
        font_weight="600",
        cursor="pointer",
    )


def top_nav() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            eyebrow("Voice and operating shell"),
            rx.text("Apollo", color=GRAPHITE, font_size="28px", font_weight="600", letter_spacing="-0.05em"),
            rx.text("Apollo is the interface. Pantheon runs the system behind it.", color=TEXT_MUTED, font_size="14px"),
            spacing="1",
            align="start",
        ),
        rx.spacer(),
        rx.hstack(
            nav_button("Apollo", State.active_tab == "apollo", State.switch_to_apollo),
            nav_button("Pantheon", State.active_tab == "pantheon", State.switch_to_pantheon),
            spacing="3",
        ),
        width="100%",
        align="center",
    )


def status_chip(label: str, value) -> rx.Component:
    return rx.hstack(
        rx.text(label, color=TEXT_MUTED, font_size="11px", text_transform="uppercase", letter_spacing="0.12em"),
        rx.text(value, color=ACCENT, font_size="12px", font_weight="600"),
        border=f"1px solid {BORDER}",
        border_radius="999px",
        padding="8px 12px",
        background=SURFACE_SOFT,
        spacing="2",
    )


def status_ribbon() -> rx.Component:
    return rx.hstack(
        status_chip("Pantheon", State.pantheon_status),
        status_chip("BlackBook", State.blackbook_status),
        status_chip("Maridian", State.maridian_status),
        status_chip("Olympus", State.olympus_status),
        width="100%",
        wrap="wrap",
        spacing="3",
    )


def transcript_message(message: Message) -> rx.Component:
    user = message.role == "user"
    return rx.vstack(
        rx.hstack(
            rx.text(rx.cond(user, "You", "Apollo"), color=ACCENT, font_size="11px", letter_spacing="0.16em", text_transform="uppercase"),
            rx.spacer(),
            rx.text(message.timestamp, color=TEXT_MUTED, font_size="11px"),
            width="100%",
        ),
        rx.text(message.content, color=TEXT_SOFT, font_size="16px", line_height="1.85", white_space="pre-wrap"),
        background=rx.cond(user, USER_TINT, APOLLO_TINT),
        border=rx.cond(user, f"1px solid {BORDER_STRONG}", "1px solid rgba(255,255,255,0.72)"),
        border_radius="22px",
        padding="18px 20px",
        width="100%",
        align="start",
        spacing="2",
    )


def composer() -> rx.Component:
    return shell_frame(
        rx.vstack(
            rx.text_area(
                value=State.input_text,
                on_change=State.update_input_text,
                on_key_down=State.handle_enter_key,
                placeholder="Ask Apollo to think, log, summarize, or act.",
                width="100%",
                min_height="180px",
                rows="7",
                resize="vertical",
                background="rgba(255, 252, 247, 0.96)",
                padding="22px 20px",
                color=GRAPHITE,
                font_size="17px",
                line_height="1.85",
                border=f"1px solid {BORDER_STRONG}",
            ),
            rx.hstack(
                rx.text("Enter sends. Shift+Enter adds a line.", color=TEXT_MUTED, font_size="12px"),
                rx.spacer(),
                nav_button("Clear", False, State.clear_chat),
                nav_button(rx.cond(State.is_loading, "Thinking...", "Transmit"), True, State.send_message),
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        padding="18px",
    )


def metric_card(label: str, value, detail: str = "") -> rx.Component:
    return shell_frame(
        rx.vstack(
            eyebrow(label),
            rx.text(value, color=GRAPHITE, font_size="24px", font_weight="600"),
            rx.cond(
                detail != "",
                rx.text(detail, color=TEXT_MUTED, font_size="12px", line_height="1.6"),
                rx.fragment(),
            ),
            width="100%",
            spacing="1",
            align="start",
        ),
        padding="16px 18px",
        background=SURFACE_STRONG,
    )


def list_row(title, meta, detail) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(title, color=GRAPHITE, font_size="14px", font_weight="600"),
            rx.spacer(),
            rx.text(meta, color=TEXT_MUTED, font_size="11px"),
            width="100%",
        ),
        rx.text(detail, color=TEXT_SOFT, font_size="13px", line_height="1.7"),
        width="100%",
        spacing="1",
        align="start",
        padding_y="10px",
        border_bottom=f"1px solid {BORDER}",
    )


def section(title: str, subtitle: str, body: rx.Component) -> rx.Component:
    return shell_frame(
        rx.vstack(
            eyebrow(subtitle),
            rx.text(title, color=GRAPHITE, font_size="19px", font_weight="600"),
            body,
            width="100%",
            spacing="4",
            align="start",
        ),
        padding="22px",
    )


def loading_skeleton(rows: int = 4) -> rx.Component:
    widths = ["78%", "58%", "68%", "52%", "72%"]
    return rx.vstack(
        *[rx.box(
            height="14px",
            width=widths[i % len(widths)],
            background="rgba(140, 106, 47, 0.12)",
            border_radius="4px",
        ) for i in range(rows)],
        gap="10px",
        width="100%",
    )


def spending_chart() -> rx.Component:
    return rx.recharts.responsive_container(
        rx.recharts.bar_chart(
            rx.recharts.bar(data_key="amount", fill=ACCENT),
            rx.recharts.x_axis(data_key="name"),
            rx.recharts.y_axis(),
            rx.recharts.tooltip(),
            data=State.spending_chart_data,
            margin={"top": 8, "right": 8, "left": 0, "bottom": 0},
        ),
        width="100%",
        height=220,
    )


def pnl_chart() -> rx.Component:
    return rx.recharts.responsive_container(
        rx.recharts.bar_chart(
            rx.recharts.bar(data_key="pnl", fill=ACCENT),
            rx.recharts.x_axis(data_key="name"),
            rx.recharts.y_axis(),
            rx.recharts.tooltip(),
            rx.recharts.reference_line(y=0, stroke=BORDER_STRONG),
            data=State.pnl_chart_data,
            margin={"top": 8, "right": 8, "left": 0, "bottom": 0},
        ),
        width="100%",
        height=220,
    )


def toast() -> rx.Component:
    return rx.cond(
        State.toast_visible,
        rx.box(
            rx.hstack(
                rx.text(
                    State.toast_message,
                    color=rx.cond(State.toast_type == "error", ACCENT_NEG, ACCENT_POS),
                    font_size="14px",
                    font_weight="500",
                    flex="1",
                ),
                rx.button(
                    "×",
                    on_click=State.dismiss_toast,
                    background="transparent",
                    border="none",
                    cursor="pointer",
                    color=TEXT_MUTED,
                    font_size="18px",
                    padding="0",
                    line_height="1",
                    height="auto",
                    min_width="auto",
                ),
                width="100%",
                align="center",
                gap="12px",
            ),
            position="fixed",
            bottom="32px",
            right="32px",
            background=SURFACE_STRONG,
            border=f"1px solid {BORDER_STRONG}",
            border_radius="14px",
            padding="14px 18px",
            box_shadow="0 8px 40px rgba(68, 45, 10, 0.18)",
            z_index="9999",
            max_width="360px",
            min_width="220px",
        ),
        rx.fragment(),
    )


def apollo_tab() -> rx.Component:
    return rx.vstack(
        status_ribbon(),
        shell_frame(
            rx.vstack(
                eyebrow("Conversation"),
                rx.text("Apollo", color=GRAPHITE, font_size="22px", font_weight="600"),
                rx.text(State.latest_signal, color=TEXT_MUTED, font_size="14px"),
                rx.cond(
                    State.messages.length() > 0,
                    rx.vstack(rx.foreach(State.messages, transcript_message), width="100%", spacing="4"),
                    rx.text(
                        "Apollo is ready. Use chat for questions, quick commands, and natural conversation. Pantheon runs the system behind the answers.",
                        color=TEXT_MUTED,
                        font_size="16px",
                        line_height="1.8",
                    ),
                ),
                width="100%",
                spacing="4",
                align="start",
            ),
            padding="22px",
        ),
        composer(),
        width="100%",
        spacing="5",
        align="stretch",
    )


def pantheon_subnav() -> rx.Component:
    return rx.hstack(
        nav_button("Overview", State.pantheon_section == "overview", State.show_overview),
        nav_button("BlackBook", State.pantheon_section == "blackbook", State.show_blackbook),
        nav_button("Maridian", State.pantheon_section == "maridian", State.show_maridian),
        nav_button("Olympus", State.pantheon_section == "olympus", State.show_olympus),
        nav_button("Activity", State.pantheon_section == "activity", State.show_activity),
        width="100%",
        wrap="wrap",
        spacing="3",
    )


def balance_row(item: BalanceItem) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(item.name, color=GRAPHITE, font_size="14px", font_weight="600"),
            rx.text(item.account_type, color=TEXT_MUTED, font_size="11px", text_transform="capitalize"),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.text(
            item.balance,
            color=rx.cond(item.is_debt, ACCENT_NEG, ACCENT_POS),
            font_size="15px",
            font_weight="600",
        ),
        rx.button(
            "Edit",
            on_click=State.open_edit_balance(item.id, item.name, item.balance),
            size="1",
            variant="ghost",
            color=TEXT_MUTED,
            cursor="pointer",
        ),
        width="100%",
        align="center",
        padding_y="10px",
        border_bottom=f"1px solid {BORDER}",
    )


def edit_balance_modal() -> rx.Component:
    return rx.cond(
        State.show_edit_balance,
        rx.box(
            rx.box(
                rx.hstack(
                    rx.text(f"Edit Balance — ", color=TEXT_MUTED, font_size="13px"),
                    rx.text(State.edit_balance_name, color=GRAPHITE, font_size="13px", font_weight="600"),
                    spacing="1",
                ),
                rx.input(
                    value=State.edit_balance_value,
                    on_change=State.set_edit_balance_value,
                    placeholder="0.00",
                    type="number",
                    width="100%",
                    margin_y="12px",
                ),
                rx.hstack(
                    rx.button("Cancel", on_click=State.close_edit_balance, variant="ghost", color=TEXT_MUTED),
                    rx.button("Save", on_click=State.save_balance_override, color_scheme="grass"),
                    justify="end",
                    width="100%",
                ),
                background=SURFACE_STRONG,
                border=f"1px solid {BORDER_STRONG}",
                border_radius="12px",
                padding="24px",
                width="320px",
            ),
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            display="flex",
            align_items="center",
            justify_content="center",
            background="rgba(0,0,0,0.4)",
            z_index="100",
            on_click=State.close_edit_balance,
        ),
    )


def transaction_row(item: TransactionItem) -> rx.Component:
    return list_row(item.description, f"{item.date} / {item.account}", f"{item.category} - {item.amount} ({item.tx_type})")


def spending_row(item: SpendingItem) -> rx.Component:
    return list_row(item.category, f"{item.count} tx", item.total)


def theme_row(item: ThemeItem) -> rx.Component:
    return list_row(item.title, item.updated_at, item.preview)


def question_row(item: QuestionItem) -> rx.Component:
    return list_row("Question", "", rx.cond(item.context != "", f"{item.question} — {item.context}", item.question))


def trade_row(item: TradeItem) -> rx.Component:
    return list_row(item.symbol, f"{item.direction} / {item.exit_time}", f"{item.realized_pnl} via {item.exit_reason}")


def audit_row(item: AuditItem) -> rx.Component:
    return list_row(
        rx.cond(item.system != "", item.system, "SYSTEM"),
        item.timestamp,
        rx.cond(item.detail != "", item.action + " - " + item.detail, item.action),
    )


def trace_row(item: AuditItem) -> rx.Component:
    return list_row(
        rx.cond(item.system != "", item.system, "PANTHEON"),
        item.timestamp,
        rx.cond(item.detail != "", item.action + " — " + item.detail, item.action),
    )


def option(value: str) -> rx.Component:
    return rx.el.option(value, value=value)


def blackbook_form() -> rx.Component:
    return rx.box(
        shell_frame(
            rx.vstack(
                eyebrow("Quick expense"),
                rx.input(placeholder="Amount", value=State.expense_amount, on_change=State.set_expense_amount),
                rx.input(placeholder="Description", value=State.expense_description, on_change=State.set_expense_description),
                rx.input(placeholder="Category", value=State.expense_category, on_change=State.set_expense_category),
                rx.el.select(
                    rx.foreach(State.blackbook_accounts, option),
                    value=State.expense_account,
                    on_change=State.set_expense_account,
                    width="100%",
                    padding="8px",
                    border=f"1px solid {BORDER_STRONG}",
                    border_radius="8px",
                    background=SURFACE_STRONG,
                    color=GRAPHITE,
                    font_size="14px",
                ),
                nav_button("Add Expense", True, State.submit_expense),
                width="100%",
                spacing="3",
                align="start",
            ),
            padding="18px",
        ),
        shell_frame(
            rx.vstack(
                eyebrow("Quick income"),
                rx.input(placeholder="Amount", value=State.income_amount, on_change=State.set_income_amount),
                rx.input(placeholder="Description", value=State.income_description, on_change=State.set_income_description),
                rx.el.select(
                    rx.foreach(State.blackbook_accounts, option),
                    value=State.income_account,
                    on_change=State.set_income_account,
                    width="100%",
                    padding="8px",
                    border=f"1px solid {BORDER_STRONG}",
                    border_radius="8px",
                    background=SURFACE_STRONG,
                    color=GRAPHITE,
                    font_size="14px",
                ),
                nav_button("Add Income", True, State.submit_income),
                width="100%",
                spacing="3",
                align="start",
            ),
            padding="18px",
        ),
        display="grid",
        grid_template_columns=["1fr", "1fr 1fr"],
        gap="18px",
        width="100%",
    )


def overview_panel() -> rx.Component:
    return rx.vstack(
        section(
            "System Pulse",
            "Overview",
            rx.vstack(
                status_ribbon(),
                rx.text(State.latest_signal, color=TEXT_SOFT, font_size="14px"),
                rx.text(State.self_model_excerpt, color=TEXT_MUTED, font_size="13px", line_height="1.8"),
                width="100%",
                spacing="4",
            ),
        ),
        rx.box(
            section(
                "Financial Core",
                "BlackBook",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(3),
                    rx.box(
                        metric_card("Net Worth", State.net_worth),
                        metric_card("Assets", State.total_assets),
                        metric_card("Debt", State.total_debt),
                        display="grid",
                        grid_template_columns="repeat(3, 1fr)",
                        gap="12px",
                        width="100%",
                    ),
                ),
            ),
            section(
                "Reflection Engine",
                "Maridian",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(3),
                    rx.box(
                        metric_card("Cycle", State.maridian_cycle_count),
                        metric_card("Entries", State.maridian_entries_processed),
                        metric_card("Last Cycle", State.maridian_last_cycle),
                        display="grid",
                        grid_template_columns="repeat(3, 1fr)",
                        gap="12px",
                        width="100%",
                    ),
                ),
            ),
            section(
                "Trading Runtime",
                "Olympus",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(3),
                    rx.box(
                        metric_card("Total PnL", State.olympus_total_pnl),
                        metric_card("Trades", State.olympus_total_trades),
                        metric_card("Avg R", State.olympus_avg_r),
                        display="grid",
                        grid_template_columns="repeat(3, 1fr)",
                        gap="12px",
                        width="100%",
                    ),
                ),
            ),
            display="grid",
            grid_template_columns=["1fr", "repeat(2, 1fr)", "repeat(3, 1fr)"],
            gap="20px",
            width="100%",
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def holding_row(item: HoldingItem) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(item.symbol, color=GRAPHITE, font_size="14px", font_weight="700"),
                rx.text(item.display_name, color=TEXT_MUTED, font_size="11px"),
                spacing="0",
                align="start",
            ),
            rx.spacer(),
            rx.text(item.account, color=TEXT_MUTED, font_size="11px"),
            rx.text(item.asset_type, color=TEXT_MUTED, font_size="11px", min_width="52px", text_align="right"),
            width="100%",
            align="center",
        ),
        rx.hstack(
            rx.text(item.price, color=TEXT_SOFT, font_size="13px", min_width="76px"),
            rx.text(f"× {item.quantity}", color=TEXT_MUTED, font_size="13px"),
            rx.spacer(),
            rx.text(item.value, color=GRAPHITE, font_size="13px", font_weight="600"),
            rx.text(
                item.pnl,
                color=rx.cond(item.is_positive, ACCENT_POS, ACCENT_NEG),
                font_size="13px",
                font_weight="500",
                min_width="72px",
                text_align="right",
            ),
            rx.text(
                item.pnl_pct,
                color=rx.cond(item.is_positive, ACCENT_POS, ACCENT_NEG),
                font_size="12px",
                min_width="52px",
                text_align="right",
            ),
            width="100%",
            align="center",
        ),
        width="100%",
        spacing="1",
        align="start",
        padding_y="10px",
        border_bottom=f"1px solid {BORDER}",
    )


def journal_entry_row(item: JournalEntry) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(item.entry_date, color=ACCENT, font_size="12px", font_weight="600"),
            rx.box(
                rx.text(item.tag, font_size="11px", color=GRAPHITE, font_weight="500"),
                background=f"rgba(140, 106, 47, 0.1)",
                border_radius="999px",
                padding="2px 10px",
            ),
            rx.spacer(),
            rx.button(
                "×",
                on_click=lambda: State.delete_journal_entry(item.id),
                background="transparent",
                border="none",
                cursor="pointer",
                color=TEXT_MUTED,
                font_size="16px",
                padding="0",
                min_width="auto",
                height="auto",
                line_height="1",
            ),
            width="100%",
            align="center",
            spacing="2",
        ),
        rx.text(item.body, color=TEXT_SOFT, font_size="14px", line_height="1.7", white_space="pre-wrap"),
        width="100%",
        spacing="2",
        align="start",
        padding_y="12px",
        border_bottom=f"1px solid {BORDER}",
    )


def holdings_panel() -> rx.Component:
    return rx.vstack(
        rx.box(
            metric_card("Portfolio Value", State.portfolio_value),
            metric_card("Total P&L", State.portfolio_pnl),
            metric_card("Last Refresh", State.holdings_last_refresh),
            display="grid",
            grid_template_columns=["1fr", "repeat(3, 1fr)"],
            gap="16px",
            width="100%",
        ),
        section(
            "Holdings",
            "Investments",
            rx.cond(
                State.context_loading,
                loading_skeleton(5),
                rx.cond(
                    State.holdings.length() > 0,
                    rx.box(rx.foreach(State.holdings, holding_row), width="100%"),
                    rx.text("No holdings found.", color=TEXT_MUTED, font_size="14px"),
                ),
            ),
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


JOURNAL_TAGS = ["All", "General", "Finance", "Reflection", "Decision", "Goals", "Other"]


def journal_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            *[rx.button(
                t,
                on_click=lambda tag=t: State.set_journal_filter(tag),
                height="34px",
                padding="0 14px",
                border_radius="999px",
                border=rx.cond(State.journal_filter_tag == t, "none", f"1px solid {BORDER}"),
                background=rx.cond(State.journal_filter_tag == t, "linear-gradient(135deg, #9b7742 0%, #c3a46f 100%)", SURFACE_SOFT),
                color=rx.cond(State.journal_filter_tag == t, "#fffaf2", GRAPHITE),
                font_size="12px",
                font_weight="600",
                cursor="pointer",
            ) for t in JOURNAL_TAGS],
            width="100%",
            wrap="wrap",
            spacing="2",
        ),
        section(
            "New Entry",
            "Write",
            rx.vstack(
                rx.hstack(
                    rx.input(
                        placeholder="Date (YYYY-MM-DD, optional)",
                        value=State.journal_form_date,
                        on_change=State.set_journal_date,
                        flex="1",
                    ),
                    rx.el.select(
                        *[rx.el.option(t, value=t) for t in ["General", "Finance", "Reflection", "Decision", "Goals", "Other"]],
                        value=State.journal_form_tag,
                        on_change=State.set_journal_tag,
                        padding="8px",
                        border=f"1px solid {BORDER_STRONG}",
                        border_radius="8px",
                        background=SURFACE_STRONG,
                        color=GRAPHITE,
                        font_size="14px",
                        min_width="130px",
                    ),
                    width="100%",
                    spacing="3",
                ),
                rx.text_area(
                    value=State.journal_form_body,
                    on_change=State.set_journal_body,
                    placeholder="Write your entry...",
                    width="100%",
                    min_height="120px",
                    rows="5",
                    resize="vertical",
                    background=SURFACE_STRONG,
                    padding="14px",
                    color=GRAPHITE,
                    font_size="14px",
                    border=f"1px solid {BORDER_STRONG}",
                ),
                nav_button("Save Entry", True, State.submit_journal_entry),
                width="100%",
                spacing="3",
                align="start",
            ),
        ),
        section(
            "Entries",
            "Journal",
            rx.cond(
                State.journal_entries.length() > 0,
                rx.box(rx.foreach(State.journal_entries, journal_entry_row), width="100%"),
                rx.text("No entries yet. Write your first one above.", color=TEXT_MUTED, font_size="14px"),
            ),
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def settings_input(label: str, value, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, color=TEXT_MUTED, font_size="11px", text_transform="uppercase", letter_spacing="0.12em"),
        rx.input(value=value, on_change=on_change, width="100%"),
        width="100%",
        spacing="1",
        align="start",
    )


def settings_panel() -> rx.Component:
    return rx.vstack(
        section(
            "Budget",
            "BlackBook Settings",
            rx.box(
                settings_input("Daily Food Budget ($)", State.bb_daily_food_budget, State.set_bb_daily_food_budget),
                settings_input("Pay Period (days)", State.bb_pay_period_days, State.set_bb_pay_period_days),
                display="grid",
                grid_template_columns=["1fr", "1fr 1fr"],
                gap="16px",
                width="100%",
            ),
        ),
        section(
            "Allocation",
            "Paycheck splits",
            rx.box(
                settings_input("Savings %", State.bb_savings_pct, State.set_bb_savings_pct),
                settings_input("Spending %", State.bb_spending_pct, State.set_bb_spending_pct),
                settings_input("Crypto %", State.bb_crypto_pct, State.set_bb_crypto_pct),
                settings_input("Taxable Investing %", State.bb_taxable_pct, State.set_bb_taxable_pct),
                settings_input("Roth IRA %", State.bb_roth_pct, State.set_bb_roth_pct),
                display="grid",
                grid_template_columns=["1fr", "1fr 1fr", "repeat(3, 1fr)"],
                gap="16px",
                width="100%",
            ),
        ),
        section(
            "Schedule",
            "Dates",
            rx.box(
                settings_input("Next Payday", State.bb_next_payday, State.set_bb_next_payday),
                display="grid",
                grid_template_columns=["1fr", "1fr 1fr"],
                gap="16px",
                width="100%",
            ),
        ),
        rx.box(
            nav_button("Save Settings", True, State.save_bb_settings),
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def blackbook_subnav() -> rx.Component:
    return rx.hstack(
        nav_button("Accounts", State.blackbook_section == "accounts", State.show_bb_accounts),
        nav_button("Holdings", State.blackbook_section == "holdings", State.show_bb_holdings),
        nav_button("Journal", State.blackbook_section == "journal", State.show_bb_journal),
        nav_button("Settings", State.blackbook_section == "settings", State.show_bb_settings),
        width="100%",
        wrap="wrap",
        spacing="3",
    )


def accounts_section() -> rx.Component:
    return rx.vstack(
        rx.box(
            metric_card("Daily Food Left", State.daily_food_left),
            metric_card("Weekly Food Left", State.weekly_food_left),
            metric_card("Net Worth", State.net_worth),
            metric_card("Runway", rx.hstack(State.runway_days, rx.text("days", font_size="14px", color=TEXT_MUTED, align_self="flex-end"), spacing="1")),
            display="grid",
            grid_template_columns=["1fr 1fr", "repeat(4, 1fr)"],
            gap="14px",
            width="100%",
        ),
        rx.box(
            metric_card("Total Debt", State.total_debt),
            metric_card("Lifetime Surplus", State.lifetime_surplus),
            metric_card("Daily Burn", State.daily_burn),
            metric_card("Txns Today", State.txns_today),
            display="grid",
            grid_template_columns=["1fr 1fr", "repeat(4, 1fr)"],
            gap="14px",
            width="100%",
        ),
        rx.box(
            section(
                "Balances",
                "BlackBook",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(4),
                    rx.box(rx.foreach(State.blackbook_balances, balance_row), width="100%"),
                ),
            ),
            section(
                "Spending This Month",
                "Summary",
                rx.vstack(
                    spending_chart(),
                    rx.cond(
                        State.context_loading,
                        loading_skeleton(3),
                        rx.box(rx.foreach(State.blackbook_spending, spending_row), width="100%"),
                    ),
                    width="100%",
                    spacing="4",
                ),
            ),
            display="grid",
            grid_template_columns=["1fr", "1fr 1fr"],
            gap="20px",
            width="100%",
        ),
        rx.box(
            section(
                "Recent Transactions",
                "Ledger",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(5),
                    rx.box(rx.foreach(State.blackbook_transactions, transaction_row), width="100%"),
                ),
            ),
            section("Quick Actions", "Write", blackbook_form()),
            display="grid",
            grid_template_columns=["1fr", "1fr 1fr"],
            gap="20px",
            width="100%",
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def blackbook_panel() -> rx.Component:
    return rx.vstack(
        blackbook_subnav(),
        rx.cond(
            State.blackbook_section == "accounts",
            accounts_section(),
            rx.cond(
                State.blackbook_section == "holdings",
                holdings_panel(),
                rx.cond(
                    State.blackbook_section == "journal",
                    journal_panel(),
                    settings_panel(),
                ),
            ),
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def maridian_panel() -> rx.Component:
    return rx.vstack(
        rx.box(
            section(
                "Cycle Status",
                "Maridian",
                rx.vstack(
                    rx.box(
                        metric_card("Last Cycle", State.maridian_last_cycle),
                        metric_card("Entries", State.maridian_entries_processed),
                        display="grid",
                        grid_template_columns="1fr 1fr",
                        gap="12px",
                        width="100%",
                    ),
                    rx.cond(
                        State.maridian_running,
                        rx.hstack(
                            rx.box(
                                width="8px",
                                height="8px",
                                border_radius="50%",
                                background=ACCENT,
                                flex_shrink="0",
                            ),
                            rx.text("Maridian cycle running...", color=ACCENT, font_size="14px", font_weight="500"),
                            align="center",
                            gap="8px",
                        ),
                        nav_button("Run Cycle", True, State.run_maridian_cycle),
                    ),
                    width="100%",
                    spacing="4",
                ),
            ),
            section(
                "Today's Questions",
                "Adaptive prompts",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(4),
                    rx.box(rx.foreach(State.maridian_questions, question_row), width="100%"),
                ),
            ),
            display="grid",
            grid_template_columns=["1fr", "1fr 1fr"],
            gap="20px",
            width="100%",
        ),
        rx.box(
            section(
                "Top Themes",
                "Synced context",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(4),
                    rx.box(rx.foreach(State.maridian_themes, theme_row), width="100%"),
                ),
            ),
            section(
                "Index Excerpt",
                "Context",
                rx.text(State.maridian_index_excerpt, color=TEXT_SOFT, font_size="13px", line_height="1.8", white_space="pre-wrap"),
            ),
            display="grid",
            grid_template_columns=["1fr", "1fr 1fr"],
            gap="20px",
            width="100%",
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def olympus_panel() -> rx.Component:
    return rx.vstack(
        rx.box(
            section(
                "Runtime Summary",
                "Olympus",
                rx.vstack(
                    rx.box(
                        metric_card("Total PnL", State.olympus_total_pnl),
                        metric_card("Trades", State.olympus_total_trades),
                        metric_card("Avg R", State.olympus_avg_r),
                        display="grid",
                        grid_template_columns="repeat(3, 1fr)",
                        gap="12px",
                        width="100%",
                    ),
                    rx.text(State.olympus_cycle_summary, color=TEXT_MUTED, font_size="13px"),
                    width="100%",
                    spacing="4",
                ),
            ),
            section(
                "PnL by Trade",
                "Recent exits",
                rx.cond(
                    State.context_loading,
                    loading_skeleton(4),
                    pnl_chart(),
                ),
            ),
            display="grid",
            grid_template_columns=["1fr", "1fr 1fr"],
            gap="20px",
            width="100%",
        ),
        section(
            "Recent Trades",
            "Read-only",
            rx.cond(
                State.context_loading,
                loading_skeleton(5),
                rx.box(rx.foreach(State.olympus_recent_trades, trade_row), width="100%"),
            ),
        ),
        section(
            "Latest Report",
            "Apex context",
            rx.text(State.olympus_report_excerpt, color=TEXT_SOFT, font_size="13px", line_height="1.8", white_space="pre-wrap"),
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def activity_panel() -> rx.Component:
    return rx.vstack(
        section(
            "Recent Audit",
            "Pantheon activity",
            rx.cond(
                State.context_loading,
                loading_skeleton(5),
                rx.box(rx.foreach(State.audit_items, audit_row), width="100%"),
            ),
        ),
        spacing="5",
        align="stretch",
        width="100%",
    )


def pantheon_panel() -> rx.Component:
    return rx.vstack(
        pantheon_subnav(),
        rx.cond(
            State.pantheon_section == "overview",
            overview_panel(),
            rx.cond(
                State.pantheon_section == "blackbook",
                blackbook_panel(),
                rx.cond(
                    State.pantheon_section == "maridian",
                    maridian_panel(),
                    rx.cond(
                        State.pantheon_section == "olympus",
                        olympus_panel(),
                        activity_panel(),
                    ),
                ),
            ),
        ),
        width="100%",
        spacing="4",
    )


def overview_panel() -> rx.Component:
    return rx.flex(
        section(
            "System Pulse",
            "Overview",
            rx.vstack(
                status_ribbon(),
                rx.text(State.latest_signal, color=TEXT_SOFT, font_size="14px"),
                rx.text(State.self_model_excerpt, color=TEXT_MUTED, font_size="13px", line_height="1.8"),
                width="100%",
                spacing="4",
            ),
        ),
        section(
            "Financial Core",
            "BlackBook",
            rx.flex(
                metric_card("Net Worth", State.net_worth, "Live from BlackBook's shared balance logic."),
                metric_card("Assets", State.total_assets, "Current assets under BlackBook."),
                metric_card("Debt", State.total_debt, "Current debts under BlackBook."),
                wrap="wrap",
                gap="16px",
                width="100%",
            ),
        ),
        section(
            "Reflection Engine",
            "Maridian",
            rx.flex(
                metric_card("Cycle", State.maridian_cycle_count, "Current Maridian cycle count."),
                metric_card("Entries", State.maridian_entries_processed, "Entries processed by Maridian."),
                metric_card("Last Cycle", State.maridian_last_cycle, "Most recent recorded cycle run."),
                wrap="wrap",
                gap="16px",
                width="100%",
            ),
        ),
        section(
            "Trading Runtime",
            "Olympus",
            rx.flex(
                metric_card("Total PnL", State.olympus_total_pnl, "Read-only Olympus performance summary."),
                metric_card("Trades", State.olympus_total_trades, "Completed trades recorded in Olympus."),
                metric_card("Avg R", State.olympus_avg_r, "Average R multiple across recorded trades."),
                wrap="wrap",
                gap="16px",
                width="100%",
            ),
        ),
        wrap="wrap",
        gap="20px",
        width="100%",
    )


def blackbook_panel() -> rx.Component:
    return rx.flex(
        section(
            "Balances",
            "BlackBook",
            rx.box(rx.foreach(State.blackbook_balances, balance_row), width="100%"),
        ),
        section(
            "Recent Transactions",
            "Ledger",
            rx.box(rx.foreach(State.blackbook_transactions, transaction_row), width="100%"),
        ),
        section(
            "Spending This Month",
            "Summary",
            rx.box(rx.foreach(State.blackbook_spending, spending_row), width="100%"),
        ),
        section("Quick Actions", "Write", blackbook_form()),
        wrap="wrap",
        gap="20px",
        width="100%",
    )


def maridian_panel() -> rx.Component:
    return rx.flex(
        section(
            "Cycle Status",
            "Maridian",
            rx.vstack(
                metric_card("Status", rx.cond(State.maridian_locked, "Locked", "Idle"), "Real lock-state from Maridian."),
                metric_card("Last Cycle", State.maridian_last_cycle, "Most recent Maridian cycle."),
                rx.text(State.maridian_notice, color=ACCENT, font_size="13px"),
                nav_button(rx.cond(State.maridian_running, "Running...", "Run Cycle"), True, State.run_maridian_cycle),
                width="100%",
                spacing="4",
            ),
        ),
        section(
            "Today's Questions",
            "Adaptive prompts",
            rx.box(rx.foreach(State.maridian_questions, question_row), width="100%"),
        ),
        section(
            "Top Themes",
            "Synced context",
            rx.box(rx.foreach(State.maridian_themes, theme_row), width="100%"),
        ),
        section(
            "Index Excerpt",
            "Context",
            rx.text(State.maridian_index_excerpt, color=TEXT_SOFT, font_size="13px", line_height="1.8", white_space="pre-wrap"),
        ),
        section(
            "Journal",
            "Maridian entries",
            journal_panel(),
        ),
        wrap="wrap",
        gap="20px",
        width="100%",
    )


def olympus_panel() -> rx.Component:
    return rx.flex(
        section(
            "Runtime Summary",
            "Olympus",
            rx.vstack(
                metric_card("Total PnL", State.olympus_total_pnl, "Pulled from Olympus trade memory."),
                metric_card("Trades", State.olympus_total_trades, "Recorded completed trades."),
                metric_card("Last Trade", State.olympus_last_trade, "Latest exit recorded in Olympus."),
                rx.text(State.olympus_cycle_summary, color=TEXT_MUTED, font_size="13px"),
                width="100%",
                spacing="4",
            ),
        ),
        section(
            "Recent Trades",
            "Read-only",
            rx.box(rx.foreach(State.olympus_recent_trades, trade_row), width="100%"),
        ),
        section(
            "Latest Report",
            "Apex context",
            rx.text(State.olympus_report_excerpt, color=TEXT_SOFT, font_size="13px", line_height="1.8", white_space="pre-wrap"),
        ),
        wrap="wrap",
        gap="20px",
        width="100%",
    )


def activity_panel() -> rx.Component:
    return rx.flex(
        section(
            "Recent Audit",
            "Pantheon activity",
            rx.box(rx.foreach(State.audit_items, audit_row), width="100%"),
        ),
        wrap="wrap",
        gap="20px",
        width="100%",
    )


def doctor_panel() -> rx.Component:
    return rx.flex(
        section(
            "Provider Health",
            "Doctor",
            rx.flex(
                metric_card("Current", State.doctor_current_provider, "Provider currently used for open-ended reasoning."),
                metric_card("Preferred", State.doctor_preferred_provider, "Configured priority order for Pantheon generation."),
                metric_card(
                    "Anthropic",
                    State.anthropic_status,
                    rx.cond(
                        State.anthropic_model != "",
                        State.anthropic_model,
                        rx.cond(
                            State.anthropic_reason != "",
                            State.anthropic_reason,
                            "Anthropic provider health.",
                        ),
                    ),
                ),
                metric_card(
                    "Ollama",
                    State.ollama_status,
                    rx.cond(
                        State.ollama_model != "",
                        State.ollama_model,
                        rx.cond(
                            State.ollama_reason != "",
                            State.ollama_reason,
                            "Ollama runtime health.",
                        ),
                    ),
                ),
                wrap="wrap",
                gap="16px",
                width="100%",
            ),
        ),
        section(
            "Subsystem Health",
            "Doctor",
            rx.vstack(
                list_row("BlackBook", State.blackbook_status, rx.cond(State.doctor_blackbook_reason != "", State.doctor_blackbook_reason, "BlackBook is reachable.")),
                list_row("Maridian", State.maridian_status, rx.cond(State.doctor_maridian_reason != "", State.doctor_maridian_reason, "Maridian is reachable.")),
                list_row("Olympus", State.olympus_status, rx.cond(State.doctor_olympus_reason != "", State.doctor_olympus_reason, "Olympus is reachable.")),
                width="100%",
                spacing="0",
            ),
        ),
        section(
            "Recent Traces",
            "Doctor",
            rx.box(rx.foreach(State.trace_items, trace_row), width="100%"),
        ),
        wrap="wrap",
        gap="20px",
        width="100%",
    )


def pantheon_panel() -> rx.Component:
    return rx.vstack(
        pantheon_subnav(),
        rx.cond(
            State.pantheon_section == "overview",
            overview_panel(),
            rx.cond(
                State.pantheon_section == "blackbook",
                blackbook_panel(),
                rx.cond(
                    State.pantheon_section == "maridian",
                    maridian_panel(),
                    rx.cond(
                        State.pantheon_section == "olympus",
                        olympus_panel(),
                        rx.cond(
                            State.pantheon_section == "activity",
                            activity_panel(),
                            doctor_panel(),
                        ),
                    ),
                ),
            ),
        ),
        width="100%",
        spacing="5",
        align="stretch",
    )


def content_shell() -> rx.Component:
    return shell_frame(
        rx.vstack(
            top_nav(),
            rx.cond(
                State.context_error != "",
                rx.text(f"Context error: {State.context_error}", color=ACCENT_NEG, font_size="13px"),
                rx.box(),
            ),
            rx.cond(State.active_tab == "apollo", apollo_tab(), pantheon_panel()),
            width="100%",
            spacing="6",
            align="stretch",
        ),
        padding=["22px", "26px", "32px"],
        width="100%",
    )


def dashboard_layout() -> rx.Component:
    return rx.box(
        ambient_background(),
        rx.box(
            content_shell(),
            max_width=rx.cond(State.active_tab == "apollo", "1020px", "1360px"),
            margin="0 auto",
            padding=["26px 18px 40px", "34px 24px 48px", "48px 28px 64px"],
            position="relative",
            z_index="1",
        ),
        toast(),
        edit_balance_modal(),
        min_height="100vh",
        background=BG,
        position="relative",
    )
