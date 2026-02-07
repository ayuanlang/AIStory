
import logging
from sqlalchemy import text, inspect
from app.db.session import engine

logger = logging.getLogger(__name__)

def check_and_migrate_tables():
    logger.info(f"Starting migration check. Dialect: {engine.dialect.name}")
    
    try:
        # Force migration for Postgres using engine.begin() which handles transaction/commit automatically
        if 'postgres' in engine.dialect.name:
            with engine.begin() as conn:
                logger.info("Attempting Postgres migration...")
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_authorized BOOLEAN DEFAULT FALSE"))
                    logger.info("Executed: ADD COLUMN IF NOT EXISTS is_authorized")
                except Exception as e:
                    logger.error(f"Error adding is_authorized: {e}")

                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_system BOOLEAN DEFAULT FALSE"))
                    logger.info("Executed: ADD COLUMN IF NOT EXISTS is_system")
                except Exception as e:
                    logger.error(f"Error adding is_system: {e}")
        
        # SQLite / Generic Fallback
        else:
            inspector = inspect(engine)
            columns = [c['name'] for c in inspector.get_columns('users')]
            logger.info(f"Current columns (SQLite): {columns}")
            
            with engine.begin() as conn:
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

        # Verification Step
        try:
            inspector = inspect(engine)
            final_columns = [c['name'] for c in inspector.get_columns('users')]
            logger.info(f"MIGRATION COMPLETE. Final columns in 'users': {final_columns}")
        except Exception as e:
            logger.error(f"Verification failed: {e}")

    except Exception as e:
        logger.critical(f"Migration CRITICAL FAILURE: {e}")
