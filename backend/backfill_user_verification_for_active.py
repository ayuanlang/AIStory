import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text
from app.core.config import settings


def backfill_user_verification_for_active():
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # 1) Ensure superusers are marked verified regardless of legacy values.
            superuser_result = conn.execute(
                text(
                    """
                    UPDATE users
                    SET email_verified = TRUE,
                        account_status = CASE
                            WHEN account_status IS NULL OR account_status = -1 THEN 1
                            ELSE account_status
                        END,
                        email_verification_code = NULL,
                        email_verification_expires_at = NULL
                    WHERE is_superuser = TRUE
                      AND (
                          email_verified IS NULL
                          OR email_verified = FALSE
                          OR account_status IS NULL
                          OR account_status = -1
                      )
                    """
                )
            )

            # 2) Backfill active users so they are not blocked by legacy verification fields.
            active_result = conn.execute(
                text(
                    """
                    UPDATE users
                    SET email_verified = TRUE,
                        account_status = CASE
                            WHEN account_status IS NULL OR account_status = -1 THEN 1
                            ELSE account_status
                        END,
                        email_verification_code = NULL,
                        email_verification_expires_at = NULL
                    WHERE is_active = TRUE
                      AND (
                          email_verified IS NULL
                          OR email_verified = FALSE
                          OR account_status IS NULL
                          OR account_status = -1
                      )
                    """
                )
            )

            trans.commit()
            print(
                "Backfill completed: "
                f"superusers_updated={superuser_result.rowcount}, "
                f"active_users_updated={active_result.rowcount}"
            )
        except Exception as e:
            trans.rollback()
            print(f"Backfill failed: {e}")
            raise


if __name__ == "__main__":
    backfill_user_verification_for_active()
