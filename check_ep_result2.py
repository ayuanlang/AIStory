import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, ai_entity_design_result FROM episodes WHERE ai_entity_design_result IS NOT NULL ORDER BY id DESC LIMIT 2;", conn)
for _, row in df.iterrows():
    print(f"ID: {row['id']}")
    print(row['ai_entity_design_result'][:1000] if row['ai_entity_design_result'] else None)
    print("-" * 50)
