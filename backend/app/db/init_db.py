
import logging
from sqlalchemy import text, inspect
from app.db.session import engine

logger = logging.getLogger(__name__)

def check_and_migrate_tables():
    print("!!! MIGRATION CHECK STARTED !!!") # stdout for visibility
    logger.info(f"Starting migration check. Dialect: {engine.dialect.name}")
    
    try:
        # 1. Get current columns using Inspector (works for both)
        inspector = inspect(engine)
        existing_columns = [c['name'] for c in inspector.get_columns('users')]
        logger.info(f"Existing columns in 'users': {existing_columns}")
        print(f"Existing columns: {existing_columns}")

        # format: (column_name, sql_type_and_default)
        columns_to_check = [
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("is_superuser", "BOOLEAN DEFAULT FALSE"),
            ("is_authorized", "BOOLEAN DEFAULT FALSE"),
            ("is_system", "BOOLEAN DEFAULT FALSE")
        ]

        columns_to_add = []
        for col_name, col_def in columns_to_check:
            if col_name not in existing_columns:
                columns_to_add.append((col_name, col_def))

        if not columns_to_add:
            logger.info("No migrations needed. Columns exist.")
            print("No migrations needed.")
            return

        # 2. Apply Changes
        with engine.begin() as conn: # Transactional
            for col_name, col_type in columns_to_add:
                print(f"Migrating {col_name}...")
                logger.info(f"Adding column {col_name}...")
                
                # Try Postgres Syntax first (most likely for Render)
                try:
                    # Note: Postgres supports 'IF NOT EXISTS' in recent versions, but standard ADD works if we checked existence
                    # We use simple ADD COLUMN logic since we verified it's missing
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"Successfully added {col_name} (Standard SQL)")
                except Exception as e_pg:
                    logger.warning(f"Standard ADD COLUMN failed ({e_pg}). Trying SQLite syntax...")
                    # Fallback for SQLite (if 'FALSE' literals cause issues, though usually mapped)
                    # SQLite doesn't strictly have boolean, but SQLAlchemy handles it. 
                    # Raw SQL might need 0/1 for SQLite default
                    try:
                        sqlite_type = col_type.replace("FALSE", "0").replace("TRUE", "1")
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {sqlite_type}"))
                        logger.info(f"Successfully added {col_name} (SQLite fallback)")
                    except Exception as e_sqlite:
                        logger.error(f"Failed to add {col_name} with SQLite syntax: {e_sqlite}")
                        raise e_sqlite # Re-raise if both fail

        # 3. Verify
        inspector = inspect(engine)
        final_cols = [c['name'] for c in inspector.get_columns('users')]
        print(f"Final columns: {final_cols}")
        
    except Exception as e:
        logger.critical(f"Migration CRITICAL FAILURE: {e}")
        print(f"MIGRATION FAILED: {e}")
