import sqlite3
import pandas as pd
conn = sqlite3.connect(r'c:\AS\AIStory\backend\aistory.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())
