import logging

from sqlalchemy.orm import Session
from app.models.all_models import SystemLog
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal

logger = logging.getLogger("api_logger")

def log_action(db: Session, user_id: int, user_name: str, action: str, details: str = None, ip_address: str = None):
    try:
        new_log = SystemLog(
            user_id=user_id,
            user_name=user_name,
            action=action,
            details=details,
            ip_address=ip_address,
            timestamp=now_bj_iso()
        )
        
        # We always use a new session to avoid breaking the caller's transaction
        # and prevent nested commit()s of half-finished states.
        with SessionLocal() as log_db:
            log_db.add(new_log)
            log_db.commit()
            
    except Exception as e:
        logger.exception(
            "Failed to write system log | user_id=%s user_name=%s action=%s error=%s",
            user_id,
            user_name,
            action,
            e,
        )

