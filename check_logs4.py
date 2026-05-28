import sqlite3
import pandas as pd
import json
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
df = pd.read_sql_query("SELECT response_json FROM llm_call_logs WHERE tag='LLM_RESPONSE' AND response_json IS NOT NULL ORDER BY id DESC LIMIT 5;", conn)
for row in df['response_json']:
    try:
        j = json.loads(row)
        content = j['choices'][0]['message']['content'] if 'choices' in j else j
        if 'characters' in content or 'environments' in content:
            print("FOUND CONTENT:")
            print(content[:500])
            break
    except:
        pass
