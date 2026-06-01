import sqlite3
import json

conn = sqlite3.connect(r'c:\AS\AIStory\backend\ai_story.db')
try:
    c = conn.cursor()
    c.execute("SELECT api_key, config FROM provider_key_pool WHERE provider_name='ark-seedance'")
    for row in c.fetchall():
        print(row)
except Exception as e:
    print("Error:", e)
