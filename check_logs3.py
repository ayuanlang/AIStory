import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(llm_call_logs)")
columns = [info[1] for info in cursor.fetchall()]
print(columns)
df = pd.read_sql_query(f"SELECT * FROM llm_call_logs ORDER BY id DESC LIMIT 2;", conn)
print(df)
