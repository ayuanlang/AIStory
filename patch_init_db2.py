import re

def main():
    with open('backend/app/db/init_db.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Find the section managing transaction_history columns
    target = '''        # Add balance_after and task_type info
        try:
            if inspector.has_table("transaction_history"):
                with engine.begin() as conn:
                    existing_th_cols = {c['name'] for c in inspector.get_columns('transaction_history')}
                    if "balance_after" not in existing_th_cols:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN balance_after INTEGER DEFAULT 0"))
                    if "task_type" not in existing_th_cols:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN task_type VARCHAR"))
                    if "provider" not in existing_th_cols:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN provider VARCHAR"))
                    if "model" not in existing_th_cols:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN model VARCHAR"))
        except Exception as e:
            logger.error(f"Failed to migrate transaction_history columns: {e}")'''

    replacement = '''        # Add balance_after and optionally description info to transaction_history
        try:
            if inspector.has_table("transaction_history"):
                with engine.begin() as conn:
                    existing_th_cols = {c['name'] for c in inspector.get_columns('transaction_history')}
                    if "balance_after" not in existing_th_cols:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN balance_after INTEGER DEFAULT 0"))
                    if "description" not in existing_th_cols:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN description VARCHAR"))
        except Exception as e:
            logger.error(f"Failed to migrate transaction_history columns: {e}")'''

    if target in text:
        text = text.replace(target, replacement, 1)
        with open('backend/app/db/init_db.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Updated init_db.py for transaction_history columns")
    else:
        print("Target string for TH columns not found in init_db.py")

if __name__ == "__main__":
    main()