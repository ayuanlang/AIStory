import sqlite3
import os
from datetime import datetime

def migrate_recharge(db_path):
    print(f"Connecting to: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Create recharge_plans
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recharge_plans'")
        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS recharge_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                min_amount INTEGER NOT NULL,
                max_amount INTEGER NOT NULL, 
                credit_rate INTEGER DEFAULT 100,
                bonus INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1
            )
            """)
            print("Created 'recharge_plans' table.")
            
            # Seed Default Plans
            plans = [
                # 1-10元: 100积分/元
                (1, 99, 100, 0),
                # 100-1000元: 300积分/元
                (100, 10000, 300, 0) 
            ]
            cursor.executemany("INSERT INTO recharge_plans (min_amount, max_amount, credit_rate, bonus) VALUES (?, ?, ?, ?)", plans)
            print("Seeded default recharge plans.")
        else:
            print("Table 'recharge_plans' already exists.")
            
    except Exception as e:
        print(f"Error creating recharge_plans: {e}")

    # 2. Create payment_orders
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payment_orders'")
        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no VARCHAR UNIQUE,
                user_id INTEGER,
                amount INTEGER NOT NULL,
                credits INTEGER NOT NULL,
                status VARCHAR DEFAULT 'PENDING',
                pay_url VARCHAR,
                provider VARCHAR DEFAULT 'wechat',
                created_at VARCHAR,
                paid_at VARCHAR,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_orders_order_no ON payment_orders (order_no)")
            print("Created 'payment_orders' table.")
        else:
            print("Table 'payment_orders' already exists.")

    except Exception as e:
        print(f"Error creating payment_orders: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    db_path = "backend/aistory.db"
    if not os.path.exists(db_path):
        # Fallback relative
        db_path = "aistory.db"
    
    if os.path.exists(db_path):
        migrate_recharge(db_path)
    else:
        print("DB not found.")
