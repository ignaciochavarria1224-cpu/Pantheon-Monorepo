import sqlite3
conn = sqlite3.connect('data/olympus.db')

print('=== TRADES TABLE ===')
r = conn.execute('SELECT COUNT(*) FROM trades').fetchone()
print(f'Total rows: {r[0]}')

r = conn.execute('SELECT MIN(entry_time), MAX(exit_time) FROM trades').fetchone()
print(f'Date range: {r[0]} -> {r[1]}')

r = conn.execute('SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL').fetchone()
print(f'Completed trades: {r[0]}')

r = conn.execute('SELECT COUNT(*) FROM trades WHERE exit_time IS NULL').fetchone()
print(f'Open trades: {r[0]}')

print()
print('=== TRADE FEATURES TABLE ===')
r = conn.execute('SELECT COUNT(*) FROM trade_features').fetchone()
print(f'Total rows: {r[0]}')

print()
print('=== ALL TABLES AND ROW COUNTS ===')
conn2 = sqlite3.connect('data/olympus.db')
tables = conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    try:
        r = conn.execute('SELECT COUNT(*) FROM ' + t[0]).fetchone()
        print(t[0] + ': ' + str(r[0]) + ' rows')
    except:
        pass

conn.close()
