import os
import sys

from sqlalchemy import create_engine, inspect, text

# Make backend/app importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

from app.core.config import settings  # noqa: E402


def migrate() -> None:
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1 and str(sys.argv[1]).strip():
        db_url = str(sys.argv[1]).strip()

    print(f"[migrate] connecting: {db_url}")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    is_postgres = engine.dialect.name == "postgresql"

    with engine.begin() as conn:
        # 1) system_api_settings new flag
        cols = {c["name"] for c in inspector.get_columns("system_api_settings")}
        if "has_granular_billing_rules" not in cols:
            if is_postgres:
                conn.execute(text("ALTER TABLE system_api_settings ADD COLUMN IF NOT EXISTS has_granular_billing_rules BOOLEAN DEFAULT FALSE"))
            else:
                conn.execute(text("ALTER TABLE system_api_settings ADD COLUMN has_granular_billing_rules BOOLEAN DEFAULT FALSE"))
            print("[migrate] added system_api_settings.has_granular_billing_rules")
        conn.execute(text("UPDATE system_api_settings SET has_granular_billing_rules = FALSE WHERE has_granular_billing_rules IS NULL"))

        # 2) system_api_billing_rules (wide rule table)
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS system_api_billing_rules (
                id INTEGER PRIMARY KEY,
                system_api_id INTEGER NOT NULL,
                name VARCHAR DEFAULT 'Rule',
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                priority INTEGER DEFAULT 0,
                applies_to_text BOOLEAN DEFAULT FALSE,
                applies_to_image BOOLEAN DEFAULT FALSE,
                applies_to_video BOOLEAN DEFAULT FALSE,
                generation_mode VARCHAR,
                input_format VARCHAR,
                output_format VARCHAR,
                has_audio BOOLEAN,
                input_tokens_min INTEGER,
                input_tokens_max INTEGER,
                output_tokens_min INTEGER,
                output_tokens_max INTEGER,
                total_tokens_min INTEGER,
                total_tokens_max INTEGER,
                image_count_min INTEGER,
                image_count_max INTEGER,
                width_min INTEGER,
                width_max INTEGER,
                height_min INTEGER,
                height_max INTEGER,
                pixels_min INTEGER,
                pixels_max INTEGER,
                duration_seconds_min FLOAT,
                duration_seconds_max FLOAT,
                fps_min FLOAT,
                fps_max FLOAT,
                billing_unit_type VARCHAR DEFAULT 'per_call',
                billing_cost INTEGER DEFAULT 0,
                billing_cost_input INTEGER DEFAULT 0,
                billing_cost_output INTEGER DEFAULT 0,
                charge_multiplier FLOAT DEFAULT 2.0,
                extra_conditions JSON,
                created_at VARCHAR,
                updated_at VARCHAR,
                FOREIGN KEY(system_api_id) REFERENCES system_api_settings(id)
            )
            """
        ))
        try:
            conn.execute(text("ALTER TABLE system_api_billing_rules ADD COLUMN IF NOT EXISTS charge_multiplier FLOAT DEFAULT 2.0"))
        except Exception:
            # SQLite may not support IF NOT EXISTS for ADD COLUMN on older versions.
            try:
                conn.execute(text("ALTER TABLE system_api_billing_rules ADD COLUMN charge_multiplier FLOAT DEFAULT 2.0"))
            except Exception:
                pass
        conn.execute(text("UPDATE system_api_billing_rules SET charge_multiplier = 2.0 WHERE charge_multiplier IS NULL OR charge_multiplier < 0"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_system_api_billing_rules_system_api_id ON system_api_billing_rules (system_api_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_system_api_billing_rules_is_active ON system_api_billing_rules (is_active)"))

        # 3) transaction_action audit table
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS transaction_action (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                transaction_id INTEGER,
                reservation_tx_id INTEGER,
                settlement_tx_id INTEGER,
                stage VARCHAR,
                task_type VARCHAR,
                provider VARCHAR,
                model VARCHAR,
                system_api_id INTEGER,
                matched_rule_id INTEGER,
                reserved_cost INTEGER DEFAULT 0,
                actual_cost INTEGER DEFAULT 0,
                delta INTEGER DEFAULT 0,
                charged_amount INTEGER DEFAULT 0,
                refunded_amount INTEGER DEFAULT 0,
                outstanding_amount INTEGER DEFAULT 0,
                matched_rule_ids JSON,
                usage_metadata JSON,
                billing_metadata JSON,
                created_at VARCHAR,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(transaction_id) REFERENCES transaction_history(id),
                FOREIGN KEY(reservation_tx_id) REFERENCES transaction_history(id),
                FOREIGN KEY(settlement_tx_id) REFERENCES transaction_history(id),
                FOREIGN KEY(system_api_id) REFERENCES system_api_settings(id),
                FOREIGN KEY(matched_rule_id) REFERENCES system_api_billing_rules(id)
            )
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transaction_action_user_id ON transaction_action (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transaction_action_stage ON transaction_action (stage)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transaction_action_system_api_id ON transaction_action (system_api_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transaction_action_matched_rule_id ON transaction_action (matched_rule_id)"))

    print("[migrate] done")


if __name__ == "__main__":
    migrate()
