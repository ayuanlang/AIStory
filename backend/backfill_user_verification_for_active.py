import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text
from sqlalchemy import inspect
from app.core.config import settings


def backfill_user_verification_for_active():
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_columns = {c['name'] for c in inspector.get_columns('users')}
        print(f"Users columns detected: {sorted(existing_columns)}")

        has_superuser = 'is_superuser' in existing_columns
        has_active = 'is_active' in existing_columns
        has_email_verified = 'email_verified' in existing_columns
        has_account_status = 'account_status' in existing_columns
        has_verify_code = 'email_verification_code' in existing_columns
        has_verify_expiry = 'email_verification_expires_at' in existing_columns

        if not has_superuser and not has_active:
            print("Skip backfill: neither is_superuser nor is_active exists on users table.")
            return

        set_clauses = []
        if has_email_verified:
            set_clauses.append("email_verified = TRUE")
        if has_account_status:
            set_clauses.append(
                """
                account_status = CASE
                    WHEN account_status IS NULL OR account_status = -1 THEN 1
                    ELSE account_status
                END
                """.strip()
            )
        if has_verify_code:
            set_clauses.append("email_verification_code = NULL")
        if has_verify_expiry:
            set_clauses.append("email_verification_expires_at = NULL")

        if not set_clauses:
            print("Skip backfill: no verification-related columns found to update.")
            return

        where_conditions = []
        if has_email_verified:
            where_conditions.append("email_verified IS NULL OR email_verified = FALSE")
        if has_account_status:
            where_conditions.append("account_status IS NULL OR account_status = -1")

        where_clause = " OR ".join(where_conditions) if where_conditions else "TRUE"

        trans = conn.begin()
        try:
            # 1) Ensure superusers are marked verified regardless of legacy values.
            superuser_result = None
            if has_superuser:
                superuser_sql = f"""
                    UPDATE users
                    SET {', '.join(set_clauses)}
                    WHERE is_superuser = TRUE
                      AND ({where_clause})
                """
                superuser_result = conn.execute(text(superuser_sql))

            # 2) Backfill active users so they are not blocked by legacy verification fields.
            active_result = None
            if has_active:
                active_sql = f"""
                    UPDATE users
                    SET {', '.join(set_clauses)}
                    WHERE is_active = TRUE
                      AND ({where_clause})
                """
                active_result = conn.execute(text(active_sql))

            trans.commit()
            print(
                "Backfill completed: "
                f"superusers_updated={(superuser_result.rowcount if superuser_result is not None else 0)}, "
                f"active_users_updated={(active_result.rowcount if active_result is not None else 0)}"
            )
        except Exception as e:
            trans.rollback()
            print(f"Backfill failed: {e}")
            return


if __name__ == "__main__":
    backfill_user_verification_for_active()
