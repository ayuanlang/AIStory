import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, name, appearance_cn, clothing FROM entities WHERE project_id=243 AND type='character' ORDER BY id DESC LIMIT 5;", conn)
print(df.to_dict('records'))
