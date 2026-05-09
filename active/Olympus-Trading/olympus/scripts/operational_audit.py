"""Olympus operational audit (read-only investigation).

Determines which database file Olympus has actually been writing to,
whether the system has been running, and what state the storage layer
is in. Strictly read-only — does not move, copy, modify, or delete any
file other than this script itself.

Usage (from the olympus/ working directory):
    python scripts/operational_audit.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, '.')

import os
import re
import sqlite3
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Anchor today per the audit brief (not derived from system clock so the
# report is reproducible).
TODAY = date(2026, 5, 7)

WORK_DIR = Path('.').resolve()
PARENT_DIR = WORK_DIR.parent

# Subtrees we don't bother walking — irrelevant to the storage audit.
SKIP_DIRS = {
    '__pycache__', '.git', '.venv', 'venv', 'node_modules',
    '.pytest_cache', '.idea', '.vscode', 'Pantheon',
}

# The canonical "expected" live DB per Phase 4 design.
CANONICAL_DB = (WORK_DIR / 'data' / 'olympus.db').resolve()


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def header(title: str) -> None:
    print()
    print('=' * 78)
    print(title)
    print('=' * 78)


def subheader(title: str) -> None:
    print()
    print('-- ' + title)


def fmt_mtime(epoch: float) -> str:
    local = datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')
    utc = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
        '%Y-%m-%d %H:%M:%S'
    )
    return f'{local} (local) | {utc} (UTC)'


def in_dropbox(path: Path) -> bool:
    return any('dropbox' in p.lower() for p in path.parts)


# ---------------------------------------------------------------------------
# DB candidate discovery
# ---------------------------------------------------------------------------

def is_db_candidate(name: str) -> bool:
    n = name.lower()
    if n.endswith(('.db', '.sqlite', '.sqlite3', '.db.bak')):
        return True
    if 'olympus' in n and n.endswith(
        ('.bak', '.backup', '.old', '.copy', '.db', '.sqlite', '.sqlite3')
    ):
        return True
    return False


def find_db_files() -> list[Path]:
    found: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(PARENT_DIR):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if is_db_candidate(fn):
                p = (Path(dirpath) / fn).resolve()
                found[str(p)] = p
    paths = list(found.values())

    def _mtime_key(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    paths.sort(key=_mtime_key, reverse=True)
    return paths


# ---------------------------------------------------------------------------
# SQLite read-only helper
# ---------------------------------------------------------------------------

def open_ro(path: Path) -> tuple[sqlite3.Connection | None, str | None]:
    """Open path as SQLite in read-only mode. Returns (conn, None) or (None, error)."""
    try:
        if not path.exists():
            return None, 'file not found'
        url = urllib.request.pathname2url(str(path.resolve()))
        # On Windows pathname2url returns '///C:/...'; on POSIX it returns '/...'.
        if url.startswith('///'):
            uri = 'file:' + url + '?mode=ro'
        elif url.startswith('/'):
            uri = 'file://' + url + '?mode=ro'
        else:
            uri = 'file:/' + url + '?mode=ro'
        conn = sqlite3.connect(uri, uri=True)
        conn.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
        return conn, None
    except sqlite3.DatabaseError as e:
        return None, f'sqlite database error: {e}'
    except sqlite3.Error as e:
        return None, f'sqlite error: {e}'
    except OSError as e:
        return None, f'os error: {e}'
    except Exception as e:  # noqa: BLE001 — defensive
        return None, f'unexpected: {e!r}'


def has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def fetch_create(conn: sqlite3.Connection, name: str) -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row[0] if row else None


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if 'T' in s:
            return datetime.fromisoformat(s)
        return datetime.fromisoformat(s.replace(' ', 'T'))
    except ValueError:
        try:
            return datetime.fromisoformat(s[:19])
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Section 1
# ---------------------------------------------------------------------------

def section_1_locate(files: list[Path]) -> None:
    header('SECTION 1 -- LOCATE EVERY DATABASE FILE')
    print(f'Search root (recursive, Pantheon excluded): {PARENT_DIR}')
    print(f'WORK_DIR (olympus): {WORK_DIR}')
    if not files:
        print()
        print('No database-candidate files found.')
        return
    print()
    print(f'Found {len(files)} database-candidate file(s) '
          '(sorted by mtime, most recent first):')
    for p in files:
        try:
            st = p.stat()
            size = f'{st.st_size:,} bytes'
            mt = fmt_mtime(st.st_mtime)
        except OSError as e:
            size = '<stat error>'
            mt = f'<{e}>'
        print()
        print(f'  Path:    {p}')
        print(f'  Size:    {size}')
        print(f'  Mtime:   {mt}')
        print(f'  Dropbox: {"YES" if in_dropbox(p) else "no"}')


# ---------------------------------------------------------------------------
# Section 2
# ---------------------------------------------------------------------------

def section_2_summaries(files: list[Path]) -> list[dict]:
    header('SECTION 2 -- PER-DATABASE TRADE SUMMARY')

    results: list[dict] = []
    for p in files:
        print()
        print('  ' + ('-' * 74))
        print(f'  Path: {p}')
        info: dict = {'path': p, 'open_ok': False}
        conn, err = open_ro(p)
        if conn is None:
            print(f'  Open: FAILED -- {err}')
            info['error'] = err
            results.append(info)
            continue
        info['open_ok'] = True
        try:
            # trades
            if has_table(conn, 'trades'):
                tn = conn.execute('SELECT COUNT(*) FROM trades').fetchone()[0]
                rng = conn.execute(
                    'SELECT MIN(entry_time), MAX(entry_time) FROM trades '
                    'WHERE entry_time IS NOT NULL'
                ).fetchone()
                info['trades_count'] = tn
                info['trades_min'] = rng[0]
                info['trades_max'] = rng[1]
                print(f'  trades: {tn:,} rows')
                print(f'    entry_time range: {rng[0]}  ..  {rng[1]}  (UTC)')
            else:
                info['trades_count'] = None
                info['trades_max'] = None
                print('  trades: <table missing>')

            # ranking_cycles
            if has_table(conn, 'ranking_cycles'):
                cn = conn.execute(
                    'SELECT COUNT(*) FROM ranking_cycles'
                ).fetchone()[0]
                rng = conn.execute(
                    'SELECT MIN(cycle_timestamp), MAX(cycle_timestamp) '
                    'FROM ranking_cycles WHERE cycle_timestamp IS NOT NULL'
                ).fetchone()
                info['cycles_count'] = cn
                info['cycles_min'] = rng[0]
                info['cycles_max'] = rng[1]
                print(f'  ranking_cycles: {cn:,} rows')
                print(f'    cycle_timestamp range: {rng[0]}  ..  '
                      f'{rng[1]}  (UTC)')
            else:
                info['cycles_count'] = None
                info['cycles_max'] = None
                print('  ranking_cycles: <table missing>')

            # trade_features
            if has_table(conn, 'trade_features'):
                fn = conn.execute(
                    'SELECT COUNT(*) FROM trade_features'
                ).fetchone()[0]
                info['features_count'] = fn
                print(f'  trade_features: {fn:,} rows')
            else:
                info['features_count'] = None
                print('  trade_features: <table missing>')

            # trades_old
            old_present = has_table(conn, 'trades_old')
            info['trades_old'] = old_present
            print(f'  trades_old table: '
                  f'{"PRESENT (pre-repair indicator)" if old_present else "absent"}')

            # trade_features CREATE SQL
            tf_sql = fetch_create(conn, 'trade_features')
            info['tf_create_sql'] = tf_sql
            if tf_sql:
                print('  trade_features CREATE SQL:')
                for line in tf_sql.splitlines():
                    print('    | ' + line)
            else:
                print('  trade_features CREATE SQL: <not present>')

        except sqlite3.Error as e:
            print(f'  Query error during summary: {e}')
            info['error'] = f'query: {e}'
        finally:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        results.append(info)
    return results


# ---------------------------------------------------------------------------
# Section 3
# ---------------------------------------------------------------------------

def _tail_n(path: Path, n: int) -> str:
    try:
        size = path.stat().st_size
        chunk = min(size, 256 * 1024)
        with path.open('rb') as f:
            f.seek(max(0, size - chunk))
            data = f.read()
        text = data.decode('utf-8', errors='replace')
        lines = text.splitlines()
        return '\n'.join('    ' + line for line in lines[-n:])
    except OSError as e:
        return f'    <error reading {path.name}: {e}>'


def section_3_runtime() -> None:
    header('SECTION 3 -- LIVE RUNTIME ARTIFACTS')

    # logs/
    subheader('Log files')
    candidates = [WORK_DIR / 'data' / 'logs', WORK_DIR / 'logs']
    logs_dir = next((c for c in candidates if c.exists()), None)
    if logs_dir is None:
        print('  No logs/ directory found at data/logs or logs/.')
    else:
        print(f'  {logs_dir}')
        log_files: list[tuple[Path, os.stat_result]] = []
        try:
            for fp in sorted(logs_dir.iterdir()):
                if fp.is_file():
                    st = fp.stat()
                    log_files.append((fp, st))
                    print(f'    {fp.name:<40} {st.st_size:>14,} bytes  '
                          f'{fmt_mtime(st.st_mtime)}')
        except OSError as e:
            print(f'  (error listing: {e})')
        if not log_files:
            print('    (directory is empty)')
        if log_files:
            log_files.sort(key=lambda x: x[1].st_mtime, reverse=True)
            most_recent = log_files[0][0]
            subheader(f'Last 50 lines of most recently modified log: '
                      f'{most_recent.name}')
            print(_tail_n(most_recent, 50))

    # .pid / .lock
    subheader('.pid / .lock files in WORK_DIR tree')
    pids: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(WORK_DIR):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(('.pid', '.lock')):
                pids.append(Path(dirpath) / fn)
    if not pids:
        print('  None found.')
    for p in pids:
        try:
            st = p.stat()
            print(f'  {p}')
            print(f'    size={st.st_size}  mtime={fmt_mtime(st.st_mtime)}')
            try:
                content = p.read_text(encoding='utf-8',
                                      errors='replace').strip()
                if content:
                    print(f'    contents: {content[:200]}')
            except OSError:
                pass
        except OSError as e:
            print(f'  {p}  (stat error: {e})')

    # WAL/SHM
    subheader('WAL / SHM files alongside data/olympus.db (current, '
              'non-.corrupt)')
    db_dir = WORK_DIR / 'data'
    for ext in ('-wal', '-shm'):
        fp = db_dir / f'olympus.db{ext}'
        if fp.exists():
            st = fp.stat()
            note = ''
            if ext == '-wal':
                note = ('  <-- non-empty WAL: pending or recent writes'
                        if st.st_size > 0
                        else '  (empty: no pending writes)')
            print(f'  {fp.name:<24} {st.st_size:>14,} bytes  '
                  f'{fmt_mtime(st.st_mtime)}{note}')
        else:
            print(f'  {fp.name:<24} <not present>')

    # .env keys only
    subheader('.env variable names (values redacted)')
    env_path = WORK_DIR / '.env'
    if not env_path.exists():
        print('  No .env file at WORK_DIR.')
    else:
        try:
            text = env_path.read_text(encoding='utf-8', errors='replace')
            keys: list[str] = []
            for line in text.splitlines():
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if s.startswith('export '):
                    s = s[7:]
                if '=' in s:
                    k = s.split('=', 1)[0].strip()
                    if k:
                        keys.append(k)
            print(f'  {len(keys)} variables defined:')
            for k in keys:
                print(f'    {k}')
        except OSError as e:
            print(f'  (error reading: {e})')


# ---------------------------------------------------------------------------
# Section 4
# ---------------------------------------------------------------------------

def _safe_rel(fp: Path, base: Path) -> str:
    try:
        return str(fp.relative_to(base))
    except ValueError:
        return str(fp)


def _grep_py(root: Path, pattern: re.Pattern) -> list[tuple[Path, int, str]]:
    out: list[tuple[Path, int, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            fp = Path(dirpath) / fn
            try:
                text = fp.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    out.append((fp, i, line))
    return out


def section_4_processes() -> dict:
    header('SECTION 4 -- PROCESS / SCHEDULER INDICATORS')
    info: dict = {}

    # launch_olympus.bat
    subheader('launch_olympus.bat (full text)')
    candidates = [WORK_DIR / 'launch_olympus.bat',
                  PARENT_DIR / 'launch_olympus.bat']
    found = next((c for c in candidates if c.exists()), None)
    info['launcher_path'] = found
    if found is None:
        print('  Not found in WORK_DIR or PARENT_DIR.')
    else:
        print(f'  {found}')
        try:
            content = found.read_text(encoding='utf-8', errors='replace')
            for line in content.splitlines():
                print('  | ' + line)
        except OSError as e:
            print(f'  (error reading: {e})')

    # run_live.py first 80 lines (raw)
    subheader('run_live.py -- first 80 lines, raw')
    rl = WORK_DIR / 'run_live.py'
    info['run_live_path'] = rl if rl.exists() else None
    if not rl.exists():
        print('  run_live.py not found in WORK_DIR.')
    else:
        try:
            text = rl.read_text(encoding='utf-8', errors='replace')
            for i, line in enumerate(text.splitlines()[:80], 1):
                print(f'  {i:>3}: {line}')
        except OSError as e:
            print(f'  (error reading: {e})')

    # Hardcoded .db / .sqlite path references in *.py
    subheader('Hardcoded .db / .sqlite references in *.py (recursive WORK_DIR)')
    db_pat = re.compile(r"\.db(?:\.bak)?\b|\.sqlite3?\b")
    db_matches = _grep_py(WORK_DIR, db_pat)
    info['db_path_matches'] = db_matches
    if not db_matches:
        print('  No matches.')
    cap = 200
    for fp, ln, txt in db_matches[:cap]:
        print(f'  {_safe_rel(fp, WORK_DIR)}:{ln}: {txt.strip()[:200]}')
    if len(db_matches) > cap:
        print(f'  ... ({len(db_matches) - cap} more matches truncated)')

    # DROPBOX_PATH / DB_PATH variable references
    subheader('DROPBOX_PATH / DB_PATH references in *.py')
    var_pat = re.compile(r'\b(DROPBOX_PATH|DB_PATH)\b')
    var_matches = _grep_py(WORK_DIR, var_pat)
    info['var_matches'] = var_matches
    if not var_matches:
        print('  No matches.')
    for fp, ln, txt in var_matches[:cap]:
        print(f'  {_safe_rel(fp, WORK_DIR)}:{ln}: {txt.strip()[:200]}')
    if len(var_matches) > cap:
        print(f'  ... ({len(var_matches) - cap} more matches truncated)')

    return info


# ---------------------------------------------------------------------------
# Section 5
# ---------------------------------------------------------------------------

def _describe_db(label: str, path: Path) -> dict | None:
    conn, err = open_ro(path)
    if conn is None:
        print(f'  [{label}] open FAILED: {err}')
        return None
    try:
        d: dict = {'path': path}
        if has_table(conn, 'trades'):
            d['trades_count'] = conn.execute(
                'SELECT COUNT(*) FROM trades'
            ).fetchone()[0]
            rng = conn.execute(
                'SELECT MIN(entry_time), MAX(entry_time) FROM trades '
                'WHERE entry_time IS NOT NULL'
            ).fetchone()
            d['trades_min'] = rng[0]
            d['trades_max'] = rng[1]
            d['trade_ids'] = {
                r[0] for r in conn.execute('SELECT trade_id FROM trades')
            }
        else:
            d['trades_count'] = None
            d['trades_min'] = None
            d['trades_max'] = None
            d['trade_ids'] = set()
        if has_table(conn, 'trade_features'):
            d['features_count'] = conn.execute(
                'SELECT COUNT(*) FROM trade_features'
            ).fetchone()[0]
        else:
            d['features_count'] = None
        return d
    except sqlite3.Error as e:
        print(f'  [{label}] query error: {e}')
        return None
    finally:
        conn.close()


def section_5_conflict() -> dict:
    header('SECTION 5 -- DROPBOX CONFLICT FILE INSPECTION')

    info: dict = {'conflict_exists': False}
    data_dir = WORK_DIR / 'data'
    candidates = list(data_dir.glob('*conflicted copy*.db'))

    if not candidates:
        print('  No conflict-copy database file found in data/.')
        return info
    if len(candidates) > 1:
        print(f'  Multiple conflict files found in data/; using the first:')
        for c in candidates:
            print(f'    {c}')

    conflict_path = candidates[0]
    main_path = WORK_DIR / 'data' / 'olympus.db'
    info['conflict_exists'] = True
    info['conflict_path'] = conflict_path

    print(f'  Conflict file: {conflict_path}')
    print(f'  Main file:     {main_path}')

    print()
    main_d = _describe_db('main', main_path)
    print()
    conf_d = _describe_db('conflict', conflict_path)

    if main_d is None or conf_d is None:
        print('  Could not compare; one or both DBs failed to open cleanly.')
        return info

    print()
    print('  Side-by-side comparison:')
    print(f'  {"":24} {"main":>22}    {"conflict":>22}')
    print(f'  {"trades count":<24} '
          f'{str(main_d["trades_count"]):>22}    '
          f'{str(conf_d["trades_count"]):>22}')
    print(f'  {"earliest entry_time":<24} '
          f'{str(main_d.get("trades_min")):>22}    '
          f'{str(conf_d.get("trades_min")):>22}')
    print(f'  {"latest entry_time":<24} '
          f'{str(main_d.get("trades_max")):>22}    '
          f'{str(conf_d.get("trades_max")):>22}')
    print(f'  {"trade_features count":<24} '
          f'{str(main_d["features_count"]):>22}    '
          f'{str(conf_d["features_count"]):>22}')

    main_ids = main_d['trade_ids']
    conf_ids = conf_d['trade_ids']
    only_in_conflict = conf_ids - main_ids
    only_in_main = main_ids - conf_ids
    print()
    print(f'  trade_ids in conflict file but NOT in main DB: '
          f'{len(only_in_conflict):,}')
    print(f'  trade_ids in main DB but NOT in conflict file: '
          f'{len(only_in_main):,}')
    print(f'  trade_ids common to both:                       '
          f'{len(main_ids & conf_ids):,}')

    info['only_in_conflict'] = len(only_in_conflict)
    info['only_in_main'] = len(only_in_main)
    return info


# ---------------------------------------------------------------------------
# Section 6
# ---------------------------------------------------------------------------

def section_6_continuity(summaries: list[dict]) -> dict:
    header('SECTION 6 -- RECENT OPERATIONAL CONTINUITY '
           '(real, anchored on today)')

    candidates = [
        s for s in summaries
        if s.get('open_ok') and s.get('trades_max') is not None
    ]
    if not candidates:
        print('  No DB with trades data available; per-day breakdown skipped.')
        return {'best': None}

    candidates.sort(key=lambda s: s['trades_max'], reverse=True)
    best = candidates[0]

    print(f'  Most-recent-data DB (by max(entry_time)): {best["path"]}')
    print(f'    latest entry_time:         {best["trades_max"]} (UTC)')
    print(f'    latest cycle_timestamp:    {best.get("cycles_max")} (UTC)')
    print()
    window_start = TODAY - timedelta(days=20)
    print(f'  Anchor (today, per brief): {TODAY.isoformat()}')
    print(f'  Window: {window_start.isoformat()} .. {TODAY.isoformat()} '
          '(21 calendar days, inclusive)')

    conn, err = open_ro(best['path'])
    if conn is None:
        print(f'  Reopen failed: {err}')
        return {'best': best}

    try:
        trades_by_day = {
            r[0]: r[1] for r in conn.execute(
                'SELECT substr(entry_time, 1, 10) AS d, COUNT(*) FROM trades '
                'WHERE substr(entry_time, 1, 10) BETWEEN ? AND ? '
                'GROUP BY d',
                (window_start.isoformat(), TODAY.isoformat()),
            )
        }
        if has_table(conn, 'ranking_cycles'):
            cycles_by_day = {
                r[0]: r[1] for r in conn.execute(
                    'SELECT substr(cycle_timestamp, 1, 10) AS d, COUNT(*) '
                    'FROM ranking_cycles '
                    'WHERE substr(cycle_timestamp, 1, 10) BETWEEN ? AND ? '
                    'GROUP BY d',
                    (window_start.isoformat(), TODAY.isoformat()),
                )
            }
        else:
            cycles_by_day = {}
    finally:
        conn.close()

    print()
    print(f'  {"date":<12} {"weekday":<10} {"trades":>8} {"cycles":>8}  notes')
    gaps: list[str] = []
    silent: list[str] = []
    for i in range(21):
        d = window_start + timedelta(days=i)
        ds = d.isoformat()
        wd = d.strftime('%a')
        is_weekday = d.weekday() < 5
        t_n = trades_by_day.get(ds, 0)
        c_n = cycles_by_day.get(ds, 0)
        note = ''
        if is_weekday:
            if t_n == 0 and c_n == 0:
                note = '  <-- GAP (weekday, no trades or cycles)'
                gaps.append(ds)
            elif t_n > 0 and c_n == 0:
                note = '  <-- RANKING-SILENT (trades but no cycles)'
                silent.append(ds)
        print(f'  {ds:<12} {wd:<10} {t_n:>8,} {c_n:>8,}{note}')

    print()
    print(f'  Weekday gap days   ({len(gaps):>2}): '
          f'{", ".join(gaps) if gaps else "(none)"}')
    print(f'  Ranking-silent days ({len(silent):>2}): '
          f'{", ".join(silent) if silent else "(none)"}')

    return {
        'best': best,
        'gaps': gaps,
        'silent': silent,
    }


# ---------------------------------------------------------------------------
# Section 7
# ---------------------------------------------------------------------------

def _suspected_status(best: dict | None,
                      summaries: list[dict],
                      days_since: int | None) -> str:
    if best is None:
        return ('INSUFFICIENT INFO -- cannot determine '
                '(no DB has any trades)')
    if days_since is None:
        return ('INSUFFICIENT INFO -- cannot determine '
                '(could not parse latest entry_time)')

    last_dt = parse_iso(best['trades_max'])
    overlapping = []
    for s in summaries:
        if not s.get('open_ok') or s is best:
            continue
        m = s.get('trades_max')
        if not m:
            continue
        m_dt = parse_iso(m)
        if not m_dt or not last_dt:
            continue
        if abs((m_dt - last_dt).total_seconds()) <= 86400:
            overlapping.append(s)

    if days_since <= 2 and overlapping:
        return ('DATABASE LOCATION AMBIGUOUS -- multiple DBs with '
                'overlapping recent activity')
    if days_since <= 2:
        if str(best['path']) != str(CANONICAL_DB):
            return ('OLYMPUS HAS BEEN RUNNING -- newer DB found, audit '
                    f'was on stale file (running DB: {best["path"]})')
        return (f'OLYMPUS HAS BEEN RUNNING -- last trade '
                f'{best["trades_max"]} (UTC)')
    last_date = last_dt.date().isoformat() if last_dt else '<unknown>'
    return (f'OLYMPUS STOPPED ON {last_date} -- no DB has activity past '
            'that date')


def section_7_verdict(files: list[Path],
                      summaries: list[dict],
                      sec4_info: dict,
                      sec5_info: dict,
                      sec6_info: dict) -> None:
    header('SECTION 7 -- VERDICT')

    n = len(files)
    most_recent_file = files[0] if files else None

    print(f'  Number of database files found: {n}')
    if most_recent_file:
        try:
            st = most_recent_file.stat()
            print(f'  Most recently modified DB (by file mtime):')
            print(f'    {most_recent_file}')
            print(f'    mtime: {fmt_mtime(st.st_mtime)}')
        except OSError as e:
            print(f'  Most recently modified DB: {most_recent_file}  '
                  f'(stat error: {e})')
    else:
        print('  Most recently modified DB: <none>')

    # run_live.py target DB references
    rl_db_refs: list[tuple[int, str]] = []
    for fp, ln, txt in sec4_info.get('db_path_matches', []):
        if fp.name == 'run_live.py':
            rl_db_refs.append((ln, txt.strip()))
    print(f'  Database path references in run_live.py: '
          f'{len(rl_db_refs)} match(es)')
    for ln, txt in rl_db_refs[:5]:
        print(f'    line {ln}: {txt[:160]}')

    # Most-recent-data DB (by max entry_time)
    best = sec6_info.get('best')
    days_since = None
    days_since_cycle = None
    if best:
        print(f'  Most-recent-data DB (by max(entry_time)): {best["path"]}')
        last_dt = parse_iso(best['trades_max'])
        if last_dt:
            days_since = (TODAY - last_dt.date()).days
        cmax = best.get('cycles_max')
        c_dt = parse_iso(cmax) if cmax else None
        if c_dt:
            days_since_cycle = (TODAY - c_dt.date()).days
        print(f'    latest entry_time:        {best["trades_max"]} (UTC)')
        print(f'    days since last trade:    '
              f'{days_since if days_since is not None else "<unknown>"}')
        print(f'    latest ranking cycle:     {cmax} (UTC)')
        print(f'    days since last cycle:    '
              f'{days_since_cycle if days_since_cycle is not None else "<unknown>"}')
        match = (str(best['path']) == str(CANONICAL_DB))
        print(f'  Match: most-recent-data DB == data/olympus.db (canonical): '
              f'{"YES" if match else "NO"}')
    else:
        print('  Most-recent-data DB: <no DB has any trades>')

    # Conflict
    if sec5_info.get('conflict_exists'):
        only_c = sec5_info.get('only_in_conflict')
        if only_c is None:
            print('  Conflict file unique trades: <comparison failed>')
        elif only_c > 0:
            print(f'  Conflict file contains unique trades not in main DB: '
                  f'YES ({only_c})')
        else:
            print('  Conflict file contains unique trades not in main DB: '
                  'NO (0)')
    else:
        print('  Conflict file: <not present>')

    # Dropbox
    in_dbx = bool(most_recent_file and in_dropbox(most_recent_file))
    print(f'  Storage in Dropbox-synced directory: '
          f'{"YES" if in_dbx else "NO"}')

    # Suspected status
    print()
    status = _suspected_status(best, summaries, days_since)
    print(f'  Suspected status:')
    print(f'    {status}')
    print('=' * 78)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # The audit prints raw lines from arbitrary files (logs, source code,
    # comments). Some contain non-ASCII characters (e.g. >=) that break
    # the default cp1252 Windows console. Switch stdout to UTF-8 with
    # replacement on unencodable bytes so the report never aborts.
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError, ValueError):
        pass

    print()
    print('Olympus operational audit (read-only investigation)')
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    print(f'Run timestamp: {now_utc.isoformat()}')
    print(f'WORK_DIR:      {WORK_DIR}')
    print(f'PARENT_DIR:    {PARENT_DIR}')
    print(f'Anchor (today, per brief): {TODAY.isoformat()}')

    files = find_db_files()
    section_1_locate(files)
    summaries = section_2_summaries(files)
    section_3_runtime()
    sec4_info = section_4_processes()
    sec5_info = section_5_conflict()
    sec6_info = section_6_continuity(summaries)
    section_7_verdict(files, summaries, sec4_info, sec5_info, sec6_info)


if __name__ == '__main__':
    main()
