import sqlite3
import os

db = sqlite3.connect('aistory.db')
c = db.cursor()
c.execute("select name from sqlite_master where type='table'")
tables = [r[0] for r in c.fetchall()]
for table in tables:
    print(f"Table: {table}")
    if table in ['generation_jobs', 'generations']:
        try:
            c.execute(f"select * from {table} where status='failed' or state='failed'")
            for row in c.fetchall():
                print(row)
        except Exception as e:
            print(f"Error reading {table}: {e}")
            try:
                c.execute(f"select * from {table} order by random() limit 10")
                for row in c.fetchall():
                    print("row:", row)
            except Exception as e2:
                print(f"Failed again: {e2}")

