"""
Import ChatGPT conversation export into Black Book journal_entries.

ChatGPT exports a folder of conversations-000.json ... conversations-NNN.json files.
Pass the folder path. The script filters for personal reflections and journal-like
messages, skipping school work, task requests, and academic content.

Usage:
    python import_chatgpt.py "C:/path/to/export-folder"           # preview first 10
    python import_chatgpt.py "C:/path/to/export-folder" --import  # actually import
"""

import json
import sys
import glob
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from db.neon_bridge import get_connection

# ── Filters ───────────────────────────────────────────────────────────────────

SCHOOL_TITLE_KEYWORDS = [
    'essay', 'thesis', 'paragraph', 'factori', 'quadratic', 'polynomial',
    'freedmen', 'pearl harbor', 'civil war', 'gentrification', 'macbeth', '1984',
    'history', 'biology', 'chemistry', 'photosynthesis', 'dred scott', 'lincoln',
    'frances perkins', 'presidential paper', 'french invasion', 'union confederate',
    'hoover', 'study guide', 'classification', 'trailblaz', 'speech analysis',
    'harvey milk', 'bobby', 'letter to', 'confederate', 'stubborn seed',
    'debates impact', 'article summary', 'grade inquiry', 'cultural heritage',
    'tech impact', 'test performance', 'global passion', 'junior year academic',
    'plankton', 'experiment', 'lab ', 'plagiarism', 'life outside london',
]

SKIP_MSG_STARTS = (
    'write ', 'create ', 'generate ', 'list ', 'summarize ', 'explain ',
    'help me write', 'help me create', 'give me ', 'can you write', 'please write',
    'make me ', 'draft ', 'translate ', 'fix the ', 'rewrite ', 'what is ',
    'what are ', 'how do ', 'how to ', 'who is ', 'calculate ', 'solve ',
    'define ', 'describe ', 'compare ', 'contrast ', 'analyze ', 'find the ',
    'prove ', 'show that ', 'simplify ', 'factor ', 'can you help me check',
    'switch up', 'help me check', 'check my application', 'is this a correctly',
    'in an effort to', 'read this speech', 'use the article', 'our overall outcome',
    'look at these', 'would these', 'paragraph 1:', 'paragraph 2:',
    'read this and', 'i need to create a', 'i need to write', 'i need to make a',
    'i want to send an email', 'i want to write a comment', 'i want to write a song',
    'i want to apply', 'conduct a ', 'i want to create a ', 'i want to make a',
    'the name of the woman', 'i just received this email', 'i need to create a powerpoint',
    'i need to decline',
)

SKIP_MSG_CONTAINS = (
    'group of answer choices', 'which of the following', 'which of these concepts',
    "maslow's hierarchy", 'describe the company you chose',
    'find out why douglas', 'the confederate economy', 'squared off in a series',
    'multiple choice', 'answer: a)', 'plankton', 'pavlova', 'culinary and business',
    'columbia summer', 'admissions officer', 'the new york court',
    'harvey weinstein', 'anyone staying', 'dear ms bearne',
    'application fee', 'non-refundable', 'powerpoint', 'character analysis of brick',
    'a cat on a hot tin roof', 'market and competitive analysis for a',
    'full market and competitive',
)

# Genuine personal language signals
PERSONAL_WORDS = [
    'i am ', 'i have ', 'i want ', 'i need ', 'i feel ', 'i think ', 'i believe ',
    "i'm ", "i've ", "i'd ", 'my goal', 'my plan', 'my life', 'my money',
    'my business', 'my trading', 'my portfolio', 'my journal', 'my project',
    'i started', 'i decided', 'i realized', 'to be honest', 'honestly i',
    'i struggle', 'i want to', 'i am going', 'i just ', 'i recently',
    "i've been", "i'm not", "i'm starting", "i'm trying", "i'm feeling",
    "i'm beginning", "i'm working", "i'm building",
]


def _ts_to_date(ts) -> str | None:
    try:
        return datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d')
    except Exception:
        return None


