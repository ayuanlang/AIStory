
import logging
from sqlalchemy import text, inspect
from app.db.session import engine

logger = logging.getLogger(__name__)

def check_and_migrate_tables():
    logger.info("Checking for database migrations...")
    try:
        inspector = inspect(engine)
        
        # Migrate Users Table
        if inspector.has_table("users"):
            columns = [c['name'] for c in inspector.get_columns('users')]
            with engine.begin() as conn:
                if 'is_authorized' not in columns:
                    logger.info("Migrating users: Adding is_authorized")
                    if engine.dialect.name == 'postgresql':
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_authorized BOOLEAN DEFAULT FALSE"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_authorized BOOLEAN DEFAULT 0"))
                
                if 'is_system' not in columns:
                    logger.info("Migrating users: Adding is_system")
                    if engine.dialect.name == 'postgresql':
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_system BOOLEAN DEFAULT FALSE"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_system BOOLEAN DEFAULT 0"))
        
        logger.info("Database migration check complete.")
    except Exception as e:
        logger.error(f"Migration check failed: {e}")
