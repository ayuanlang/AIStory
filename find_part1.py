import sqlite3
import json

conn = sqlite3.connect('c:/AS/AIStory/backend/aistory.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, timestamp, length(response_json) FROM llm_call_logs WHERE response_json LIKE '%Part 1%' ORDER BY id DESC LIMIT 5").fetchall()

print("FOUND:")
for r in rows:
    print(dict(r))
