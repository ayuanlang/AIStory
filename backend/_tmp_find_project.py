import sqlite3

con = sqlite3.connect(r"c:\AS\AIStory\backend\aistory.db")
cur = con.cursor()
print("llm today")
rows = cur.execute(
    """
    SELECT id, project_id, action, tag, model, substr(error_msg,1,120), timestamp
    FROM llm_call_logs
    WHERE timestamp >= '2026-11-08'
    ORDER BY id DESC
    LIMIT 30
    """
).fetchall()
print("count", len(rows))
for r in rows:
    print(r)
print("--- system logs today ---")
rows = cur.execute(
    """
    SELECT id, action, substr(details,1,160), timestamp
    FROM system_logs
    WHERE timestamp >= '2026-11-08'
    ORDER BY id DESC
    LIMIT 20
    """
).fetchall()
for r in rows:
    print(r)
