import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, episode_id, name, type, description FROM entities WHERE project_id=241 ORDER BY id DESC;", conn)
print(df)
