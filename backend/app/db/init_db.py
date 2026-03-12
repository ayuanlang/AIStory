
import logging
import bcrypt
import os
import json
from datetime import datetime
from sqlalchemy import text, inspect
from app.db.session import engine, SessionLocal
from app.models.all_models import (
    APISetting,
    User,
    SystemAPISetting,
    ProviderKeyPool,
    SystemAPIBillingRule,
    TransactionAction,
    SMTPSystemConfig,
    WechatPayConfig,
    TaskDefaultSystemAPI,
)
from app.services.system_default_api_service import normalize_task_category
from app.core.time_utils import now_bj_iso

logger = logging.getLogger(__name__)


def _should_manage_api_settings_on_init() -> bool:
    """
    Whether init/deploy flow is allowed to mutate API settings data records.
    Default is OFF to protect existing website data; use import/export for changes.
    Enable only when explicitly needed for bootstrap/migration.
    """
    return str(os.getenv("AISTORY_MANAGE_API_SETTINGS_ON_INIT", "0")).strip().lower() in {"1", "true", "yes", "on"}

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
                    INSERT INTO users (username, email, hashed_password, is_active, account_status, email_verified, is_superuser, is_authorized, is_system)
                    VALUES (:username, :email, :password, :active, :account_status, :email_verified, :superuser, :authorized, :system)
                """)
                
                conn.execute(sql, {
                    "username": "ylsystem",
                    "email": "ylsystem@admin.com",
                    "password": hashed,
                    "active": True, # SQLAlchemy generic type handling should convert to 1/0 or TRUE/FALSE
                    "account_status": 1,
                    "email_verified": True,
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
        is_postgres = engine.dialect.name == 'postgresql'

        # Ensure dedicated system_api_settings table exists
        try:
            if not inspector.has_table("system_api_settings"):
                SystemAPISetting.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created system_api_settings table")
        except Exception as e:
            logger.error(f"Failed to ensure system_api_settings table: {e}")

        # Ensure provider_key_pool table exists
        try:
            if not inspector.has_table("provider_key_pool"):
                ProviderKeyPool.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created provider_key_pool table")
        except Exception as e:
            logger.error(f"Failed to ensure provider_key_pool table: {e}")

        # Ensure provider_key_pool.intro_url exists for supplier analysis context.
        try:
            inspector = inspect(engine)
            existing_pool_cols = {c['name'] for c in inspector.get_columns('provider_key_pool')} if inspector.has_table('provider_key_pool') else set()
            if 'intro_url' not in existing_pool_cols:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE provider_key_pool ADD COLUMN IF NOT EXISTS intro_url TEXT"))
                    else:
                        conn.execute(text("ALTER TABLE provider_key_pool ADD COLUMN intro_url TEXT"))
                logger.info("Ensured provider_key_pool.intro_url column")
        except Exception as e:
            logger.error(f"Failed to ensure provider_key_pool.intro_url column: {e}")

        # Ensure provider_key_pool.provider_alias exists for user-facing provider display names.
        try:
            inspector = inspect(engine)
            existing_pool_cols = {c['name'] for c in inspector.get_columns('provider_key_pool')} if inspector.has_table('provider_key_pool') else set()
            if 'provider_alias' not in existing_pool_cols:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE provider_key_pool ADD COLUMN IF NOT EXISTS provider_alias VARCHAR"))
                    else:
                        conn.execute(text("ALTER TABLE provider_key_pool ADD COLUMN provider_alias VARCHAR"))
                logger.info("Ensured provider_key_pool.provider_alias column")
        except Exception as e:
            logger.error(f"Failed to ensure provider_key_pool.provider_alias column: {e}")

        # Ensure dedicated default API mapping table exists.
        try:
            if not inspector.has_table("system_task_default_apis"):
                TaskDefaultSystemAPI.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created system_task_default_apis table")
        except Exception as e:
            logger.error(f"Failed to ensure system_task_default_apis table: {e}")

        # Ensure system_api_billing_rules table exists
        try:
            if not inspector.has_table("system_api_billing_rules"):
                SystemAPIBillingRule.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created system_api_billing_rules table")
        except Exception as e:
            logger.error(f"Failed to ensure system_api_billing_rules table: {e}")

        # Ensure dedicated smtp_system_configs table exists
        try:
            if not inspector.has_table("smtp_system_configs"):
                SMTPSystemConfig.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created smtp_system_configs table")
        except Exception as e:
            logger.error(f"Failed to ensure smtp_system_configs table: {e}")

        # Ensure dedicated wechat_pay_configs table exists
        try:
            if not inspector.has_table("wechat_pay_configs"):
                WechatPayConfig.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created wechat_pay_configs table")
        except Exception as e:
            logger.error(f"Failed to ensure wechat_pay_configs table: {e}")

        # Ensure legacy system_api_billing_rules schema can support charge multiplier.
        try:
            inspector = inspect(engine)
            existing_rule_cols = {c['name'] for c in inspector.get_columns('system_api_billing_rules')} if inspector.has_table('system_api_billing_rules') else set()
            with engine.begin() as conn:
                if 'charge_multiplier' not in existing_rule_cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE system_api_billing_rules ADD COLUMN IF NOT EXISTS charge_multiplier DOUBLE PRECISION DEFAULT 2.0"))
                    else:
                        conn.execute(text("ALTER TABLE system_api_billing_rules ADD COLUMN charge_multiplier FLOAT DEFAULT 2.0"))
                    logger.info("Ensured system_api_billing_rules.charge_multiplier column")
                try:
                    conn.execute(text("UPDATE system_api_billing_rules SET charge_multiplier = 2.0 WHERE charge_multiplier IS NULL OR charge_multiplier < 0"))
                except Exception as e:
                    logger.warning(f"Failed to backfill system_api_billing_rules.charge_multiplier: {e}")
        except Exception as e:
            logger.error(f"Failed to migrate system_api_billing_rules schema: {e}")

        # Ensure transaction_action table exists
        try:
            if not inspector.has_table("transaction_action"):
                TransactionAction.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created transaction_action table")
        except Exception as e:
            logger.error(f"Failed to ensure transaction_action table: {e}")

        # Cleanup legacy duplicate table: transaction_actions (plural).
        # Keep this guard conservative: only drop when table exists and is empty.
        try:
            inspector = inspect(engine)
            if inspector.has_table("transaction_actions"):
                with engine.begin() as conn:
                    count_result = conn.execute(text("SELECT COUNT(1) FROM transaction_actions"))
                    row_count = int((count_result.scalar() or 0))
                    if row_count == 0:
                        if is_postgres:
                            conn.execute(text("DROP TABLE IF EXISTS transaction_actions CASCADE"))
                        else:
                            conn.execute(text("DROP TABLE IF EXISTS transaction_actions"))
                        logger.info("Dropped legacy empty table transaction_actions")
                    else:
                        logger.warning(
                            "Skipped dropping transaction_actions because it is not empty (rows=%s)",
                            row_count,
                        )
        except Exception as e:
            logger.error(f"Failed to cleanup legacy table transaction_actions: {e}")

        # Ensure legacy system_api_settings schema is compatible with current model.
        # Render DB may have an older table shape missing columns like deprecated/config/is_active.
        try:
            inspector = inspect(engine)
            existing_system_cols = {c['name'] for c in inspector.get_columns('system_api_settings')}

            # Detect if modality is still VARCHAR and needs migration to JSON
            modality_col_info = None
            for col in inspector.get_columns('system_api_settings'):
                if col['name'] == 'modality':
                    modality_col_info = col
                    break
            need_modality_type_migration = False
            if modality_col_info:
                col_type_str = str(modality_col_info.get('type', '')).upper()
                if 'VARCHAR' in col_type_str or 'TEXT' in col_type_str or 'CHAR' in col_type_str:
                    need_modality_type_migration = True

            system_columns_to_check = [
                ("deprecated", "BOOLEAN DEFAULT FALSE"),
                ("config", "JSON"),
                ("is_active", "BOOLEAN DEFAULT FALSE"),
                ("base_model", "VARCHAR"),
                ("tags", "JSON"),
                ("supplier_info", "JSON"),
                # Wide modality columns (normalized fields)
                ("generation_modes", "JSON"),
                ("input_formats", "JSON"),
                ("output_format", "VARCHAR"),
                ("supported_resolutions", "JSON"),
                ("aspect_ratios", "JSON"),
                ("max_images_per_call", "INTEGER"),
                ("reference_image_limit", "VARCHAR"),
                ("reference_video_limit", "VARCHAR"),
                ("durations_seconds", "JSON"),
                ("max_duration", "INTEGER"),
                ("fps_options", "JSON"),
                ("has_audio", "BOOLEAN"),
                ("mode_values", "JSON"),
                # Category-specific capability objects
                ("text_capabilities", "JSON"),
                ("image_capabilities", "JSON"),
                ("video_capabilities", "JSON"),
                ("digital_human_capabilities", "JSON"),
                ("voice_capabilities", "JSON"),
                ("music_capabilities", "JSON"),
                # Billing hint columns
                ("pricing_unit", "VARCHAR"),
                ("token_billing_supported", "BOOLEAN"),
                ("input_token_price", "FLOAT"),
                ("output_token_price", "FLOAT"),
                ("per_resolution_price_map", "JSON"),
                ("per_duration_price_map", "JSON"),
                ("has_tiered_pricing", "BOOLEAN"),
                ("free_quota", "VARCHAR"),
                ("currency", "VARCHAR"),
            ]
            # Only add modality column if it doesn't exist yet (new installs)
            if 'modality' not in existing_system_cols:
                system_columns_to_check.append(("modality", "JSON"))

            with engine.begin() as conn:
                for col_name, col_type in system_columns_to_check:
                    try:
                        if is_postgres:
                            conn.execute(text(f"ALTER TABLE system_api_settings ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        elif col_name not in existing_system_cols:
                            conn.execute(text(f"ALTER TABLE system_api_settings ADD COLUMN {col_name} {col_type}"))
                    except Exception as e:
                        logger.error(f"Failed to ensure system_api_settings.{col_name}: {e}")

                # Migrate modality column from VARCHAR to JSON if needed
                if need_modality_type_migration:
                    try:
                        if is_postgres:
                            # Step 1: rename old column
                            conn.execute(text("ALTER TABLE system_api_settings RENAME COLUMN modality TO modality_legacy"))
                            # Step 2: add new JSON column
                            conn.execute(text("ALTER TABLE system_api_settings ADD COLUMN modality JSON"))
                            # Step 3: migrate data - convert old string values to JSON
                            conn.execute(text("""
                                UPDATE system_api_settings
                                SET modality = NULL
                                WHERE modality_legacy IS NULL OR TRIM(modality_legacy) = ''
                            """))
                            # For non-null values, we'll do a Python-based migration below
                            conn.execute(text("ALTER TABLE system_api_settings DROP COLUMN modality_legacy"))
                            logger.info("Migrated system_api_settings.modality from VARCHAR to JSON (PostgreSQL)")
                        else:
                            # SQLite: recreate approach via rename + new column
                            conn.execute(text("ALTER TABLE system_api_settings RENAME COLUMN modality TO modality_legacy"))
                            conn.execute(text("ALTER TABLE system_api_settings ADD COLUMN modality JSON"))
                            conn.execute(text("ALTER TABLE system_api_settings DROP COLUMN modality_legacy"))
                            logger.info("Migrated system_api_settings.modality from VARCHAR to JSON (SQLite)")
                    except Exception as e:
                        logger.error(f"Failed to migrate system_api_settings.modality to JSON: {e}")

                try:
                    conn.execute(text("UPDATE system_api_settings SET deprecated = FALSE WHERE deprecated IS NULL"))
                except Exception as e:
                    logger.warning(f"Failed to backfill system_api_settings.deprecated: {e}")

                try:
                    conn.execute(text("UPDATE system_api_settings SET is_active = FALSE WHERE is_active IS NULL"))
                except Exception as e:
                    logger.warning(f"Failed to backfill system_api_settings.is_active: {e}")

                try:
                    if is_postgres:
                        conn.execute(text("UPDATE system_api_settings SET config = '{}'::json WHERE config IS NULL"))
                    else:
                        conn.execute(text("UPDATE system_api_settings SET config = '{}' WHERE config IS NULL"))
                except Exception as e:
                    logger.warning(f"Failed to backfill system_api_settings.config: {e}")


                # Hard-drop deprecated legacy structures (no backward compatibility mode).
                try:
                    conn.execute(text("DROP TABLE IF EXISTS pricing_rules"))
                except Exception as e:
                    logger.warning(f"Failed to drop legacy table pricing_rules: {e}")

                for legacy_col in [
                    "billing_unit_type",
                    "billing_cost",
                    "billing_cost_input",
                    "billing_cost_output",
                    "has_granular_billing_rules",
                ]:
                    try:
                        if is_postgres:
                            conn.execute(text(f"ALTER TABLE system_api_settings DROP COLUMN IF EXISTS {legacy_col}"))
                        else:
                            conn.execute(text(f"ALTER TABLE system_api_settings DROP COLUMN {legacy_col}"))
                    except Exception as e:
                        logger.warning(f"Failed to drop legacy column system_api_settings.{legacy_col}: {e}")
        except Exception as e:
            logger.error(f"Failed to migrate system_api_settings schema: {e}")

        # --- Migrate legacy category defaults from system_api_settings.is_active ---
        try:
            with SessionLocal() as session:
                existing_default_count = session.query(TaskDefaultSystemAPI).count()
                if existing_default_count == 0:
                    active_rows = session.query(SystemAPISetting).filter(
                        SystemAPISetting.is_active == True,
                        ~SystemAPISetting.category.like("System_%"),
                    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.id.desc()).all()

                    seen_task_categories = set()
                    created = 0
                    for row in active_rows:
                        task_category = normalize_task_category(row.category)
                        if task_category in seen_task_categories:
                            continue
                        seen_task_categories.add(task_category)
                        now = now_bj_iso()
                        session.add(TaskDefaultSystemAPI(
                            task_category=task_category,
                            system_api_id=int(row.id),
                            created_at=now,
                            updated_at=now,
                        ))
                        created += 1
                    if created > 0:
                        session.commit()
                        logger.info("Migrated %s legacy system defaults into system_task_default_apis", created)
        except Exception as e:
            logger.error(f"Failed to migrate task default api mappings: {e}")

        # --- Migrate provider key pool data from config JSON to dedicated table ---
        try:
            with SessionLocal() as session:
                existing_pool_count = session.query(ProviderKeyPool).count()
                if existing_pool_count == 0:
                    # First run: extract key pool data from system_api_settings.config
                    all_rows = session.query(SystemAPISetting).order_by(SystemAPISetting.id.asc()).all()
                    provider_pools: dict = {}  # provider -> {keys, strategy, weights}
                    for row in all_rows:
                        cfg = row.config if isinstance(row.config, dict) else {}
                        provider_name = str(row.provider or "").strip().lower()
                        if not provider_name:
                            continue
                        raw_keys = cfg.get("provider_api_keys")
                        if not raw_keys:
                            continue
                        keys_list = raw_keys if isinstance(raw_keys, list) else [raw_keys]
                        keys_list = [str(k).strip() for k in keys_list if str(k).strip()]
                        if not keys_list:
                            continue
                        if provider_name not in provider_pools:
                            strategy = str(cfg.get("provider_api_key_strategy") or "random").strip().lower()
                            if strategy not in ("random", "round_robin", "weighted"):
                                strategy = "random"
                            raw_weights = cfg.get("provider_api_key_weights")
                            weights = raw_weights if isinstance(raw_weights, list) else []
                            provider_pools[provider_name] = {
                                "keys": list(dict.fromkeys(keys_list)),  # dedup preserving order
                                "strategy": strategy,
                                "weights": weights,
                            }
                        else:
                            existing = provider_pools[provider_name]["keys"]
                            seen = set(existing)
                            for k in keys_list:
                                if k not in seen:
                                    seen.add(k)
                                    existing.append(k)
                    migrated = 0
                    for prov, data in provider_pools.items():
                        session.add(ProviderKeyPool(
                            provider=prov,
                            api_keys=data["keys"],
                            strategy=data["strategy"],
                            weights=data["weights"],
                        ))
                        migrated += 1
                    if migrated:
                        session.commit()
                        logger.info("Migrated %s provider key pools from config JSON to provider_key_pool table", migrated)
        except Exception as e:
            logger.error(f"Failed to migrate provider key pool data: {e}")

        # --- Migrate legacy SMTP config from system_api_settings to smtp_system_configs ---
        try:
            with SessionLocal() as session:
                existing_smtp = session.query(SMTPSystemConfig).filter(SMTPSystemConfig.is_active == True).first()
                if not existing_smtp:
                    legacy_smtp = session.query(SystemAPISetting).filter(
                        SystemAPISetting.category == "System_Email",
                        SystemAPISetting.provider == "smtp",
                    ).order_by(SystemAPISetting.id.desc()).first()
                    if legacy_smtp:
                        cfg = legacy_smtp.config if isinstance(legacy_smtp.config, dict) else {}
                        session.add(SMTPSystemConfig(
                            host=str(cfg.get("host", "") or "").strip(),
                            port=int(cfg.get("port") or 587),
                            username=str(cfg.get("username", "") or "").strip(),
                            password=str(legacy_smtp.api_key or "").strip(),
                            use_ssl=bool(cfg.get("use_ssl", False)),
                            use_tls=bool(cfg.get("use_tls", True)),
                            from_email=str(cfg.get("from_email", "") or "").strip(),
                            frontend_base_url=str(cfg.get("frontend_base_url", "") or "").strip(),
                            is_active=True,
                            created_at=now_bj_iso(),
                            updated_at=now_bj_iso(),
                        ))
                        session.commit()
                        logger.info("Migrated legacy SMTP config into smtp_system_configs")
        except Exception as e:
            logger.error(f"Failed to migrate legacy SMTP config: {e}")

        # --- Migrate legacy WeChat config from system_api_settings to wechat_pay_configs ---
        try:
            with SessionLocal() as session:
                existing_wechat = session.query(WechatPayConfig).filter(WechatPayConfig.is_active == True).first()
                if not existing_wechat:
                    legacy_wechat = session.query(SystemAPISetting).filter(
                        SystemAPISetting.category == "System_Payment",
                        SystemAPISetting.provider == "wechat_pay",
                    ).order_by(SystemAPISetting.id.desc()).first()
                    if legacy_wechat:
                        cfg = legacy_wechat.config if isinstance(legacy_wechat.config, dict) else {}
                        session.add(WechatPayConfig(
                            mchid=str(cfg.get("mchid", "") or "").strip(),
                            appid=str(cfg.get("appid", "") or "").strip(),
                            api_v3_key=str(legacy_wechat.api_key or "").strip(),
                            cert_serial_no=str(cfg.get("cert_serial_no", "") or "").strip(),
                            private_key=str(cfg.get("private_key", "") or ""),
                            notify_url=str(cfg.get("notify_url", "") or "").strip(),
                            use_mock=bool(cfg.get("use_mock", True)),
                            is_active=True,
                            created_at=now_bj_iso(),
                            updated_at=now_bj_iso(),
                        ))
                        session.commit()
                        logger.info("Migrated legacy WeChat config into wechat_pay_configs")
        except Exception as e:
            logger.error(f"Failed to migrate legacy WeChat config: {e}")

        # --- Migrate legacy pricing source to system_api_billing_rules base rows ---
        try:
            with SessionLocal() as session:
                def _normalize_unit_type(raw):
                    text = str(raw or "per_call").strip() or "per_call"
                    allowed = {"per_call", "per_second", "per_minute", "per_token", "per_1k_tokens", "per_million_tokens"}
                    return text if text in allowed else "per_call"

                def _nni(value):
                    try:
                        parsed = int(float(value))
                        return parsed if parsed >= 0 else 0
                    except Exception:
                        return 0

                def _safe_json_dict(value):
                    if isinstance(value, dict):
                        return dict(value)
                    if isinstance(value, str):
                        raw = value.strip()
                        if not raw:
                            return {}
                        try:
                            parsed = json.loads(raw)
                            return parsed if isinstance(parsed, dict) else {}
                        except Exception:
                            return {}
                    return {}

                def _mode_flags(category):
                    normalized = str(category or "").strip().lower()
                    if normalized == "image":
                        return (False, True, False)
                    if normalized == "video":
                        return (False, False, True)
                    return (True, False, False)

                def _has_base_rule(system_api_id):
                    rules = session.query(SystemAPIBillingRule).filter(
                        SystemAPIBillingRule.system_api_id == system_api_id,
                    ).all()
                    for rule in rules:
                        extra = _safe_json_dict(getattr(rule, "extra_conditions", {}))
                        if str(extra.get("rule_kind", "")).strip().lower() == "base_pricing":
                            return True
                    return False

                rows = session.query(SystemAPISetting).filter(SystemAPISetting.category != "System_Payment").all()
                migrated = 0
                for row in rows:
                    if _has_base_rule(int(row.id)):
                        continue

                    cfg = _safe_json_dict(row.config)
                    ap = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
                    unit_type = _normalize_unit_type(ap.get("unit_type", cfg.get("billing_unit_type", "per_call")))
                    cost = _nni(ap.get("cost", cfg.get("billing_cost", 0)))
                    cost_input = _nni(ap.get("cost_input", cfg.get("billing_cost_input", 0)))
                    cost_output = _nni(ap.get("cost_output", cfg.get("billing_cost_output", 0)))
                    if cost <= 0 and cost_input <= 0 and cost_output <= 0:
                        continue

                    applies_to_text, applies_to_image, applies_to_video = _mode_flags(row.category)
                    now_iso = now_bj_iso()
                    session.add(SystemAPIBillingRule(
                        system_api_id=int(row.id),
                        name="Base Pricing",
                        description="Base pricing rule migrated from system_api_settings.",
                        is_active=True,
                        priority=-100000,
                        applies_to_text=applies_to_text,
                        applies_to_image=applies_to_image,
                        applies_to_video=applies_to_video,
                        billing_unit_type=unit_type,
                        billing_cost=cost,
                        billing_cost_input=cost_input,
                        billing_cost_output=cost_output,
                        charge_multiplier=2.0,
                        extra_conditions={"rule_kind": "base_pricing"},
                        created_at=now_iso,
                        updated_at=now_iso,
                    ))

                    if isinstance(cfg, dict):
                        for key in ("api_pricing", "billing_unit_type", "billing_cost", "billing_cost_input", "billing_cost_output"):
                            cfg.pop(key, None)
                        row.config = cfg

                    migrated += 1

                if migrated:
                    session.commit()
                    logger.info("Migrated %s system_api_settings pricing rows into base billing rules", migrated)
        except Exception as e:
            logger.error(f"Failed to migrate system_api pricing into base rules: {e}")

        # Migrate legacy system-owned rows from api_settings into system_api_settings (opt-in only).
        if _should_manage_api_settings_on_init():
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
        else:
            logger.info("Skip legacy API settings migration on init (AISTORY_MANAGE_API_SETTINGS_ON_INIT is disabled)")

        if is_postgres:
            # Robust Postgres Strategy
            user_columns_pg = [
                ("is_active", "BOOLEAN DEFAULT TRUE"),
                ("account_status", "INTEGER DEFAULT 1"),
                ("email_verified", "BOOLEAN DEFAULT FALSE"),
                ("email_verification_code", "VARCHAR"),
                ("email_verification_expires_at", "VARCHAR"),
                ("is_superuser", "BOOLEAN DEFAULT FALSE"),
                ("is_authorized", "BOOLEAN DEFAULT FALSE"),
                ("is_system", "BOOLEAN DEFAULT FALSE"),
                ("credits", "INTEGER DEFAULT 0"),
                ("avatar_url", "VARCHAR")
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
            ("account_status", "INTEGER DEFAULT 1"),
            ("email_verified", "BOOLEAN DEFAULT FALSE"),
            ("email_verification_code", "VARCHAR"),
            ("email_verification_expires_at", "VARCHAR"),
            ("is_superuser", "BOOLEAN DEFAULT FALSE"),
            ("is_authorized", "BOOLEAN DEFAULT FALSE"),
            ("is_system", "BOOLEAN DEFAULT FALSE"),
            ("credits", "INTEGER DEFAULT 0"),
            ("avatar_url", "VARCHAR")
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

        # --- MIGRATE ENTITIES TABLE ---
        try:
            inspector = inspect(engine)
            existing_entity_columns = [c['name'] for c in inspector.get_columns('entities')]
            if 'generation_prompt_cn' not in existing_entity_columns:
                with engine.begin() as conn:
                    if engine.dialect.name == 'postgresql':
                        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS generation_prompt_cn TEXT"))
                    else:
                        conn.execute(text("ALTER TABLE entities ADD COLUMN generation_prompt_cn TEXT"))
                logger.info("Ensured entities.generation_prompt_cn exists")
        except Exception as e:
            logger.error(f"Failed to migrate entities table: {e}")
        
    except Exception as e:
        logger.critical(f"Migration CRITICAL FAILURE: {e}")

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

    rows = db.query(APISetting).filter(APISetting.provider == "grsai").all()
    changed = 0
    for row in rows:
        row_name = (row.name or "").lower()
        row_category = (row.category or "").lower()

        if row_category in ("vision", "llm") and "sora" in row_name and (row.model or "") != "gemini-3-pro":
            row.model = "gemini-3-pro"
            changed += 1
            if row.category != "LLM":
                row.category = "LLM"
                changed += 1
        elif row_category == "video" and "video" in row_name and "sora" in row_name and (row.model or "") != "veo3.1-fast":
            row.model = "veo3.1-fast"
            changed += 1
        elif row_category == "image" and "dakka" in row_name and (row.model or "") != "nano-banana-fast":
            row.model = "nano-banana-fast"
            changed += 1

        current_base_url = (row.base_url or "").strip()
        normalized_base_url = current_base_url.replace("grsaiapi.com", "grsai.dakka.com.cn").rstrip("/")
        if normalized_base_url and not normalized_base_url.endswith("/chat/completions") and not normalized_base_url.endswith("/v1"):
            normalized_base_url = f"{normalized_base_url}/v1"
        if normalized_base_url and normalized_base_url != current_base_url:
            row.base_url = normalized_base_url
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

    grsai_base_url = "https://grsai.dakka.com.cn/v1"
    grsai_nano_banana_endpoint = "https://grsai.dakka.com.cn/v1/draw/nano-banana"
    grsai_gpt_image_endpoint = "https://grsai.dakka.com.cn/v1/draw/completions"
    grsai_sora2_endpoint = "https://grsai.dakka.com.cn/v1/video/sora-video"
    grsai_veo_endpoint = "https://grsai.dakka.com.cn/v1/video/veo"
    grsai_provider = "grsai"

    # Source list requested by user (from Grsai model catalog page).
    grsai_models = [
        {"category": "Image", "name": "sora-image", "model": "sora-image"},
        {"category": "Image", "name": "gpt-image-1.5", "model": "gpt-image-1.5"},
        {"category": "Image", "name": "nano-banana", "model": "nano-banana"},
        {"category": "Image", "name": "nano-banana-fast", "model": "nano-banana-fast"},
        {"category": "Image", "name": "nano-banana-pro", "model": "nano-banana-pro"},
        {"category": "Image", "name": "nano-banana-pro-vt", "model": "nano-banana-pro-vt"},
        {"category": "Image", "name": "nano-banana-pro-cl", "model": "nano-banana-pro-cl"},
        {"category": "Image", "name": "nano-banana-pro-vip", "model": "nano-banana-pro-vip"},
        {"category": "Image", "name": "nano-banana-pro-4k-vip", "model": "nano-banana-pro-4k-vip"},
        {"category": "Image", "name": "sora-create-character", "model": "sora-create-character"},
        {"category": "Image", "name": "sora-upload-character", "model": "sora-upload-character"},
        {"category": "Video", "name": "sora-2", "model": "sora-2"},
        {"category": "Video", "name": "veo3.1-fast", "model": "veo3.1-fast"},
        {"category": "Video", "name": "veo3.1-fast-1080p", "model": "veo3.1-fast-1080p"},
        {"category": "Video", "name": "veo3.1-fast-4k", "model": "veo3.1-fast-4k"},
        {"category": "Video", "name": "veo3.1-pro", "model": "veo3.1-pro"},
        {"category": "Video", "name": "veo3.1-pro-1080p", "model": "veo3.1-pro-1080p"},
        {"category": "Video", "name": "veo3.1-pro-4k", "model": "veo3.1-pro-4k"},
        {"category": "LLM", "name": "gemini-2.5-pro", "model": "gemini-2.5-pro"},
        {"category": "LLM", "name": "gemini-3-pro", "model": "gemini-3-pro"},
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

        current_base_url = (row.base_url or "").strip()
        normalized_base_url = current_base_url.replace("grsaiapi.com", "grsai.dakka.com.cn").rstrip("/")
        if normalized_base_url and not normalized_base_url.endswith("/chat/completions") and not normalized_base_url.endswith("/v1"):
            normalized_base_url = f"{normalized_base_url}/v1"
        if normalized_base_url and normalized_base_url != current_base_url:
            row.base_url = normalized_base_url
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
            modality=item.get("modality"),
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

    # Seed baseline KIE models for system-level configuration.
    kie_provider = "kie"
    kie_base_url = "https://api.kie.ai"

    def _kie_item(name: str, category: str, model: str, modality: str = None, tags: list = None) -> dict:
        from app.services.modality_utils import migrate_legacy_modality_string
        d = {
            "name": name,
            "category": category,
            "model": model,
        }
        if modality is not None:
            d["modality"] = migrate_legacy_modality_string(modality)
        if tags is not None:
            d["tags"] = tags
        return d

    kie_models = [
        _kie_item("Kie Seedream 4.5", "Image", "seedream/4.5-text-to-image", "text-to-image"),
        _kie_item("Kie Seedream 4.5 Edit", "Image", "seedream/4.5-edit", "image-to-image"),
        _kie_item("Kie Google Imagen4 Fast (Canonical)", "Image", "google/imagen4-fast", "text-to-image"),
        _kie_item("Kie Google Imagen4 Ultra (Canonical)", "Image", "google/imagen4-ultra", "text-to-image"),
        _kie_item("Kie Google Imagen4", "Image", "google/imagen4", "text-to-image"),
        _kie_item("Kie Google Nano Banana", "Image", "google/nano-banana", "text-to-image"),
        _kie_item("Kie Google Nano Banana Edit", "Image", "google/nano-banana-edit", "image-to-image"),
        _kie_item("Kie Google Nano Banana 2", "Image", "google/nanobanana2", "text-to-image"),
        _kie_item("Kie Google Pro Image-to-Image", "Image", "google/pro-image-to-image", "image-to-image"),
        _kie_item("Kie Grok Imagine T2I (Canonical)", "Image", "grok-imagine/text-to-image", "text-to-image"),
        _kie_item("Kie Grok Imagine I2I (Canonical)", "Image", "grok-imagine/image-to-image", "image-to-image"),
        _kie_item("Kie Grok Imagine Upscale (Canonical)", "Image", "grok-imagine/upscale", "image-to-image"),
        _kie_item("Kie Qwen T2I (Canonical)", "Image", "qwen/text-to-image", "text-to-image"),
        _kie_item("Kie Qwen I2I (Canonical)", "Image", "qwen/image-to-image", "image-to-image"),
        _kie_item("Kie Qwen Edit (Canonical)", "Image", "qwen/image-edit", "image-to-image"),
        _kie_item("Kie Flux2 Pro T2I (Canonical)", "Image", "flux-2/pro-text-to-image", "text-to-image"),
        _kie_item("Kie Flux2 Pro I2I (Canonical)", "Image", "flux-2/pro-image-to-image", "image-to-image"),
        _kie_item("Kie Flux2 Flex T2I (Canonical)", "Image", "flux-2/flex-text-to-image", "text-to-image"),
        _kie_item("Kie Flux2 Flex I2I (Canonical)", "Image", "flux-2/flex-image-to-image", "image-to-image"),
        _kie_item("Kie GPT Image 1.5 T2I", "Image", "gpt-image/1-5-text-to-image", "text-to-image"),
        _kie_item("Kie GPT Image 1.5 I2I", "Image", "gpt-image/1-5-image-to-image", "image-to-image"),
        _kie_item("Kie Topaz Image Upscale", "Image", "topaz/image-upscale", "image-to-image"),
        _kie_item("Kie Recraft Remove BG", "Image", "recraft/remove-background", "image-to-image"),
        _kie_item("Kie Recraft Crisp Upscale", "Image", "recraft/crisp-upscale", "image-to-image"),
        _kie_item("Kie Ideogram V3 Reframe", "Image", "ideogram/v3-reframe", "image-to-image"),
        _kie_item("Kie Ideogram Character", "Image", "ideogram/character", "text-to-image"),
        _kie_item("Kie Ideogram Character Edit", "Image", "ideogram/character-edit", "image-to-image"),
        _kie_item("Kie Ideogram Character Remix", "Image", "ideogram/character-remix", "image-to-image"),

        # z-image-v4.0 / z-image-v4.5 retired by KIE

        _kie_item("Kie Kling 3.0", "Video", "kling-3.0/video", "text-to-video,image-to-video"),
        _kie_item("Kie Kling 2.6 T2V", "Video", "kling-2.6/text-to-video", "text-to-video"),
        _kie_item("Kie Kling 2.6 I2V", "Video", "kling-2.6/image-to-video", "image-to-video"),
        _kie_item("Kie Kling 2.6 Motion Control", "Video", "kling-2.6/motion-control", "image-to-video"),
        _kie_item("Kie Kling 2.5 Turbo T2V Pro", "Video", "kling/v2-5-turbo-text-to-video-pro", "text-to-video"),
        _kie_item("Kie Kling 2.5 Turbo I2V Pro", "Video", "kling/v2-5-turbo-image-to-video-pro", "image-to-video"),
        _kie_item("Kie Kling V2.1 Pro", "Video", "kling/v2-1-pro", "text-to-video,image-to-video"),
        _kie_item("Kie Kling V2.1 Standard", "Video", "kling/v2-1-standard", "text-to-video,image-to-video"),
        _kie_item("Kie Kling V2.1 Master T2V", "Video", "kling/v2-1-master-text-to-video", "text-to-video"),
        _kie_item("Kie Kling V2.1 Master I2V", "Video", "kling/v2-1-master-image-to-video", "image-to-video"),
        _kie_item("Kie Bytedance V1 Pro T2V (Canonical)", "Video", "bytedance/v1-pro-text-to-video", "text-to-video"),
        _kie_item("Kie Bytedance V1 Pro I2V (Canonical)", "Video", "bytedance/v1-pro-image-to-video", "image-to-video"),
        _kie_item("Kie Bytedance V1 Pro Fast I2V (Canonical)", "Video", "bytedance/v1-pro-fast-image-to-video", "image-to-video"),
        _kie_item("Kie Bytedance V1 Lite T2V (Canonical)", "Video", "bytedance/v1-lite-text-to-video", "text-to-video"),
        _kie_item("Kie Bytedance V1 Lite I2V (Canonical)", "Video", "bytedance/v1-lite-image-to-video", "image-to-video"),
        _kie_item("Kie Hailuo Pro T2V (Canonical)", "Video", "hailuo/02-text-to-video-pro", "text-to-video"),
        _kie_item("Kie Hailuo Pro I2V (Canonical)", "Video", "hailuo/02-image-to-video-pro", "image-to-video"),
        _kie_item("Kie Hailuo Standard T2V (Canonical)", "Video", "hailuo/02-text-to-video-standard", "text-to-video"),
        _kie_item("Kie Hailuo Standard I2V (Canonical)", "Video", "hailuo/02-image-to-video-standard", "image-to-video"),
        _kie_item("Kie Hailuo 2.3 Pro I2V", "Video", "hailuo/2-3-image-to-video-pro", "image-to-video"),
        _kie_item("Kie Hailuo 2.3 Standard I2V", "Video", "hailuo/2-3-image-to-video-standard", "image-to-video"),
        _kie_item("Kie Wan 2.6 T2V (Canonical)", "Video", "wan/2-6-text-to-video", "text-to-video"),
        _kie_item("Kie Wan 2.6 I2V (Canonical)", "Video", "wan/2-6-image-to-video", "image-to-video"),
        _kie_item("Kie Wan 2.6 V2V (Canonical)", "Video", "wan/2-6-video-to-video", "video-to-video"),
        _kie_item("Kie Wan 2.2 A14B T2V Turbo", "Video", "wan/2-2-a14b-text-to-video-turbo", "text-to-video"),
        _kie_item("Kie Wan 2.2 A14B I2V Turbo", "Video", "wan/2-2-a14b-image-to-video-turbo", "image-to-video"),
        _kie_item("Kie Wan 2.2 A14B Speech2Video", "Video", "wan/2-2-a14b-speech-to-video-turbo", "speech-to-video"),
        _kie_item("Kie Wan Animate Move", "Video", "wan/2-2-animate-move", "image-to-video"),
        _kie_item("Kie Wan Animate Replace", "Video", "wan/2-2-animate-replace", "image-to-video"),
        _kie_item("Kie Wan 2.6 Flash I2V", "Video", "wan/2-6-flash-image-to-video", "image-to-video"),
        _kie_item("Kie Wan 2.6 Flash V2V", "Video", "wan/2-6-flash-video-to-video", "video-to-video"),
        _kie_item("Kie Sora2 T2V (Canonical)", "Video", "sora-2-text-to-video", "text-to-video"),
        _kie_item("Kie Sora2 I2V (Canonical)", "Video", "sora-2-image-to-video", "image-to-video"),
        _kie_item("Kie Sora2 Pro T2V (Canonical)", "Video", "sora-2-pro-text-to-video", "text-to-video"),
        _kie_item("Kie Sora2 Pro I2V (Canonical)", "Video", "sora-2-pro-image-to-video", "image-to-video"),
        _kie_item("Kie Sora2 Watermark Remover", "Video", "sora-watermark-remover", "video-to-video"),
        _kie_item("Kie Sora2 Pro Storyboard", "Video", "sora-2-pro-storyboard", "text-to-video,image-to-video"),
        _kie_item("Kie Sora2 Characters", "Video", "sora-2-characters", "text-to-video,image-to-video"),
        _kie_item("Kie Sora2 Characters Pro", "Video", "sora-2-characters-pro", "text-to-video,image-to-video"),
        _kie_item("Kie Grok Imagine T2V (Canonical)", "Video", "grok-imagine/text-to-video", "text-to-video"),
        _kie_item("Kie Grok Imagine I2V (Canonical)", "Video", "grok-imagine/image-to-video", "image-to-video"),
        _kie_item("Kie Topaz Video Upscale", "Video", "topaz/video-upscale", "video-to-video"),
        _kie_item("Kie Infinitalk From Audio", "Video", "infinitalk/from-audio", "audio-to-video"),


        # bare "elevenlabs" retired by KIE; use sub-models below
        _kie_item("Kie ElevenLabs Text to Dialogue v3", "Tools", "elevenlabs/text-to-dialogue-v3", "text-to-audio"),
        _kie_item("Kie ElevenLabs TTS Turbo 2.5", "Tools", "elevenlabs/text-to-speech-turbo-2-5", "text-to-audio"),
        _kie_item("Kie ElevenLabs TTS Multilingual v2", "Tools", "elevenlabs/text-to-speech-multilingual-v2", "text-to-audio"),
        _kie_item("Kie ElevenLabs Speech-to-Text", "Tools", "elevenlabs/speech-to-text", "audio-to-text"),
        _kie_item("Kie ElevenLabs Sound Effect v2", "Tools", "elevenlabs/sound-effect-v2", "text-to-audio"),
        _kie_item("Kie ElevenLabs Audio Isolation", "Tools", "elevenlabs/audio-isolation", "audio-to-audio"),
        
        _kie_item("Kie Suno", "Audio", "suno", "text-to-audio"),
        _kie_item("Kie Runway Gen3 Alpha", "Video", "runwayml/gen3a-turbo", "text-to-video"),
        _kie_item("Kie Runway Gen3 Alpha Image to Video", "Video", "runwayml/gen3a-turbo-image-to-video", "image-to-video"),
        _kie_item("Kie 4o Image", "Image", "gpt4o-image", "text-to-image,image-to-image"),
        _kie_item("Kie Flux Kontext", "Image", "flux/kontext", "text-to-image,image-to-image"),

        _kie_item("Kie Gemini 2.5 Flash", "LLM", "gemini-2.5-flash"),
        _kie_item("Kie Gemini 2.5 Pro", "LLM", "gemini-2.5-pro"),
        _kie_item("Kie Gemini 3 Pro", "LLM", "gemini-3-pro"),
        _kie_item("Kie GPT-5-2", "LLM", "gpt-5-2"),
        _kie_item("Kie Claude Sonnet 4.5", "LLM", "claude-sonnet-4-5"),
        _kie_item("Kie Claude Opus 4.5", "LLM", "claude-opus-4-5"),
    ]

    existing_kie_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == kie_provider
    ).all()

    kie_shared_api_key = ""
    for row in existing_kie_rows:
        if (row.api_key or "").strip():
            kie_shared_api_key = row.api_key.strip()
            break

    existing_kie_keys = {
        ((row.category or "").strip().lower(), (row.model or "").strip().lower())
        for row in existing_kie_rows
    }

    kie_added = 0
    for item in kie_models:
        key = (item["category"].strip().lower(), item["model"].strip().lower())
        if key in existing_kie_keys:
            continue

        db.add(SystemAPISetting(
            name=item["name"],
            category=item["category"],
            provider=kie_provider,
            api_key=kie_shared_api_key,
            base_url=kie_base_url,
            model=item["model"],
            modality=item.get("modality"),
            config={
                "endpoint": f"{kie_base_url}/api/v1/jobs/createTask",
                "query_endpoint": f"{kie_base_url}/api/v1/jobs/recordInfo",
                "credits_endpoint": f"{kie_base_url}/api/v1/user/credits",
                "credits_endpoint_v2": f"{kie_base_url}/api/v1/chat/credit",
            },
            is_active=False,
        ))
        existing_kie_keys.add(key)
        kie_added += 1

    if kie_added > 0:
        db.commit()
        logger.info("Seeded %s kie models into system_api_settings", kie_added)
    else:
        logger.info("System kie models already initialized")

    # Seed baseline Vidu models for system-level configuration.
    vidu_provider = "vidu"
    vidu_base_url = "https://api.vidu.studio/open/v1/creation/video"

    def _vidu_item(name: str, model: str, modality: str = None) -> dict:
        from app.services.modality_utils import migrate_legacy_modality_string
        item = {
            "name": name,
            "category": "Video",
            "model": model,
            "config": {
                "provider_api_key_strategy": "random",
            },
        }
        if modality is not None:
            item["modality"] = migrate_legacy_modality_string(modality)
        return item

    vidu_models = [
        _vidu_item("Vidu 2.0", "vidu2.0", "text-to-video,image-to-video"),
        _vidu_item("Vidu Q2 Pro", "viduq2-pro", "text-to-video,image-to-video"),
    ]

    existing_vidu_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == vidu_provider
    ).all()

    vidu_shared_api_key = ""
    for row in existing_vidu_rows:
        if (row.api_key or "").strip():
            vidu_shared_api_key = row.api_key.strip()
            break

    existing_vidu_keys = {
        ((row.category or "").strip().lower(), (row.model or "").strip().lower())
        for row in existing_vidu_rows
    }

    vidu_added = 0
    for item in vidu_models:
        key = (item["category"].strip().lower(), item["model"].strip().lower())
        if key in existing_vidu_keys:
            continue

        db.add(SystemAPISetting(
            name=item["name"],
            category=item["category"],
            provider=vidu_provider,
            api_key=vidu_shared_api_key,
            base_url=vidu_base_url,
            model=item["model"],
            modality=item.get("modality"),
            config=item.get("config") or {},
            is_active=False,
        ))
        existing_vidu_keys.add(key)
        vidu_added += 1

    if vidu_added > 0:
        db.commit()
        logger.info("Seeded %s vidu models into system_api_settings", vidu_added)
    else:
        logger.info("System vidu models already initialized")

    # Seed default Vidu granular billing rules for audio-on/off matching.
    try:
        vidu_rows = db.query(SystemAPISetting).filter(
            SystemAPISetting.provider == vidu_provider,
            SystemAPISetting.category == "Video",
        ).all()

        rules_added = 0
        for row in vidu_rows:
            existing_rule_names = {
                str(rule.name or "").strip().lower()
                for rule in db.query(SystemAPIBillingRule).filter(
                    SystemAPIBillingRule.system_api_id == int(row.id)
                ).all()
            }

            rule_specs = [
                {
                    "name": "Vidu Sound On",
                    "description": "Vidu pricing rule when generated video has audio.",
                    "has_audio": True,
                    "priority": 20,
                },
                {
                    "name": "Vidu Sound Off",
                    "description": "Vidu pricing rule when generated video has no audio.",
                    "has_audio": False,
                    "priority": 19,
                },
            ]

            now_iso = now_bj_iso()
            for spec in rule_specs:
                normalized_name = str(spec["name"]).strip().lower()
                if normalized_name in existing_rule_names:
                    continue

                db.add(SystemAPIBillingRule(
                    system_api_id=int(row.id),
                    name=str(spec["name"]),
                    description=str(spec["description"]),
                    is_active=True,
                    priority=int(spec["priority"]),
                    applies_to_text=False,
                    applies_to_image=False,
                    applies_to_video=True,
                    has_audio=bool(spec["has_audio"]),
                    billing_unit_type="per_second",
                    billing_cost=30,
                    billing_cost_input=0,
                    billing_cost_output=0,
                    charge_multiplier=2.0,
                    extra_conditions={"provider": "vidu"},
                    created_at=now_iso,
                    updated_at=now_iso,
                ))
                rules_added += 1

        if rules_added > 0:
            db.commit()
            logger.info("Seeded %s default vidu billing rules", rules_added)
    except Exception as e:
        logger.warning(f"Failed to seed default vidu billing rules: {e}")


def init_initial_data():
    db = SessionLocal()
    try:
        if _should_manage_api_settings_on_init():
            init_api_settings(db)
            cleanup_api_settings_active_conflicts(db)
            normalize_grsai_user_api_settings(db)
            init_system_api_settings(db)
        else:
            logger.info("Skipping system API init sync because MANAGE_API_SETTINGS_ON_INIT is disabled")
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

