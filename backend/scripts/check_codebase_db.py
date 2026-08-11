import sqlite3
conn = sqlite3.connect('codebase_visualizer.db')
cur = conn.cursor()
cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','index')")
rows = cur.fetchall()
print('sqlite_master entries:')
for r in rows:
    print(r)
cur.execute("PRAGMA table_info('repository')")
print('repository columns:', cur.fetchall())
cur.execute("PRAGMA index_list('repository')")
indexes = cur.fetchall()
print('indexes:', indexes)
for idx in indexes:
    name = idx[1]
    cur.execute(f"PRAGMA index_info('{name}')")
    print(name, cur.fetchall())
conn.close()
