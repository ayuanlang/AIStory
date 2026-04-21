import re

def main():
    with open('backend/app/db/init_db.py', 'r', encoding='utf-8') as f:
        text = f.read()

    target = '''        # Ensure transaction_action table exists
        try:
            if not inspector.has_table("transaction_action"):
                TransactionAction.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created transaction_action table")
        except Exception as e:
            logger.error(f"Failed to ensure transaction_action table: {e}")'''

    replacement = '''        # Ensure transaction_action table exists
        try:
            if not inspector.has_table("transaction_action"):
                TransactionAction.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created transaction_action table")
            else:
                # Add project_id and episode_id to existing transaction_action table
                ta_cols = {c['name'] for c in inspector.get_columns('transaction_action')}
                with engine.begin() as conn:
                    if "project_id" not in ta_cols:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                        logger.info("Added project_id to transaction_action")
                    if "episode_id" not in ta_cols:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                        logger.info("Added episode_id to transaction_action")
        except Exception as e:
            logger.error(f"Failed to ensure/migrate transaction_action table: {e}")'''

    if target in text:
        text = text.replace(target, replacement, 1)
        with open('backend/app/db/init_db.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Updated init_db.py")
    else:
        print("Target string not found in init_db.py")

if __name__ == "__main__":
    main()
