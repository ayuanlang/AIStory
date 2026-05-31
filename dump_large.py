import sqlite3
import json

conn = sqlite3.connect('c:/AS/AIStory/backend/aistory.db')
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT result_json FROM async_tasks WHERE task_id='e2d98b081b304c35932bc5e87764d81d'").fetchone()
with open('c:/AS/AIStory/dump_task_e2.txt', 'w', encoding='utf-8') as f:
    f.write(row['result_json'])
