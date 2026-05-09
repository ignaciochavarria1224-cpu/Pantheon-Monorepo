import sqlite3
c = sqlite3.connect('file:data/olympus.db?mode=ro', uri=True)
print('trades max:    ', c.execute('SELECT MAX(entry_time) FROM trades').fetchone()[0])
print('cycles max:    ', c.execute('SELECT MAX(cycle_timestamp) FROM ranking_cycles').fetchone()[0])
has_events = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_events'").fetchone()
if has_events:
    cols = [r[1] for r in c.execute('PRAGMA table_info(system_events)').fetchall()]
    ts_col = 'timestamp' if 'timestamp' in cols else ('event_timestamp' if 'event_timestamp' in cols else ('created_at' if 'created_at' in cols else None))
    if ts_col:
        print(f'events max ({ts_col}):', c.execute(f'SELECT MAX({ts_col}) FROM system_events').fetchone()[0])
        print('events count:  ', c.execute('SELECT COUNT(*) FROM system_events').fetchone()[0])
    else:
        print('events: table exists but no timestamp-like column found, columns:', cols)
else:
    print('events: system_events table missing')
print('trades count:  ', c.execute('SELECT COUNT(*) FROM trades').fetchone()[0])
