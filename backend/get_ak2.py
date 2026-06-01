import sqlite3

conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
c = conn.cursor()
c.execute("SELECT api_key, config FROM provider_key_pool WHERE provider_name='ark-seedance'")
for row in c.fetchall():
    print(row)
