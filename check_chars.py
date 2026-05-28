import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, project_id, episode_id, name, type, description, appearance_cn, clothing FROM entities WHERE type='character' ORDER BY id DESC LIMIT 15;", conn)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 50)
df['description'] = df['description'].apply(lambda x: x[:30] if x else '')
print(df)
