import sqlite3

def main():
    db_path = 'backend/aistory.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE transaction_history DROP COLUMN project_id")
        print("Dropped project_id from transaction_history")
    except Exception as e:
        print("Error DROP TH project_id:", e)

    try:
        cur.execute("ALTER TABLE transaction_history DROP COLUMN episode_id")
        print("Dropped episode_id from transaction_history")
    except Exception as e:
        print("Error DROP TH episode_id:", e)

    try:
        cur.execute("ALTER TABLE transaction_action ADD COLUMN project_id INTEGER REFERENCES projects(id)")
        print("Added project_id to transaction_action")
    except Exception as e:
        print("Error ADD TA project_id:", e)

    try:
        cur.execute("ALTER TABLE transaction_action ADD COLUMN episode_id INTEGER REFERENCES episodes(id)")
        print("Added episode_id to transaction_action")
    except Exception as e:
        print("Error ADD TA episode_id:", e)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
