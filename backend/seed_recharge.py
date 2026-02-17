import sqlite3

def seed():
    conn = sqlite3.connect("aistory.db")
    c = conn.cursor()
    c.execute("SELECT count(*) FROM recharge_plans")
    if c.fetchone()[0] == 0:
        print("Seeding...")
        c.executemany("INSERT INTO recharge_plans (min_amount, max_amount, credit_rate, bonus, is_active) VALUES (?, ?, ?, ?, ?)", [
            (1, 99, 100, 0, 1),
            (100, 10000, 300, 0, 1)
        ])
        conn.commit()
        print("Done.")
    else:
        print("Already seeded.")
    conn.close()

if __name__ == "__main__":
    seed()
