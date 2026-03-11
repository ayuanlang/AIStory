from sqlalchemy.orm import Session
from app.models.all_models import SystemLog
from app.core.time_utils import now_bj_iso

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
        db.add(new_log)
        db.commit()
    except Exception as e:
        print(f"Failed to write system log: {e}")

