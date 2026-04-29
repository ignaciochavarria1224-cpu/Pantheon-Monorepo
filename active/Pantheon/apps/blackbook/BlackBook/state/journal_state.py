"""
state/journal_state.py — Journal entries, Meridian questions, permanent prompts.
"""
from __future__ import annotations

from datetime import date

import reflex as rx

from BlackBook.db import queries

# Fixed daily reflection prompts always shown in the Journal tab
PERMANENT_QUESTIONS: list[str] = [
    "What is the most important financial move I can make this week?",
    "Am I spending in alignment with my actual values and goals?",
    "What progress did I make toward financial independence today?",
    "What is one belief or habit I can upgrade right now?",
    "If I repeated today's financial decisions for a year, where would I end up?",
]


class JournalEntry(rx.Base):
    id: int = 0
    entry_date: str = ""
    tag: str = ""
    body: str = ""


class JournalState(rx.State):
    entries: list[JournalEntry] = []
    loading: bool = False
    error: str = ""
    success: str = ""

    form_date: str = ""
    form_tag: str = "General"
    form_body: str = ""
    filter_tag: str = "All"

    # Meridian AI-generated questions (flattened to list[str])
    meridian_question_date: str = ""
    meridian_question_list: list[str] = []

    @rx.event
    async def load(self) -> None:
        self.loading = True
        self.error = ""
        try:
            raw = queries.load_journal_entries(limit=50, tag_filter=self.filter_tag)
            self.entries = [_to_entry(e) for e in raw]
            if not self.form_date:
                self.form_date = date.today().isoformat()

            # Load Meridian AI questions and flatten to list[str]
            try:
                batches = queries.load_meridian_questions(limit=1)
                if batches:
                    batch = batches[0]
                    self.meridian_question_date = str(batch.get("date", ""))
                    raw_qs = batch.get("questions", [])
                    if isinstance(raw_qs, list):
                        self.meridian_question_list = [_extract_q(q) for q in raw_qs]
                    else:
                        self.meridian_question_list = []
                else:
                    self.meridian_question_date = ""
                    self.meridian_question_list = []
            except Exception:
                self.meridian_question_date = ""
                self.meridian_question_list = []

        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    @rx.event
    async def submit_entry(self) -> None:
        self.error = ""
        self.success = ""
        if not self.form_body.strip():
            self.error = "Entry cannot be empty."
            return
        try:
            queries.save_journal_entry(
                entry_date=date.fromisoformat(self.form_date),
                tag=self.form_tag,
                body=self.form_body,
            )
            self.success = "Entry saved."
            self.form_body = ""
            raw = queries.load_journal_entries(limit=50, tag_filter=self.filter_tag)
            self.entries = [_to_entry(e) for e in raw]
        except Exception as e:
            self.error = str(e)

    @rx.event
    async def delete_entry(self, entry_id: int) -> None:
        try:
            queries.delete_journal_entry(entry_id)
            raw = queries.load_journal_entries(limit=50, tag_filter=self.filter_tag)
            self.entries = [_to_entry(e) for e in raw]
        except Exception as e:
            self.error = str(e)

    @rx.event
    async def set_filter(self, tag: str) -> None:
        self.filter_tag = tag
        raw = queries.load_journal_entries(limit=50, tag_filter=tag)
        self.entries = [_to_entry(e) for e in raw]

    def set_form_date(self, v: str) -> None:
        self.form_date = v

    def set_form_tag(self, v: str) -> None:
        self.form_tag = v

    def set_form_body(self, v: str) -> None:
        self.form_body = v

    def use_question_as_prompt(self, question: str) -> None:
        self.form_body = question
        self.form_tag = "Reflection"


def _extract_q(q: object) -> str:
    if isinstance(q, str):
        return q
    if isinstance(q, dict):
        return str(q.get("question") or q.get("text") or q.get("body") or str(q))
    return str(q)


def _to_entry(e: dict) -> JournalEntry:
    return JournalEntry(
        id=int(e.get("id") or 0),
        entry_date=str(e.get("entry_date") or ""),
        tag=str(e.get("tag") or ""),
        body=str(e.get("body") or ""),
    )
