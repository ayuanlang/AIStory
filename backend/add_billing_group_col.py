import sqlite3
import os

db_path = r"C:\AS\AIStory\backend\app.db"

# We execute an alter table directly
conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE payment_orders ADD COLUMN target_group_id INTEGER;")
    print("Added target_group_id to payment_orders")
except Exception as e:
    print("payment_orders error or already exists:", e)

try:
    cur.execute("ALTER TABLE transaction_history ADD COLUMN group_id INTEGER;")
    print("Added group_id to transaction_history")
except Exception as e:
    print("transaction_history error or already exists:", e)

conn.commit()
conn.close()