def _is_personal(text: str, entry_date: str) -> bool:
    """Return True if this message reads like a personal reflection, not a task."""
    if len(text) < 140:
        return False
    tl = text.lower().strip()
    if any(tl.startswith(s) for s in SKIP_MSG_STARTS):
        return False
    if any(s in tl for s in SKIP_MSG_CONTAINS):
        return False
    score = sum(1 for w in PERSONAL_WORDS if w in tl)
    year = int(entry_date[:4]) if entry_date else 2025
    # Earlier years had more school work — require stronger personal signal
    min_score = 4 if year <= 2023 else (3 if year == 2024 else 2)
    return score >= min_score


def load_all_conversations(folder: str) -> list:
    """Load all conversations-*.json files from the export folder."""
    files = sorted(glob.glob(str(Path(folder) / 'conversations-*.json')))
    if not files:
        # Fallback: try single conversations.json
        single = Path(folder) / 'conversations.json'
        if single.exists():
            files = [str(single)]
    if not files:
        raise FileNotFoundError(f"No conversations JSON files found in {folder}")
    all_convs = []
    for f in files:
        data = json.loads(Path(f).read_text(encoding='utf-8'))
        all_convs.extend(data)
    return all_convs


def extract_entries(folder: str) -> list[dict]:
    all_convs = load_all_conversations(folder)
    entries = []
    for c in all_convs:
        title = c.get('title') or 'ChatGPT'
        title_lower = title.lower()
        if any(kw in title_lower for kw in SCHOOL_TITLE_KEYWORDS):
            continue
        mapping = c.get('mapping', {})
        msg_list = []
        for node in mapping.values():
            msg = node.get('message')
            if not msg:
                continue
            if msg.get('author', {}).get('role') != 'user':
                continue
            parts = msg.get('content', {}).get('parts', [])
            text = ' '.join(str(p) for p in parts if isinstance(p, str)).strip()
            ts = msg.get('create_time') or 0
            if text:
                msg_list.append((ts, text))
        msg_list.sort()
        for ts, text in msg_list:
            entry_date = _ts_to_date(ts)
            if not entry_date:
                continue
            if not _is_personal(text, entry_date):
                continue
            entries.append({
                'entry_date': entry_date,
                'tag': 'ChatGPT',
                'body': f'[{title}]\n\n{text}',
                'ts': ts,
            })
    # Sort by date, deduplicate
    entries.sort(key=lambda e: e['ts'])
    seen, unique = set(), []
    for e in entries:
        key = e['body'][:200]
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def preview(entries: list[dict], n: int = 10) -> None:
    by_year: dict = {}
    for e in entries:
        y = e['entry_date'][:4]
        by_year[y] = by_year.get(y, 0) + 1

    print(f"\nFound {len(entries)} personal entries to import.")
    print(f"By year: {by_year}")
    print(f"\nShowing first {min(n, len(entries))}:\n")
    for e in entries[:n]:
        print(f"  [{e['entry_date']}]  {e['body'][:180].strip()}")
        print()
    if len(entries) > n:
        print(f"  ... and {len(entries) - n} more.")
    print("\nRun with --import to insert into Black Book.\n")


def do_import(entries: list[dict]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    imported = skipped = 0
    try:
        for e in entries:
            cur.execute(
                "SELECT id FROM journal_entries WHERE entry_date = %s AND body = %s",
                (e['entry_date'], e['body'])
            )
            if cur.fetchone():
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO journal_entries (entry_date, tag, body) VALUES (%s, %s, %s)",
                (e['entry_date'], e['tag'], e['body'])
            )
            imported += 1
        conn.commit()
        print(f"\nDone: {imported} entries imported, {skipped} duplicates skipped.")
        print("Next: run  python evolve.py evolve  to process the new entries.\n")
    except Exception as exc:
        conn.rollback()
        print(f"\nImport failed: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    folder = args[0]
    if not Path(folder).exists():
        print(f"Path not found: {folder}")
        sys.exit(1)

    entries = extract_entries(folder)
    if '--import' in args:
        do_import(entries)
    else:
        preview(entries)
