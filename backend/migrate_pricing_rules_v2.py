import sqlite3
import os

# Adjust path to your DB
DB_PATH = os.path.join(os.path.dirname(__file__), "aistory.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(pricing_rules)")
        columns = [info[1] for info in cursor.fetchall()]
        
        new_columns = {
            "ref_cost_cny": "REAL",
            "ref_cost_input_cny": "REAL",
            "ref_cost_output_cny": "REAL",
            "ref_markup": "REAL DEFAULT 1.5",
            "ref_exchange_rate": "REAL DEFAULT 10.0"
        }

        for col, type_def in new_columns.items():
            if col not in columns:
                print(f"Adding column {col}...")
                cursor.execute(f"ALTER TABLE pricing_rules ADD COLUMN {col} {type_def}")
        
        conn.commit()
        print("Pricing Rules migration completed successfully.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
