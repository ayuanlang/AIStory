
import logging
from app.db.session import engine
from sqlalchemy import text, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_users_table():
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('users')]
    
    with engine.connect() as conn:
        # Check and add is_authorized
        if 'is_authorized' not in columns:
            logger.info("Adding 'is_authorized' column to users table...")
            # Detect DB type
            if engine.dialect.name == 'postgresql':
                conn.execute(text("ALTER TABLE users ADD COLUMN is_authorized BOOLEAN DEFAULT FALSE"))
            else: # sqlite
                conn.execute(text("ALTER TABLE users ADD COLUMN is_authorized BOOLEAN DEFAULT 0"))
            logger.info("Added 'is_authorized'")
        else:
            logger.info("'is_authorized' column already exists.")

        # Check and add is_system
        if 'is_system' not in columns:
            logger.info("Adding 'is_system' column to users table...")
            if engine.dialect.name == 'postgresql':
                conn.execute(text("ALTER TABLE users ADD COLUMN is_system BOOLEAN DEFAULT FALSE"))
            else: # sqlite
                conn.execute(text("ALTER TABLE users ADD COLUMN is_system BOOLEAN DEFAULT 0"))
            logger.info("Added 'is_system'")
        else:
            logger.info("'is_system' column already exists.")
            
        conn.commit()

if __name__ == "__main__":
    try:
        migrate_users_table()
        logger.info("Migration completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
