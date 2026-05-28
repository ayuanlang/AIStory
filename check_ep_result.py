import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT ai_entity_design_result FROM episodes WHERE id=413;", conn)
print(df['ai_entity_design_result'][0][:1500] if df['ai_entity_design_result'][0] else None)
