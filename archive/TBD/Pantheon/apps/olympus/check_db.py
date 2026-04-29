import sqlite3

conn = sqlite3.connect('data/olympus.db')

print('=== TRADES TABLE ===')
r = conn.execute('SELECT COUNT(*) FROM trades').fetchone()
print('Total rows: ' + str(r[0]))

r = conn.execute('SELECT MIN(entry_time), MAX(exit_time) FROM trades').fetchone()
print('Date range: ' + str(r[0]) + ' -> ' + str(r[1]))

r = conn.execute('SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL').fetchone()
print('Completed trades: ' + str(r[0]))

r = conn.execute('SELECT COUNT(*) FROM trades WHERE exit_time IS NULL').fetchone()
print('Open trades: ' + str(r[0]))

print()
print('=== TRADE FEATURES TABLE ===')
r = conn.execute('SELECT COUNT(*) FROM trade_features').fetchone()
print('Total rows: ' + str(r[0]))

print()
print('=== ALL TABLES AND ROW COUNTS ===')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    try:
        r = conn.execute('SELECT COUNT(*) FROM ' + t[0]).fetchone()
        print(t[0] + ': ' + str(r[0]) + ' rows')
    except Exception as e:
        print(t[0] + ': ERROR - ' + str(e))

conn.close()