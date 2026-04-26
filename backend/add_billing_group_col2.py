import sqlite3
import os

db_path = r"C:\AS\AIStory\backend\aistory.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE payment_orders ADD COLUMN target_group_id INTEGER;")
    print("Added target_group_id to payment_orders")
except Exception as e:
    print("payment_orders error or already exists:", e)

try:
    # Not using SQLite ForeignKey constraint because ALTER TABLE doesn't support it directly
    cur.execute("ALTER TABLE transaction_history ADD COLUMN target_group_id INTEGER;")
    print("Added target_group_id to transaction_history")
except Exception as e:
    print("transaction_history error or already exists:", e)

conn.commit()
conn.close()