import sqlite3
from pathlib import Path

DBS = [Path('aistory.db'), Path('sql_app.db')]
TABLES = ['transaction_history', 'transaction_action', 'transaction_actions']

for db_path in DBS:
    print(f'DB={db_path}')
    if not db_path.exists():
        print('  status=missing_file')
        continue

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    for table in TABLES:
        cur.execute("SELECT COUNT(1) FROM sqlite_master WHERE type='table' AND name=?", (table,))
        exists = bool(cur.fetchone()[0])
        print(f'  {table} exists={exists}')
    conn.close()
