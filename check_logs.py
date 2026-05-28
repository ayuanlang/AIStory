import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT id, model, prompt_tokens, result_text FROM llm_call_logs ORDER BY id DESC LIMIT 5;", conn)
pd.set_option('display.max_colwidth', 50)
print(df)
