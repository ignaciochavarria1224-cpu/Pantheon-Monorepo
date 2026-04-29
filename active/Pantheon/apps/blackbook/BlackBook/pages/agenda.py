"""
pages/agenda.py — Financial agenda + Google Calendar integration.

Google Calendar setup (one-time):
  1. pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
  2. Go to console.cloud.google.com → Create project → Enable Google Calendar API
  3. Create OAuth2 credentials (Desktop app) → Download as client_secret.json
  4. Run: python scripts/auth_google.py   (see note below)
  5. This saves google_token.json next to rxconfig.py
  6. Add GOOGLE_CALENDAR_ID=primary to your .env (or a specific calendar ID)

The app will then show your upcoming Google Calendar events automatically.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

import reflex as rx

from BlackBook.db import queries


class CalendarEvent(rx.Base):
    title: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    is_all_day: bool = False


class AgendaItem(rx.Base):
    label: str = ""
    date_str: str = ""
    days_str: str = ""
    type_label: str = ""
    border_color: str = ""
    days_color: str = ""


class AgendaState(rx.State):
    items: list[AgendaItem] = []
    cal_events: list[CalendarEvent] = []
    cal_status: str = "unchecked"   # "ok" | "needs_setup" | "error" | "unchecked"
    cal_error: str = ""
    loading: bool = False
    error: str = ""

    @rx.event
    async def load(self) -> None:
        self.loading = True
        try:
            settings = queries.get_settings()
            self.items = _build_items(settings)
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False
        # Always attempt Google Calendar load
        yield AgendaState.load_google_calendar  # type: ignore

    @rx.event
    async def load_google_calendar(self) -> None:
        """Try to load Google Calendar events. Gracefully degrades if not set up."""
        token_path = _find_token_file()
        if not token_path:
            self.cal_status = "needs_setup"
            return
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import json

            with open(token_path) as f:
                cred_data = json.load(f)

            creds = Credentials.from_authorized_user_info(cred_data)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(token_path, "w") as f:
                        f.write(creds.to_json())
                else:
                    self.cal_status = "needs_setup"
                    return

            service = build("calendar", "v3", credentials=creds)
            cal_id = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
            now_iso = datetime.now(timezone.utc).isoformat()

            result = service.events().list(
                calendarId=cal_id,
                timeMin=now_iso,
                maxResults=15,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = result.get("items", [])
            self.cal_events = [_to_cal_event(e) for e in events]
            self.cal_status = "ok"

        except ImportError:
            self.cal_status = "needs_setup"
        except Exception as e:
            self.cal_status = "error"
            self.cal_error = str(e)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_token_file() -> str | None:
    """Look for google_token.json next to rxconfig.py or in the project root."""
    candidates = [
        os.path.join(os.getcwd(), "google_token.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "google_token.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def _to_cal_event(e: dict) -> CalendarEvent:
    start = e.get("start", {})
    end = e.get("end", {})
    all_day = "date" in start and "dateTime" not in start
    return CalendarEvent(
        title=str(e.get("summary", "(no title)")),
        start=str(start.get("dateTime") or start.get("date") or ""),
        end=str(end.get("dateTime") or end.get("date") or ""),
        location=str(e.get("location", "")),
        is_all_day=all_day,
    )


def _build_items(s: dict) -> list[AgendaItem]:
    items = []
    today = date.today()

    next_pay_str = s.get("next_payday", "")
    if next_pay_str:
        try:
            nxt = date.fromisoformat(next_pay_str)
            items.append(_make_item("Next Payday", next_pay_str, (nxt - today).days, "income"))
        except Exception:
            pass

    due_day = int(s.get("due_day", "27"))
    if today.day <= due_day:
        due = today.replace(day=due_day)
    else:
        due = today.replace(month=today.month % 12 + 1, day=due_day) if today.month < 12 else today.replace(year=today.year + 1, month=1, day=due_day)
    items.append(_make_item("CC Payment Due", due.isoformat(), (due - today).days, "expense"))

    stmt_day = int(s.get("statement_day", "2"))
    if today.day <= stmt_day:
        stmt = today.replace(day=stmt_day)
    else:
        stmt = today.replace(month=today.month % 12 + 1, day=stmt_day) if today.month < 12 else today.replace(year=today.year + 1, month=1, day=stmt_day)
    items.append(_make_item("CC Statement Closes", stmt.isoformat(), (stmt - today).days, "neutral"))

    return sorted(items, key=lambda x: int(x.days_str.rstrip("d")))


def _make_item(label: str, date_str: str, days: int, itype: str) -> AgendaItem:
    border = "var(--go)" if itype == "income" else ("var(--re)" if itype == "expense" else "var(--cy)")
    urgency = "var(--re)" if days <= 3 else ("var(--mg)" if days <= 7 else "var(--t1)")
    return AgendaItem(
        label=label,
        date_str=date_str,
        days_str=f"{days}d",
        type_label=itype,
        border_color=border,
        days_color=urgency,
    )


# ── Components ─────────────────────────────────────────────────────────────────

def agenda_item_card(item: AgendaItem) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(item.label, style={"color": "var(--t0)", "font_size": "0.82rem"}),
            rx.el.span(
                item.days_str,
                style={"color": item.days_color, "font_family": "'Syne',sans-serif",
                       "font_size": "1.05rem", "font_weight": "700"},
            ),
            style={"display": "flex", "justify_content": "space-between", "align_items": "center"},
        ),
        rx.el.div(item.date_str, style={"color": "var(--t2)", "font_size": "0.58rem", "margin_top": "0.2rem"}),
        class_name="bb-card",
        style={"border_left": "2px solid " + item.border_color, "border_radius": "0 10px 10px 0", "margin_bottom": "0.6rem"},
    )


def cal_event_card(event: CalendarEvent) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(event.title, style={"color": "var(--t0)", "font_size": "0.8rem", "font_weight": "500"}),
            rx.cond(
                event.is_all_day,
                rx.el.span("all-day", class_name="bb-tag"),
                rx.el.span(
                    event.start,
                    style={"color": "var(--cy)", "font_size": "0.56rem", "letter_spacing": "0.08em"},
                ),
            ),
            style={"display": "flex", "justify_content": "space-between", "align_items": "flex-start", "gap": "0.5rem"},
        ),
        rx.cond(
            event.location != "",
            rx.el.div(
                "📍 ", event.location,
                style={"color": "var(--t2)", "font_size": "0.58rem", "margin_top": "0.25rem"},
            ),
        ),
        class_name="bb-card",
        style={"border_left": "2px solid var(--cy)", "border_radius": "0 10px 10px 0", "margin_bottom": "0.6rem"},
    )


def agenda_page() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            rx.el.h1("Agenda", class_name="bb-title"),
            rx.el.p("FINANCIAL EVENTS · CALENDAR · DEADLINES", class_name="bb-subtitle"),
            class_name="bb-page-header",
        ),

        rx.cond(AgendaState.error != "", rx.el.div(AgendaState.error, class_name="bb-error")),

        # ── Two-column layout: financial deadlines | google calendar ──
        rx.el.div(
            # Left: financial events
            rx.el.div(
                rx.el.div("Financial Deadlines", class_name="bb-section", style={"margin_top": "0"}),
                rx.cond(
                    AgendaState.loading,
                    rx.el.div("Loading...", style={"color": "var(--t2)", "font_size": "0.72rem"}),
                    rx.cond(
                        AgendaState.items.length() == 0,
                        rx.el.div("No items.", style={"color": "var(--t2)"}),
                        rx.foreach(AgendaState.items, agenda_item_card),
                    ),
                ),
                style={"flex": "1"},
            ),

            # Right: Google Calendar
            rx.el.div(
                rx.el.div("Google Calendar", class_name="bb-section", style={"margin_top": "0"}),

                # OK — show events
                rx.cond(
                    AgendaState.cal_status == "ok",
                    rx.cond(
                        AgendaState.cal_events.length() == 0,
                        rx.el.div("No upcoming events.", style={"color": "var(--t2)", "font_size": "0.72rem"}),
                        rx.foreach(AgendaState.cal_events, cal_event_card),
                    ),
                ),

                # Needs setup — show instructions
                rx.cond(
                    AgendaState.cal_status == "needs_setup",
                    rx.el.div(
                        rx.el.div(
                            "Connect Google Calendar",
                            style={"color": "var(--cy)", "font_size": "0.72rem", "font_weight": "600", "margin_bottom": "0.6rem"},
                        ),
                        rx.el.div(
                            "1. pip install google-api-python-client google-auth-oauthlib",
                            style={"font_size": "0.64rem", "color": "var(--t1)", "margin_bottom": "0.3rem"},
                        ),
                        rx.el.div(
                            "2. Download OAuth credentials from console.cloud.google.com",
                            style={"font_size": "0.64rem", "color": "var(--t1)", "margin_bottom": "0.3rem"},
                        ),
                        rx.el.div(
                            "3. Save as client_secret.json next to rxconfig.py",
                            style={"font_size": "0.64rem", "color": "var(--t1)", "margin_bottom": "0.3rem"},
                        ),
                        rx.el.div(
                            "4. Run: python -c \"from google_auth_oauthlib.flow import InstalledAppFlow; flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', ['https://www.googleapis.com/auth/calendar.readonly']); creds = flow.run_local_server(); open('google_token.json','w').write(creds.to_json())\"",
                            style={"font_size": "0.58rem", "color": "var(--pu)", "margin_bottom": "0.3rem", "word_break": "break-all", "line_height": "1.6"},
                        ),
                        rx.el.div(
                            "5. Restart the app — events will appear here automatically.",
                            style={"font_size": "0.64rem", "color": "var(--t1)"},
                        ),
                        class_name="bb-card",
                        style={"border_left": "2px solid var(--cy)", "border_radius": "0 10px 10px 0"},
                    ),
                ),

                # Error state
                rx.cond(
                    AgendaState.cal_status == "error",
                    rx.el.div(
                        "Calendar error: ", AgendaState.cal_error,
                        class_name="bb-error",
                    ),
                ),

                style={"flex": "1"},
            ),

            style={"display": "grid", "grid_template_columns": "1fr 1fr", "gap": "2rem"},
        ),

        on_mount=AgendaState.load,
    )
