from datetime import datetime, timedelta, timezone

# China Standard Time (UTC+8), used for all admin-facing timestamp records.
BEIJING_TZ = timezone(timedelta(hours=8), name="CST")


def now_bj() -> datetime:
    return datetime.now(BEIJING_TZ)


def now_bj_iso() -> str:
    return now_bj().isoformat(timespec="microseconds")
