
import logging
import bcrypt
from sqlalchemy import text, inspect
from app.db.session import engine

logger = logging.getLogger(__name__)

def create_default_superuser():
    """Ensure default system user exists."""
    print("!!! CHECKING DEFAULT SUPERUSER !!!")
    try:
        with engine.begin() as conn:
            # Check if user exists
            result = conn.execute(text("SELECT id FROM users WHERE username = 'ylsystem'"))
            user = result.fetchone()
            
            if not user:
                print("Creating default superuser: ylsystem")
                logger.info("Creating default superuser 'ylsystem'...")
                
                # Hash password using bcrypt
                password = "ylsystem"
                hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                # Insert
                # PostgreSQL and SQLite compatible parameter binding for raw SQL varies (%(name)s vs :name)
                # We'll use text() with params which usually handles it via SQLAlchemy
                sql = text("""
                    INSERT INTO users (username, email, hashed_password, is_active, is_superuser, is_authorized, is_system)
                    VALUES (:username, :email, :password, :active, :superuser, :authorized, :system)
                """)
                
                conn.execute(sql, {
                    "username": "ylsystem",
                    "email": "ylsystem@admin.com",
                    "password": hashed,
                    "active": True, # SQLAlchemy generic type handling should convert to 1/0 or TRUE/FALSE
                    "superuser": True,
                    "authorized": True,
                    "system": True
                })
                logger.info("Default superuser created.")
                print("Default superuser 'ylsystem' created.")
            else:
                logger.info("Default superuser 'ylsystem' already exists.")
                print("Default superuser exists.")

    except Exception as e:
        logger.error(f"Failed to create default superuser: {e}")
        print(f"SUPERUSER CREATION FAILED: {e}")

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

        # 3. Verify Users
        inspector = inspect(engine)
        final_cols = [c['name'] for c in inspector.get_columns('users')]
        print(f"Final users columns: {final_cols}")

        # --- MIGRATE SHOTS TABLE ---
        logger.info("Checking 'shots' table for missing columns...")
        existing_shot_columns = [c['name'] for c in inspector.get_columns('shots')]
        print(f"Existing columns in 'shots': {existing_shot_columns}")

        # format: (column_name, sql_type_and_default)
        shot_columns_to_check = [
            ("keyframes", "TEXT"),
            ("associated_entities", "TEXT"),
            ("shot_logic_cn", "TEXT"),
            ("scene_code", "VARCHAR") 
        ]

        shot_columns_to_add = []
        for col_name, col_def in shot_columns_to_check:
            if col_name not in existing_shot_columns:
                shot_columns_to_add.append((col_name, col_def))
        
        if shot_columns_to_add:
            with engine.begin() as conn:
                for col_name, col_type in shot_columns_to_add:
                    print(f"Migrating shots.{col_name}...")
                    logger.info(f"Adding column shots.{col_name}...")
                    try:
                        conn.execute(text(f"ALTER TABLE shots ADD COLUMN {col_name} {col_type}"))
                        logger.info(f"Successfully added shots.{col_name}")
                    except Exception as e:
                        logger.error(f"Failed to add shots.{col_name}: {e}")
                        # Don't re-raise immediately so we can try others? No, DB might be in bad state.
                        
        final_shot_cols = [c['name'] for c in inspector.get_columns('shots')]
        print(f"Final shots columns: {final_shot_cols}")
        
    except Exception as e:
        logger.critical(f"Migration CRITICAL FAILURE: {e}")
        print(f"MIGRATION FAILED: {e}")
