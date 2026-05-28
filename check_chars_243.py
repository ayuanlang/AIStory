import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, episode_id, name, description, appearance_cn FROM entities WHERE type='character' AND project_id=243 ORDER BY id DESC;", conn)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 30)
df['description'] = df['description'].apply(lambda x: x[:30] if x else '')
df['appearance_cn'] = df['appearance_cn'].apply(lambda x: x[:30] if x else '')
print(df)
