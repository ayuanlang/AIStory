#!/usr/bin/env bash
# Web process entrypoint for Render (4GB-class hosts).
# Always use a single async UvicornWorker unless WEB_CONCURRENCY is explicitly
# set to a positive integer; values above 1 are clamped to 1 on small hosts
# when FORCE_SINGLE_WEB_WORKER=1 (default).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[boot] backend pre-start migrations begin"
python migrate_system_api_settings_drop_wide_columns.py || echo "[WARN] migrate_system_api_settings_drop_wide_columns.py failed, continuing"
python migrate_api_settings_missing_columns.py || echo "[WARN] migrate_api_settings_missing_columns.py failed, continuing"
python migrate_api_settings_user_category_binding.py || echo "[WARN] migrate_api_settings_user_category_binding.py failed, continuing"
python migrate_hailuo_billing_rules_x3.py || echo "[WARN] migrate_hailuo_billing_rules_x3.py failed, continuing"
python add_users_credits_column.py || echo "[WARN] add_users_credits_column.py failed, continuing"
python add_scene_ai_shots_result_column.py || echo "[WARN] add_scene_ai_shots_result_column.py failed, continuing"
python add_users_email_verification_columns.py || echo "[WARN] add_users_email_verification_columns.py failed, continuing"
python ensure_assets_meta_info_column.py || echo "[WARN] ensure_assets_meta_info_column.py failed, continuing"
python backfill_user_verification_for_active.py || echo "[WARN] backfill_user_verification_for_active.py failed, continuing"
python cleanup_llm_call_logs.py || echo "[WARN] cleanup_llm_call_logs.py failed, continuing"
echo "[boot] KIE data import is disabled during deploy"
export RUN_DB_BOOTSTRAP_ON_START="${RUN_DB_BOOTSTRAP_ON_START:-1}"
echo "[boot] RUN_DB_BOOTSTRAP_ON_START=${RUN_DB_BOOTSTRAP_ON_START}"

WORKERS="${WEB_CONCURRENCY:-1}"
if ! [[ "${WORKERS}" =~ ^[0-9]+$ ]] || [[ "${WORKERS}" -lt 1 ]]; then
  WORKERS=1
fi
# 4GB Render web: refuse multi-worker unless explicitly overridden.
if [[ "${FORCE_SINGLE_WEB_WORKER:-1}" == "1" ]] && [[ "${WORKERS}" -gt 1 ]]; then
  echo "[boot] clamping WEB_CONCURRENCY=${WORKERS} -> 1 (FORCE_SINGLE_WEB_WORKER=1)"
  WORKERS=1
fi
export WEB_CONCURRENCY="${WORKERS}"

echo "[boot] starting gunicorn on PORT=${PORT:-8000} workers=${WORKERS}"
exec gunicorn app.main:app \
  -c gunicorn.conf.py \
  -k uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WORKERS}" \
  --timeout "${GUNICORN_TIMEOUT:-600}" \
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-660}" \
  --keep-alive "${GUNICORN_KEEPALIVE:-15}" \
  --access-logfile - \
  --error-logfile - \
  --access-logformat '%(h)s %(l)s %(u)s [%(t)s] "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" req_time=%(D)sus pid=%(p)s' \
  --max-requests "${GUNICORN_MAX_REQUESTS:-300}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-50}"
