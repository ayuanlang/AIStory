import sqlite3
conn = sqlite3.connect("aistory.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('recharge_plans', 'payment_orders')")
print(c.fetchall())
c.execute("SELECT * FROM recharge_plans")
print(c.fetchall())
conn.close()
