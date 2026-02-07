
import logging
from sqlalchemy import text, inspect
from app.db.session import engine

logger = logging.getLogger(__name__)

def check_and_migrate_tables():
    logger.info("Checking for database migrations...")
    try:
        # Use simple try-except block for each column to be robust against inspection failures or race conditions
        with engine.connect() as conn:
            # PostgreSQL optimized path
            if engine.dialect.name == 'postgresql':
                conn.execute(text("COMMIT")) # Ensure we are not in a failed transaction state if any
                
                # Add is_authorized
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_authorized BOOLEAN DEFAULT FALSE"))
                    logger.info("Checked/Migrated is_authorized (PostgreSQL)")
                except Exception as e:
                    logger.warning(f"Message during is_authorized migration: {e}")

                # Add is_system
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_system BOOLEAN DEFAULT FALSE"))
                    logger.info("Checked/Migrated is_system (PostgreSQL)")
                except Exception as e:
                    logger.warning(f"Message during is_system migration: {e}")
                
                conn.commit()

            # SQLite path (local dev)
            else: 
                inspector = inspect(engine)
                columns = [c['name'] for c in inspector.get_columns('users')]
                
                if 'is_authorized' not in columns:
                    try:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_authorized BOOLEAN DEFAULT 0"))
                        logger.info("Migrated is_authorized (SQLite)")
                    except Exception as e:
                        logger.error(f"Failed to add is_authorized: {e}")

                if 'is_system' not in columns:
                    try:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_system BOOLEAN DEFAULT 0"))
                        logger.info("Migrated is_system (SQLite)")
                    except Exception as e:
                        logger.error(f"Failed to add is_system: {e}")
                conn.commit()
                
        logger.info("Database migration check complete.")
    except Exception as e:
        logger.error(f"Migration check CRITICAL FAILURE: {e}")
