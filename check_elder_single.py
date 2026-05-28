import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, episode_id, name, type, description, appearance_cn, clothing FROM entities WHERE project_id=243 AND name='大长老';", conn)
print(df.to_dict('records'))
