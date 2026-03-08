"""Remove redundant transaction_actions table when it is empty.

Rationale:
- Canonical audit table is `transaction_action` (singular).
- `transaction_actions` (plural) is a historical duplicate and should not be used.
- This script is intentionally conservative: it aborts if plural table contains rows.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "aistory.db"


def main() -> None:
    if not DB_PATH.exists():
        print(f"SKIP db not found: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transaction_actions'")
    exists = cur.fetchone() is not None
    if not exists:
        print("SKIP no transaction_actions table")
        conn.close()
        return

    cur.execute("SELECT COUNT(1) FROM transaction_actions")
    count = int(cur.fetchone()[0] or 0)
    if count != 0:
        conn.close()
        raise RuntimeError(f"ABORT: transaction_actions is not empty (rows={count})")

    cur.execute("DROP TABLE IF EXISTS transaction_actions")
    conn.commit()
    conn.close()
    print("OK dropped transaction_actions")


if __name__ == "__main__":
    main()
