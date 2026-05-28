import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, episode_id, name, description FROM entities WHERE type='character' AND project_id=243 ORDER BY id DESC;", conn)
print(df)
