import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text
from sqlalchemy import inspect
from app.core.config import mask_database_url, settings


def _truthy_sql(column_name: str, col_type: str) -> str:
    """Build a SQL predicate for columns that may be boolean or integer (0/1)."""
    t = (col_type or "").lower()
    if "bool" in t:
        return f"{column_name} = TRUE"
    # users.is_active is Integer (1=active); also tolerate boolean-ish ints.
    return f"{column_name} = 1"


def _falsy_or_null_sql(column_name: str, col_type: str) -> str:
    t = (col_type or "").lower()
    if "bool" in t:
        return f"{column_name} IS NULL OR {column_name} = FALSE"
    return f"{column_name} IS NULL OR {column_name} = 0"


def backfill_user_verification_for_active():
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    # Avoid printing credentials (Render/Postgres URLs embed the password).
    safe_url = db_url
    try:
        if "://" in db_url and "@" in db_url:
            scheme, rest = db_url.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            user = creds.split(":", 1)[0]
            safe_url = f"{scheme}://{user}:***@{hostpart}"
    except Exception:
        safe_url = "***"
    print(f"Connecting to database: {safe_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        inspector = inspect(engine)
        columns = inspector.get_columns("users")
        column_types = {}
        for c in columns:
            typ = c.get("type")
            type_name = ""
            if typ is not None:
                type_name = getattr(typ, "__visit_name__", None) or type(typ).__name__
            column_types[c["name"]] = str(type_name or "")
        existing_columns = set(column_types)
        print(f"Users columns detected: {sorted(existing_columns)}")

        has_superuser = "is_superuser" in existing_columns
        has_active = "is_active" in existing_columns
        has_email_verified = "email_verified" in existing_columns
        has_account_status = "account_status" in existing_columns
        has_verify_code = "email_verification_code" in existing_columns
        has_verify_expiry = "email_verification_expires_at" in existing_columns

        if not has_superuser and not has_active:
            print("Skip backfill: neither is_superuser nor is_active exists on users table.")
            return

        set_clauses = []
        if has_email_verified:
            # email_verified is Boolean in the model; keep boolean literals.
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
            where_conditions.append(_falsy_or_null_sql("email_verified", column_types.get("email_verified", "boolean")))
        if has_account_status:
            where_conditions.append("account_status IS NULL OR account_status = -1")

        where_clause = " OR ".join(where_conditions) if where_conditions else "TRUE"

        trans = conn.begin()
        try:
            # 1) Ensure superusers are marked verified regardless of legacy values.
            superuser_result = None
            if has_superuser:
                superuser_pred = _truthy_sql("is_superuser", column_types.get("is_superuser", "boolean"))
                superuser_sql = f"""
                    UPDATE users
                    SET {', '.join(set_clauses)}
                    WHERE {superuser_pred}
                      AND ({where_clause})
                """
                superuser_result = conn.execute(text(superuser_sql))

            # 2) Backfill active users so they are not blocked by legacy verification fields.
            # users.is_active is Integer (default 1), not boolean — do not compare to TRUE.
            active_result = None
            if has_active:
                active_pred = _truthy_sql("is_active", column_types.get("is_active", "integer"))
                active_sql = f"""
                    UPDATE users
                    SET {', '.join(set_clauses)}
                    WHERE {active_pred}
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
