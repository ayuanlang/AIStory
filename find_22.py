import sqlite3
import json

conn = sqlite3.connect('c:/AS/AIStory/backend/aistory.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, payload_json, response_json, timestamp FROM llm_call_logs ORDER BY id DESC LIMIT 20").fetchall()

for r in rows:
    req = r['payload_json']
    if not req:
        print(f"[{r['id']}] NULL req")
        continue

    try:
        j = json.loads(req)
        func = j.get('function_name', 'MISSING_FUNC_KEY')
        print(f"[{r['id']}] -> {func}")
    except Exception as e:
        print(f"[{r['id']}] INVALID JSON")
