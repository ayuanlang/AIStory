
import logging
import bcrypt
from sqlalchemy import text, inspect
from app.db.session import engine, SessionLocal
from app.models.all_models import PricingRule, APISetting, User, SystemAPISetting

logger = logging.getLogger(__name__)

def create_default_superuser():
    """Ensure default system user exists."""
    # logger.info("Checking default superuser...")
    try:
        with engine.begin() as conn:
            # Check if user exists
            result = conn.execute(text("SELECT id FROM users WHERE username = 'ylsystem'"))
            user = result.fetchone()
            
            if not user:
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
            # else:
                # logger.info("Default superuser 'ylsystem' already exists.")

    except Exception as e:
        logger.error(f"Failed to create default superuser: {e}")

def check_and_migrate_tables():
    # logger.info(f"Starting migration check. Dialect: {engine.dialect.name}")
    
    try:
        inspector = inspect(engine)

        # Ensure dedicated system_api_settings table exists
        try:
            if not inspector.has_table("system_api_settings"):
                SystemAPISetting.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created system_api_settings table")
        except Exception as e:
            logger.error(f"Failed to ensure system_api_settings table: {e}")

        # Migrate legacy system-owned rows from api_settings into system_api_settings.
        try:
            with SessionLocal() as session:
                system_count = session.query(SystemAPISetting).count()
                if system_count == 0:
                    legacy_rows = session.query(APISetting).join(User, APISetting.user_id == User.id).filter(
                        User.is_system == True,
                        APISetting.category != "System_Payment",
                    ).all()
                    for row in legacy_rows:
                        session.add(SystemAPISetting(
                            name=row.name,
                            category=row.category or "LLM",
                            provider=row.provider or "unknown",
                            api_key=row.api_key or "",
                            base_url=row.base_url,
                            model=row.model,
                            config=row.config or {},
                            is_active=bool(row.is_active),
                        ))
                    if legacy_rows:
                        session.commit()
                        logger.info("Migrated %s legacy system API rows into system_api_settings", len(legacy_rows))
        except Exception as e:
            logger.error(f"Failed migrating legacy system API settings: {e}")

        is_postgres = engine.dialect.name == 'postgresql'
        
        if is_postgres:
            # Robust Postgres Strategy
            user_columns_pg = [
                ("is_active", "BOOLEAN DEFAULT TRUE"),
                ("is_superuser", "BOOLEAN DEFAULT FALSE"),
                ("is_authorized", "BOOLEAN DEFAULT FALSE"),
                ("is_system", "BOOLEAN DEFAULT FALSE"),
                ("credits", "INTEGER DEFAULT 0")
            ]
            with engine.begin() as conn:
                 for col_name, col_type in user_columns_pg:
                     try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        # logger.info(f"Ensured users.{col_name} exists")
                     except Exception as e:
                        logger.error(f"Failed to ensure users.{col_name}: {e}")
        
        # Fallback / Original logic for non-postgres or extra checks
        # 1. Get current columns using Inspector (works for both)
        inspector = inspect(engine)
        existing_columns = [c['name'] for c in inspector.get_columns('users')]
        # logger.info(f"Existing columns in 'users': {existing_columns}")

        # format: (column_name, sql_type_and_default)
        columns_to_check = [
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("is_superuser", "BOOLEAN DEFAULT FALSE"),
            ("is_authorized", "BOOLEAN DEFAULT FALSE"),
            ("is_system", "BOOLEAN DEFAULT FALSE"),
            ("credits", "INTEGER DEFAULT 0")
        ]

        columns_to_add = []
        for col_name, col_def in columns_to_check:
            if col_name not in existing_columns:
                columns_to_add.append((col_name, col_def))

        if not columns_to_add:
            pass
            # logger.info("No user-table migrations needed. Columns exist.")

        if columns_to_add:
            # 2. Apply Changes
            with engine.begin() as conn: # Transactional
                for col_name, col_type in columns_to_add:
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

        # --- Episodes table migrations ---
        try:
            inspector = inspect(engine)
            existing_episode_columns = [c['name'] for c in inspector.get_columns('episodes')]
            episode_columns_to_check = [
                ("ai_scene_analysis_result", "TEXT"),
                ("character_profiles", "JSON")
            ]

            missing_episode_cols = [(n, t) for (n, t) in episode_columns_to_check if n not in existing_episode_columns]
            if missing_episode_cols:
                with engine.begin() as conn:
                    for col_name, col_type in missing_episode_cols:
                        try:
                            # Postgres: IF NOT EXISTS is safe; SQLite will fail and we fallback.
                            if engine.dialect.name == 'postgresql':
                                conn.execute(text(f"ALTER TABLE episodes ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                            else:
                                conn.execute(text(f"ALTER TABLE episodes ADD COLUMN {col_name} {col_type}"))
                            logger.info(f"Ensured episodes.{col_name} exists")
                        except Exception as e1:
                            # SQLite fallback (no IF NOT EXISTS)
                            if engine.dialect.name != 'postgresql':
                                logger.error(f"Failed to add episodes.{col_name}: {e1}")
                                raise
                            logger.error(f"Failed to add episodes.{col_name}: {e1}")
                            raise
        except Exception as e:
            logger.error(f"Episodes table migration failed: {e}")
            # Do not crash startup; but keep visibility
            # raise

        # 3. Verify Users
        inspector = inspect(engine)
        final_cols = [c['name'] for c in inspector.get_columns('users')]

        # --- MIGRATE SHOTS TABLE ---
        # logger.info("Checking 'shots' table for missing columns...")
        
        # Robust Strategy for Postgres (Render)
        if engine.dialect.name == 'postgresql':
            logger.info("Detected Postgres dialect. Running idempotent migrations.")
            shot_columns_pg = [
                ("keyframes", "TEXT"),
                ("associated_entities", "TEXT"),
                ("shot_logic_cn", "TEXT"),
                ("scene_code", "VARCHAR"),
                ("technical_notes", "TEXT"),
                ("image_url", "TEXT"), 
                ("video_url", "TEXT"),
                ("prompt", "TEXT")
            ]
            
            with engine.begin() as conn:
                for col_name, col_type in shot_columns_pg:
                    try:
                        # 'IF NOT EXISTS' handles the check atomically in the DB
                        conn.execute(text(f"ALTER TABLE shots ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        logger.info(f"Ensured shots.{col_name} exists (Postgres atomic check)")
                    except Exception as pg_err:
                        # Log but continue - often means column exists or slight syntax diff on older PG
                        logger.warning(f"Postgres atomic ADD check for {col_name} returned: {pg_err}")
        
        else:
            # Inspection-based Strategy for SQLite/Other
            existing_shot_columns = [c['name'] for c in inspector.get_columns('shots')]

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
                        logger.info(f"Adding column shots.{col_name}...")
                        try:
                            conn.execute(text(f"ALTER TABLE shots ADD COLUMN {col_name} {col_type}"))
                            logger.info(f"Successfully added shots.{col_name}")
                        except Exception as e:
                            logger.error(f"Failed to add shots.{col_name}: {e}")
                            # Don't re-raise immediately so we can try others? No, DB might be in bad state.
                        
        final_shot_cols = [c['name'] for c in inspector.get_columns('shots')]
        
        # --- MIGRATE SCENES TABLE ---
        try:
             inspector = inspect(engine)
             existing_scene_columns = [c['name'] for c in inspector.get_columns('scenes')]
             
             if 'ai_shots_result' not in existing_scene_columns:
                 logger.info("Adding ai_shots_result to scenes table...")
                 with engine.begin() as conn:
                     # Use TEXT for general compatibility (SQLite/Postgres)
                     # For Postgres, we can make it TEXT or JSONB if we wanted, but TEXT is safe
                     # If existing table is Postgres, ALTER TABLE ADD COLUMN ... TEXT works fine
                     conn.execute(text("ALTER TABLE scenes ADD COLUMN ai_shots_result TEXT"))
                     logger.info("Successfully added scenes.ai_shots_result")

        except Exception as e:
             logger.error(f"Failed to migrate scenes table: {e}")
        
    except Exception as e:
        logger.critical(f"Migration CRITICAL FAILURE: {e}")

def init_pricing_rules(db):
    # 1. Ensure Generic Fallback Rules Exist (Provider=None, Model=None)
    # These are critical to prevent "No pricing rule found" errors when usage doesn't match specific providers.
    generic_defaults = [
        {"task_type": "image_gen", "cost": 10, "unit_type": "per_call", "description": "Default Image Gen Cost"},
        {"task_type": "video_gen", "cost": 50, "unit_type": "per_call", "description": "Default Video Gen Cost"},
        {"task_type": "llm_chat", "cost": 1, "unit_type": "per_call", "description": "Default LLM Chat Cost"},
        {"task_type": "analysis", "cost": 1, "unit_type": "per_call", "description": "Default Analysis Cost"},
    ]

    for rule_def in generic_defaults:
        exists = db.query(PricingRule).filter(
            PricingRule.task_type == rule_def["task_type"],
            PricingRule.provider == None,
            PricingRule.model == None
        ).first()
        
        if not exists:
            logger.info(f"Adding missing generic pricing rule for {rule_def['task_type']}")
            new_rule = PricingRule(
                task_type=rule_def["task_type"],
                provider=None,
                model=None,
                cost=rule_def["cost"],
                unit_type=rule_def["unit_type"],
                description=rule_def["description"],
                ref_markup=1.0,
                ref_exchange_rate=1.0,
                is_active=True
            )
            db.add(new_rule)
    
    db.commit()

    # 2. Add sample specific rules ONLY if table was completely empty (legacy behavior preservation)
    # We check if there are any PROVIDER-specific rules to determine "fresh install" vs "update"
    has_specific_rules = db.query(PricingRule).filter(PricingRule.provider != None).first()
    
    if has_specific_rules:
        return

    logger.info("Initializing default specific pricing rules...")
    
    rules = [
        PricingRule(
            provider='doubao', model='doubao-pro-32k', task_type='llm_chat',        
            cost=1, cost_input=200, cost_output=250,
            unit_type='per_million_tokens',
            ref_markup=1.5, ref_exchange_rate=10.0,
            description='None'
        ),
        PricingRule(
            provider='Grsai-Video', model='veo3.1-fast', task_type='video_gen',     
            cost=100, cost_input=0, cost_output=0,
            unit_type='per_call',
            ref_markup=1.5, ref_exchange_rate=10.0,
            description='Auto-synced from Grsai Video (Sora)'
        ),
        PricingRule(
            provider='Grsai-Image', model='nano-banana-fast', task_type='image_gen',
            cost=10, cost_input=0, cost_output=0,
            unit_type='per_call',
            ref_markup=1.5, ref_exchange_rate=10.0,
            description='Auto-synced from Grsai (Dakka)'
        ),
        PricingRule(
            provider='baidu_translate', model='None', task_type='llm_chat',
            cost=1, cost_input=0, cost_output=0,
            unit_type='per_call',
            ref_markup=1.5, ref_exchange_rate=10.0,
            description='Auto-synced from baidu_translate'
        ),
        PricingRule(
            provider='doubao', model='glm-4-7-251222', task_type='llm_chat',        
            cost=1, cost_input=200, cost_output=200,
            unit_type='per_call',
            ref_markup=1.5, ref_exchange_rate=10.0,
            description='Auto-synced from doubao'
        ),
        PricingRule(
            provider='grsai', model='gemini-3-pro', task_type='llm_chat',
            cost=1, cost_input=200, cost_output=1200,
            unit_type='per_million_tokens',
            ref_markup=1.5, ref_exchange_rate=10.0,
            description='Auto-synced from Grsai (Sora)'
        ),
    ]
    
    for r in rules:
        db.add(r)
    db.commit()
    logger.info("Default specific pricing rules created.")

def init_api_settings(db):
    # Check if system user has settings
    system_user = db.query(User).filter(User.username == "ylsystem").first()
    if not system_user:
        logger.warning("System user not found, skipping api settings init.")
        return

    if db.query(APISetting).filter(APISetting.user_id == system_user.id).first():
        return

    logger.info("Initializing default API settings for system user...")
    
    # Defaults
    settings_list = [
        APISetting(
            user_id=system_user.id,
            name="System OpenAI",
            category="LLM",
            provider="openai",
            model="gpt-4o",
            api_key="sk-CHANGE_ME",
            is_active=True
        ),
        APISetting(
            user_id=system_user.id,
            name="System Midjourney",
            category="Image",
            provider="midjourney",
            api_key="CHANGE_ME",
            base_url="https://api.midjourney.com",
            is_active=True
        ),
        APISetting(
            user_id=system_user.id,
            name="Runway Gen3",
            category="Video",
            provider="runway",
            api_key="CHANGE_ME",
            is_active=True
        ),
        APISetting(
            user_id=system_user.id,
            name="Doubao System",
            category="LLM",
            provider="doubao",
            api_key="CHANGE_ME",
            is_active=True
        ),
        APISetting(
            user_id=system_user.id,
            name="Grsai System",
            category="LLM",
            provider="grsai",
            api_key="CHANGE_ME",
            is_active=True
        ),
        APISetting(
            user_id=system_user.id,
            name="Baidu Translate",
            category="LLM",
            provider="baidu_translate",
            api_key="CHANGE_ME",
            is_active=True
        )
    ]
    
    for s in settings_list:
        db.add(s)
    db.commit()
    logger.info("Default API settings created.")


def cleanup_api_settings_active_conflicts(db):
    """
    Ensure only one active API setting per (user_id, category).
    Keeps the newest active row (highest id), deactivates older duplicates.
    Safe to run repeatedly.
    """
    active_rows = db.query(APISetting).filter(APISetting.is_active == True).order_by(
        APISetting.user_id.asc(),
        APISetting.category.asc(),
        APISetting.id.desc(),
    ).all()

    seen = set()
    changed = 0

    for row in active_rows:
        key = (row.user_id, row.category or "LLM")
        if key in seen:
            row.is_active = False
            changed += 1
        else:
            seen.add(key)

    if changed > 0:
        db.commit()
        logger.info(f"API settings cleanup: deactivated {changed} duplicate active rows.")
    else:
        logger.info("API settings cleanup: no duplicate active rows found.")


def normalize_grsai_user_api_settings(db):
    """Normalize legacy grsai rows in user-scoped api_settings."""

    def _normalize_model(model_value: str) -> str:
        value = (model_value or "").strip()
        if not value:
            return value
        prefixes = ("grsai/", "grsai-", "grsai_", "grsai ")
        normalized = value
        while True:
            lowered = normalized.lower()
            matched = False
            for prefix in prefixes:
                if lowered.startswith(prefix):
                    normalized = normalized[len(prefix):].strip(" /_-")
                    matched = True
                    break
            if not matched:
                break

        alias_map = {
            "nano-banana-fast": "gemini-2.5-flash-image",
            "veo3.1-fast": "veo_3_1_t2v_fast_ultra",
            "gemini-3-pro": "gemini-3-pro-preview",
        }
        return alias_map.get(normalized.lower(), normalized)

    rows = db.query(APISetting).filter(APISetting.provider == "grsai").all()
    changed = 0
    for row in rows:
        row_name = (row.name or "").lower()
        row_category = (row.category or "").lower()

        new_model = _normalize_model(row.model or "")
        if (row.model or "") != new_model:
            row.model = new_model
            changed += 1

        if row_category in ("vision", "llm") and "sora" in row_name and (row.model or "") != "gemini-3-pro-preview":
            row.model = "gemini-3-pro-preview"
            changed += 1
            if row.category != "LLM":
                row.category = "LLM"
                changed += 1
        elif row_category == "video" and "video" in row_name and "sora" in row_name and (row.model or "") != "veo_3_1_t2v_fast_ultra":
            row.model = "veo_3_1_t2v_fast_ultra"
            changed += 1
        elif row_category == "image" and "dakka" in row_name and (row.model or "") != "gemini-2.5-flash-image":
            row.model = "gemini-2.5-flash-image"
            changed += 1

    if changed > 0:
        db.commit()
        logger.info("Normalized %s legacy grsai api_settings rows", changed)


def init_system_api_settings(db):
    """Seed dedicated System API settings (independent from user APISetting rows)."""
    def _normalize_grsai_model_name(model_value: str) -> str:
        value = (model_value or "").strip()
        if not value:
            return value
        prefixes = ("grsai/", "grsai-", "grsai_", "grsai ")
        normalized = value
        while True:
            lowered = normalized.lower()
            matched = False
            for prefix in prefixes:
                if lowered.startswith(prefix):
                    normalized = normalized[len(prefix):].strip(" /_-")
                    matched = True
                    break
            if not matched:
                break
        return normalized

    def _legacy_model_alias(model_value: str) -> str:
        value = (model_value or "").strip().lower()
        alias_map = {
            "nano-banana-fast": "gemini-2.5-flash-image",
            "veo3.1-fast": "veo_3_1_t2v_fast_ultra",
            "gemini-3-pro": "gemini-3-pro-preview",
        }
        return alias_map.get(value, (model_value or "").strip())

    grsai_base_url = "https://grsaiapi.com"
    grsai_nano_banana_endpoint = "https://grsai.dakka.com.cn/v1/draw/nano-banana"
    grsai_gpt_image_endpoint = "https://grsai.dakka.com.cn/v1/draw/completions"
    grsai_sora2_endpoint = "https://grsai.dakka.com.cn/v1/video/sora-video"
    grsai_veo_endpoint = "https://grsai.dakka.com.cn/v1/video/veo"
    grsai_provider = "grsai"

    # Source list requested by user (from Grsai model catalog page).
    grsai_models = [
        {"category": "Image", "name": "sora-image", "model": "sora-image"},
        {"category": "Image", "name": "gpt-image-1.5", "model": "gpt-image-1.5"},
        {"category": "Image", "name": "nano-banana", "model": "gemini-2.5-flash-image"},
        {"category": "Image", "name": "nano-banana-fast", "model": "gemini-2.5-flash-image"},
        {"category": "Image", "name": "nano-banana-pro", "model": "gemini-3-pro-image-preview"},
        {"category": "Image", "name": "nano-banana-pro-vt", "model": "gemini-3-pro-image-preview"},
        {"category": "Image", "name": "nano-banana-pro-cl", "model": "gemini-3-pro-image-preview"},
        {"category": "Image", "name": "nano-banana-pro-vip", "model": "gemini-3-pro-image-preview"},
        {"category": "Image", "name": "nano-banana-pro-4k-vip", "model": "gemini-3-pro-image-preview"},
        {"category": "Image", "name": "sora-create-character", "model": "sora-create-character"},
        {"category": "Image", "name": "sora-upload-character", "model": "sora-upload-character"},
        {"category": "Video", "name": "sora-2", "model": "sora-2"},
        {"category": "Video", "name": "veo3.1-fast", "model": "veo_3_1_t2v_fast_ultra"},
        {"category": "Video", "name": "veo3.1-fast-1080p", "model": "veo_3_1_t2v_fast_ultra"},
        {"category": "Video", "name": "veo3.1-fast-4k", "model": "veo_3_1_t2v_fast_ultra"},
        {"category": "Video", "name": "veo3.1-pro", "model": "veo_3_1_t2v"},
        {"category": "Video", "name": "veo3.1-pro-1080p", "model": "veo_3_1_t2v"},
        {"category": "Video", "name": "veo3.1-pro-4k", "model": "veo_3_1_t2v"},
        {"category": "LLM", "name": "gemini-2.5-pro", "model": "gemini-2.5-pro"},
        {"category": "LLM", "name": "gemini-3-pro", "model": "gemini-3-pro-preview"},
    ]
    canonical_by_name = {
        item["name"].strip().lower(): {
            "category": item["category"],
            "model": item["model"],
        }
        for item in grsai_models
    }

    existing_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == grsai_provider
    ).all()

    updated_existing = 0
    for row in existing_rows:
        row_name = (row.name or "").lower()
        normalized_model = _normalize_grsai_model_name(row.model or "")
        normalized_model = _legacy_model_alias(normalized_model)
        if normalized_model != (row.model or ""):
            row.model = normalized_model
            updated_existing += 1
        row_model = (row.model or "").lower()
        row_category = (row.category or "").lower()
        cfg = dict(row.config or {})

        canonical_name_key = row_name.replace("grsai ", "", 1).strip() if row_name.startswith("grsai ") else row_name.strip()
        canonical = canonical_by_name.get(canonical_name_key)
        if not canonical:
            if row_category == "image" and "dakka" in row_name:
                canonical = canonical_by_name.get("nano-banana-fast")
            elif row_category == "video" and "video" in row_name and "sora" in row_name:
                canonical = canonical_by_name.get("veo3.1-fast")
            elif row_category in ("llm", "vision") and "sora" in row_name:
                canonical = canonical_by_name.get("gemini-3-pro")
        if canonical:
            desired_category = canonical["category"]
            desired_model = canonical["model"]
            if (row.category or "") != desired_category:
                row.category = desired_category
                row_category = desired_category.lower()
                updated_existing += 1
            if (row.model or "") != desired_model:
                row.model = desired_model
                row_model = desired_model.lower()
                updated_existing += 1

        expected_endpoint = None
        if row_category == "image" and "nano-banana" in row_name:
            expected_endpoint = grsai_nano_banana_endpoint
        elif row_category == "image" and (
            "gpt-image" in row_name
            or "gpt-image" in row_model
            or "gpt image" in row_name
        ):
            expected_endpoint = grsai_gpt_image_endpoint
        elif row_category == "video" and (
            "sora-2" in row_name
            or "sora-2" in row_model
            or "sora 2" in row_name
            or "sora_video" in row_model
            or "sora-video" in row_model
        ):
            expected_endpoint = grsai_sora2_endpoint
        elif row_category == "video" and ("veo" in row_name or "veo" in row_model):
            expected_endpoint = grsai_veo_endpoint

        if expected_endpoint and cfg.get("endpoint") != expected_endpoint:
            cfg["endpoint"] = expected_endpoint
            row.config = cfg
            updated_existing += 1

    if updated_existing > 0:
        db.commit()
        logger.info("Updated %s existing grsai system settings", updated_existing)

    existing_keys = {
        ((row.category or "").strip().lower(), (row.name or "").replace("Grsai ", "", 1).strip().lower())
        for row in existing_rows
    }

    shared_api_key = ""
    for row in existing_rows:
        if (row.api_key or "").strip():
            shared_api_key = row.api_key.strip()
            break

    added = 0
    for item in grsai_models:
        key = (item["category"].strip().lower(), item["name"].strip().lower())
        if key in existing_keys:
            continue

        db.add(SystemAPISetting(
            name=f"Grsai {item['name']}",
            category=item["category"],
            provider=grsai_provider,
            api_key=shared_api_key,
            base_url=grsai_base_url,
            model=item["model"],
            config={
                "endpoint": grsai_nano_banana_endpoint
            } if item["category"] == "Image" and "nano-banana" in item["name"] else ({
                "endpoint": grsai_gpt_image_endpoint
            } if item["category"] == "Image" and "gpt-image" in item["name"] else ({
                "endpoint": grsai_sora2_endpoint
            } if item["category"] == "Video" and "sora-2" in item["name"] else ({
                "endpoint": grsai_veo_endpoint
            } if item["category"] == "Video" and "veo" in item["name"] else {}))),
            is_active=False,
        ))
        existing_keys.add(key)
        added += 1

    if added > 0:
        db.commit()
        logger.info("Seeded %s grsai models into system_api_settings", added)
    else:
        logger.info("System grsai models already initialized")

def init_initial_data():
    db = SessionLocal()
    try:
        init_pricing_rules(db)
        init_api_settings(db)
        cleanup_api_settings_active_conflicts(db)
        normalize_grsai_user_api_settings(db)
        init_system_api_settings(db)
    except Exception as e:
        logger.error(f"Failed to initialize data: {e}")
    finally:
        db.close()


def init_db():
    """Convenience entrypoint used by scripts/ops.

    Runs schema checks/migrations and seeds required initial data.
    Safe to call multiple times.
    """
    check_and_migrate_tables()
    create_default_superuser()
    init_initial_data()
