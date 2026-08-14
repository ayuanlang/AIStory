
import logging
import bcrypt
import os
import json
from datetime import datetime
from sqlalchemy import text, inspect
from app.db.session import engine, SessionLocal
from app.models import all_models as models
from app.services.system_default_api_service import normalize_task_category
from app.core.time_utils import now_bj_iso

APISetting = models.APISetting
User = models.User
ProjectShare = models.ProjectShare
ProjectAssetReviewThread = getattr(models, "ProjectAssetReviewThread", None)
ProjectAssetReviewRound = getattr(models, "ProjectAssetReviewRound", None)
ProjectAssetReviewMessage = getattr(models, "ProjectAssetReviewMessage", None)
SystemAPISetting = models.SystemAPISetting
ProviderKeyPool = models.ProviderKeyPool
OSSProviderPool = getattr(models, "OSSProviderPool", None)
DeletedMedia = getattr(models, "DeletedMedia", None)
DeletionBatch = getattr(models, "DeletionBatch", None)
DeletionBatchItem = getattr(models, "DeletionBatchItem", None)
SystemAPIBillingRule = models.SystemAPIBillingRule
TransactionAction = models.TransactionAction
SMTPSystemConfig = models.SMTPSystemConfig
WechatPayConfig = models.WechatPayConfig
TaskDefaultSystemAPI = models.TaskDefaultSystemAPI

_REVIEW_MODELS_AVAILABLE = all(
    model is not None
    for model in (ProjectAssetReviewThread, ProjectAssetReviewRound, ProjectAssetReviewMessage)
)

logger = logging.getLogger(__name__)


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


def _normalize_system_api_price_tier(category: str, average_cost: int) -> str:
    normalized_category = str(category or "").strip().lower()
    cost = max(0, int(average_cost or 0))
    if normalized_category == "video":
        if cost <= 120:
            return "low"
        if cost <= 400:
            return "mid"
        return "high"
    if normalized_category == "image":
        if cost <= 15:
            return "low"
        if cost <= 80:
            return "mid"
        return "high"
    if cost <= 30:
        return "low"
    if cost <= 150:
        return "mid"
    return "high"


def _infer_system_api_retry_group(row: SystemAPISetting) -> str:
    category = str(getattr(row, "category", "") or "").strip().lower()
    provider = str(getattr(row, "provider", "") or "").strip().lower()
    model = str(getattr(row, "model", "") or "").strip().lower()
    name = str(getattr(row, "name", "") or "").strip().lower()
    merged = f"{provider} {model} {name}"

    if category == "image":
        if any(token in merged for token in ["create-character", "upload-character", "character"]):
            return "image-character"
        if any(token in merged for token in ["remove-background"]):
            return "image-remove-bg"
        if any(token in merged for token in ["upscale", "reframe"]):
            return "image-upscale"
        if any(token in merged for token in ["image-to-image", "-edit", "/edit", " edit", "kontext", "remix"]):
            return "image-edit-pro"
        if any(token in merged for token in ["fast", "flex-text-to-image", "imagen4-fast", "qwen/text-to-image"]):
            return "image-general-fast"
        return "image-general-pro"

    if category == "video":
        if any(token in merged for token in ["storyboard"]):
            return "video-storyboard"
        if any(token in merged for token in ["characters"]):
            return "video-character"
        if any(token in merged for token in ["video-to-video", "watermark-remover", "video-upscale"]):
            return "video-v2v"
        if any(token in merged for token in ["image-to-video", "i2v", "animate-", "motion-control"]):
            if any(token in merged for token in ["lite", "flash", "standard"]):
                return "video-i2v-fast"
            return "video-i2v-pro"
        if any(token in merged for token in ["text-to-video", "t2v", "from-audio", "speech-to-video"]):
            if any(token in merged for token in ["lite", "fast", "draft", "turbo"]):
                return "video-t2v-fast"
            return "video-t2v-pro"
        if any(token in merged for token in ["vidu", "seedance", "sora-2", "veo", "hailuo", "wan", "kling", "runway"]):
            return "video-t2v-pro"

    if category in {"voice", "audio", "tools"}:
        if any(token in merged for token in ["speech-to-text", "stt"]):
            return "voice-stt"
        if any(token in merged for token in ["sound-effect", "audio-isolation", "sfx"]):
            return "voice-sfx"
        if any(token in merged for token in ["dialogue"]):
            return "voice-dialogue"
        if any(token in merged for token in ["text-to-speech", "tts", "text-to-audio"]):
            return "voice-tts-general"

    return ""


def _backfill_system_api_retry_metadata() -> None:
    try:
        from app.services.billing_service import BillingService

        with SessionLocal() as session:
            rows = session.query(SystemAPISetting).filter(~SystemAPISetting.category.like("System_%")).all()
            changed = 0
            now_iso = now_bj_iso()

            def _fallback_average_cost(row: SystemAPISetting, cfg: dict) -> int:
                api_pricing = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
                for raw in (
                    api_pricing.get("cost"),
                    cfg.get("billing_cost"),
                    getattr(row, "price_avg_cost", None),
                    getattr(row, "provider_price_avg_cost", None),
                ):
                    try:
                        parsed = int(float(raw or 0))
                    except Exception:
                        parsed = 0
                    if parsed > 0:
                        return parsed
                return 0

            for row in rows:
                cfg = _safe_json_dict(getattr(row, "config", None))
                retry_group = _infer_system_api_retry_group(row)
                average_cost = 0
                try:
                    average_cost = int((BillingService.estimate_system_api_average_price(session, int(row.id)) or {}).get("average_cost") or 0)
                except Exception:
                    average_cost = 0
                if average_cost <= 0:
                    average_cost = _fallback_average_cost(row, cfg)
                retry_price_group = _normalize_system_api_price_tier(getattr(row, "category", None), average_cost)

                next_cfg = dict(cfg)
                if retry_group:
                    next_cfg["retry_group"] = retry_group
                else:
                    next_cfg.pop("retry_group", None)
                next_cfg["retry_price_group"] = retry_price_group
                next_cfg["retry_price_estimate"] = int(max(0, average_cost))
                if next_cfg.get("smart_priority") is None:
                    next_cfg["smart_priority"] = 100

                if next_cfg != cfg:
                    row.config = next_cfg
                    row.updated_at = now_iso
                    changed += 1

            if changed > 0:
                session.commit()
                logger.info("Backfilled %s system_api_settings retry group/price tier metadata", changed)
    except Exception as exc:
        logger.warning("Failed to backfill system_api_settings retry metadata: %s", exc)


def _compile_column_type_sql(column) -> str:
    try:
        return column.type.compile(dialect=engine.dialect)
    except Exception:
        return str(column.type)


def _ensure_missing_table_columns(table_name: str, model, *, is_postgres: bool) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return

    existing_cols = {c['name'] for c in inspector.get_columns(table_name)}
    missing_columns = [
        column
        for column in model.__table__.columns
        if not column.primary_key and column.name not in existing_cols
    ]
    if not missing_columns:
        return

    with engine.begin() as conn:
        for column in missing_columns:
            column_type_sql = _compile_column_type_sql(column)
            ddl = f"ALTER TABLE {table_name} ADD COLUMN {'IF NOT EXISTS ' if is_postgres else ''}{column.name} {column_type_sql}"
            conn.execute(text(ddl))

    logger.info(
        "Ensured missing columns for %s: %s",
        table_name,
        ", ".join(column.name for column in missing_columns),
    )


def _ensure_review_workflow_schema(*, is_postgres: bool, apply_backfills: bool = True) -> None:
    if not _REVIEW_MODELS_AVAILABLE:
        logger.warning("Skipping project asset review table bootstrap because review models are unavailable")
        return

    inspector = inspect(engine)
    try:
        if not inspector.has_table("project_asset_review_threads"):
            ProjectAssetReviewThread.__table__.create(bind=engine, checkfirst=True)
            logger.info("Created project_asset_review_threads table")
        if not inspector.has_table("project_asset_review_rounds"):
            ProjectAssetReviewRound.__table__.create(bind=engine, checkfirst=True)
            logger.info("Created project_asset_review_rounds table")
        if not inspector.has_table("project_asset_review_messages"):
            ProjectAssetReviewMessage.__table__.create(bind=engine, checkfirst=True)
            logger.info("Created project_asset_review_messages table")
    except Exception as exc:
        logger.error(f"Failed to ensure project asset review tables: {exc}")
        return

    try:
        _ensure_missing_table_columns("project_asset_review_threads", ProjectAssetReviewThread, is_postgres=is_postgres)
        _ensure_missing_table_columns("project_asset_review_rounds", ProjectAssetReviewRound, is_postgres=is_postgres)
        _ensure_missing_table_columns("project_asset_review_messages", ProjectAssetReviewMessage, is_postgres=is_postgres)

        if apply_backfills:
            with engine.begin() as conn:
                if is_postgres:
                    conn.execute(text("UPDATE project_asset_review_threads SET title = COALESCE(title, '')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET status = COALESCE(NULLIF(status, ''), 'open')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET latest_round_no = COALESCE(latest_round_no, 0)"))
                    conn.execute(text("UPDATE project_asset_review_threads SET latest_activity_at = COALESCE(latest_activity_at, updated_at, created_at)"))
                    conn.execute(text("UPDATE project_asset_review_threads SET created_at = COALESCE(created_at, updated_at, latest_activity_at, '')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET updated_at = COALESCE(updated_at, latest_activity_at, created_at, '')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET requester_last_read_at = COALESCE(requester_last_read_at, created_at, updated_at, latest_activity_at)"))

                    conn.execute(text("UPDATE project_asset_review_rounds SET round_no = COALESCE(round_no, 1)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET scope_type = COALESCE(NULLIF(scope_type, ''), 'all_current')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET entity_required = COALESCE(entity_required, TRUE)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET shot_required = COALESCE(shot_required, TRUE)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET entity_decision = COALESCE(NULLIF(entity_decision, ''), 'pending')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET shot_decision = COALESCE(NULLIF(shot_decision, ''), 'pending')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET overall_status = COALESCE(NULLIF(overall_status, ''), 'pending_reviewer')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET selected_entity_ids = COALESCE(selected_entity_ids, '[]'::json)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET selected_shot_ids = COALESCE(selected_shot_ids, '[]'::json)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET created_at = COALESCE(created_at, updated_at, '')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET updated_at = COALESCE(updated_at, created_at, '')"))

                    conn.execute(text("UPDATE project_asset_review_messages SET sender_role = COALESCE(NULLIF(sender_role, ''), 'requester')"))
                    conn.execute(text("UPDATE project_asset_review_messages SET message_type = COALESCE(NULLIF(message_type, ''), 'message')"))
                    conn.execute(text("UPDATE project_asset_review_messages SET created_at = COALESCE(created_at, '')"))
                else:
                    conn.execute(text("UPDATE project_asset_review_threads SET title = COALESCE(title, '')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET status = COALESCE(NULLIF(status, ''), 'open')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET latest_round_no = COALESCE(latest_round_no, 0)"))
                    conn.execute(text("UPDATE project_asset_review_threads SET latest_activity_at = COALESCE(latest_activity_at, updated_at, created_at)"))
                    conn.execute(text("UPDATE project_asset_review_threads SET created_at = COALESCE(created_at, updated_at, latest_activity_at, '')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET updated_at = COALESCE(updated_at, latest_activity_at, created_at, '')"))
                    conn.execute(text("UPDATE project_asset_review_threads SET requester_last_read_at = COALESCE(requester_last_read_at, created_at, updated_at, latest_activity_at)"))

                    conn.execute(text("UPDATE project_asset_review_rounds SET round_no = COALESCE(round_no, 1)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET scope_type = COALESCE(NULLIF(scope_type, ''), 'all_current')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET entity_required = COALESCE(entity_required, 1)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET shot_required = COALESCE(shot_required, 1)"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET entity_decision = COALESCE(NULLIF(entity_decision, ''), 'pending')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET shot_decision = COALESCE(NULLIF(shot_decision, ''), 'pending')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET overall_status = COALESCE(NULLIF(overall_status, ''), 'pending_reviewer')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET selected_entity_ids = COALESCE(selected_entity_ids, '[]')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET selected_shot_ids = COALESCE(selected_shot_ids, '[]')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET created_at = COALESCE(created_at, updated_at, '')"))
                    conn.execute(text("UPDATE project_asset_review_rounds SET updated_at = COALESCE(updated_at, created_at, '')"))

                    conn.execute(text("UPDATE project_asset_review_messages SET sender_role = COALESCE(NULLIF(sender_role, ''), 'requester')"))
                    conn.execute(text("UPDATE project_asset_review_messages SET message_type = COALESCE(NULLIF(message_type, ''), 'message')"))
                    conn.execute(text("UPDATE project_asset_review_messages SET created_at = COALESCE(created_at, '')"))

            logger.info("Ensured project asset review workflow schema compatibility with backfills")
        else:
            logger.info("Ensured project asset review workflow schema structure without startup backfills")
    except Exception as exc:
        logger.error(f"Failed to ensure project asset review workflow schema compatibility: {exc}")


def _deactivate_legacy_duplicate_base_billing_rules() -> None:
    """Keep only the newest active base pricing rule per system API."""
    try:
        with SessionLocal() as session:
            rows = session.query(SystemAPIBillingRule).filter(
                SystemAPIBillingRule.is_active == True,
            ).order_by(
                SystemAPIBillingRule.system_api_id.asc(),
                SystemAPIBillingRule.id.desc(),
            ).all()

            seen_system_api_ids = set()
            changed = 0
            now_iso = now_bj_iso()

            for row in rows:
                extra = row.extra_conditions if isinstance(row.extra_conditions, dict) else {}
                if str(extra.get("rule_kind", "")).strip().lower() != "base_pricing":
                    continue

                system_api_id = int(getattr(row, "system_api_id", 0) or 0)
                if system_api_id <= 0:
                    continue

                if system_api_id in seen_system_api_ids:
                    row.is_active = False
                    row.updated_at = now_iso
                    changed += 1
                    continue

                seen_system_api_ids.add(system_api_id)

            if changed:
                session.commit()
                logger.info("Deactivated %s legacy duplicate base billing rules", changed)
    except Exception as exc:
        logger.warning("Failed to deactivate duplicate base billing rules: %s", exc)


def _ensure_core_performance_indexes() -> None:
    """Create hot-path indexes idempotently for auth/project/system-api reads."""
    ddl_statements = [
        # users: auth and profile lookups
        "CREATE INDEX IF NOT EXISTS ix_users_username_active ON users(username, is_active)",
        "CREATE INDEX IF NOT EXISTS ix_users_email_active ON users(email, is_active)",
        # projects: owner dashboard listing and recency sorting
        "CREATE INDEX IF NOT EXISTS ix_projects_owner_updated ON projects(owner_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_projects_owner_created ON projects(owner_id, created_at)",
        # project share checks
        "CREATE INDEX IF NOT EXISTS ix_project_shares_project_user ON project_shares(project_id, user_id)",
        "CREATE INDEX IF NOT EXISTS ix_project_shares_user_project ON project_shares(user_id, project_id)",
        "CREATE INDEX IF NOT EXISTS ix_review_threads_project_activity ON project_asset_review_threads(project_id, latest_activity_at)",
        "CREATE INDEX IF NOT EXISTS ix_review_threads_reviewer_activity ON project_asset_review_threads(reviewer_user_id, latest_activity_at)",
        "CREATE INDEX IF NOT EXISTS ix_review_rounds_thread_roundno ON project_asset_review_rounds(thread_id, round_no)",
        "CREATE INDEX IF NOT EXISTS ix_review_messages_round_created ON project_asset_review_messages(round_id, created_at)",
        # user api bindings
        "CREATE INDEX IF NOT EXISTS ix_api_settings_user_category_system ON api_settings(user_id, category, system_api_id)",
        # system api selection hot paths
        "CREATE INDEX IF NOT EXISTS ix_system_api_settings_cat_depr ON system_api_settings(category, deprecated)",
        "CREATE INDEX IF NOT EXISTS ix_system_api_settings_provider_cat_model ON system_api_settings(provider, category, model)",
        "CREATE INDEX IF NOT EXISTS ix_system_api_settings_active_cat ON system_api_settings(is_active, category)",
    ]

    with engine.begin() as conn:
        for ddl in ddl_statements:
            try:
                conn.execute(text(ddl))
            except Exception as exc:
                logger.warning("Index DDL failed (non-fatal): %s | err=%s", ddl, exc)


def _ensure_shots_project_episode_shot_id_unique_index(*, is_postgres: bool) -> None:
    """Enforce active Shot uniqueness: project + episode + shot_id (business EP##_SC##_SH##)."""
    if not is_postgres and engine.dialect.name != "sqlite":
        logger.info("Skip shots scoped unique index migration for dialect=%s", engine.dialect.name)
        return

    # Soft-delete older duplicates so the partial unique index can be created.
    # Keep the highest id per (project_id, episode_id, upper(trim(shot_id))).
    dedup_sql = (
        "UPDATE shots SET is_deleted = true, deleted_at = CURRENT_TIMESTAMP "
        "WHERE coalesce(is_deleted, false) = false "
        "AND id NOT IN ("
        "  SELECT max(id) FROM shots "
        "  WHERE coalesce(is_deleted, false) = false "
        "    AND shot_id IS NOT NULL AND trim(shot_id) <> '' "
        "  GROUP BY project_id, coalesce(episode_id, -1), upper(trim(shot_id))"
        ") "
        "AND shot_id IS NOT NULL AND trim(shot_id) <> ''"
    )

    with engine.begin() as conn:
        try:
            conn.execute(text(dedup_sql))
        except Exception as exc:
            logger.warning("Shot deduplication before unique index failed (non-fatal): %s", exc)

    ddl = (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_shots_proj_ep_shot_id_active "
        "ON shots (project_id, COALESCE(episode_id, -1), upper(trim(shot_id))) "
        "WHERE shot_id IS NOT NULL AND trim(shot_id) <> '' "
        "AND coalesce(is_deleted, false) = false"
    )
    with engine.begin() as conn:
        try:
            conn.execute(text(ddl))
            logger.info("Ensured shots project/episode/shot_id unique index")
        except Exception as exc:
            logger.warning("Shot unique index DDL failed (non-fatal): %s | err=%s", ddl, exc)


def _canonicalize_scene_no_for_unique_index(scene_no: str) -> str:
    """Mirror import canonicalization: EP01_SC03/03/3 → '3'; letter-suffix kept."""
    import re

    source = str(scene_no or "").strip()
    if not source:
        return ""
    letter_match = re.fullmatch(r"(EP\d+_SC\d+[A-Za-z]+)", source, flags=re.IGNORECASE)
    if letter_match:
        return letter_match.group(1).upper()
    canonical_match = re.fullmatch(r"EP\d+_SC(\d+)", source, flags=re.IGNORECASE)
    if canonical_match:
        return str(int(canonical_match.group(1)))
    sc_match = re.fullmatch(r"SC?(\d+)", source, flags=re.IGNORECASE)
    if sc_match:
        return str(int(sc_match.group(1)))
    if re.fullmatch(r"\d+", source):
        return str(int(source))
    return source


def _ensure_scenes_episode_scene_no_unique_index(*, is_postgres: bool) -> None:
    """Enforce active Scene uniqueness: one scene_no per episode (project implied)."""
    if not is_postgres and engine.dialect.name != "sqlite":
        logger.info("Skip scenes episode/scene_no unique index migration for dialect=%s", engine.dialect.name)
        return

    # 1) Canonicalize legacy aliases (EP01_SC03 → 3) then soft-delete active dupes.
    try:
        db = SessionLocal()
        try:
            Scene = models.Scene
            rows = (
                db.query(Scene)
                .filter(
                    (Scene.is_deleted.is_(False)) | (Scene.is_deleted.is_(None)),
                    Scene.scene_no.isnot(None),
                )
                .order_by(Scene.episode_id.asc(), Scene.id.asc())
                .all()
            )
            changed = 0
            for row in rows:
                canonical = _canonicalize_scene_no_for_unique_index(getattr(row, "scene_no", None))
                if not canonical:
                    continue
                if str(row.scene_no or "").strip() != canonical:
                    row.scene_no = canonical
                    changed += 1
            if changed:
                db.commit()
                logger.info("Canonicalized %s active scene_no value(s) before unique index", changed)
            else:
                db.rollback()

            # Soft-delete older active duplicates per (episode_id, canonical scene_no).
            active_rows = (
                db.query(Scene)
                .filter(
                    (Scene.is_deleted.is_(False)) | (Scene.is_deleted.is_(None)),
                    Scene.scene_no.isnot(None),
                )
                .order_by(Scene.episode_id.asc(), Scene.id.desc())
                .all()
            )
            seen = set()
            soft_deleted = 0
            now = now_bj_iso()
            for row in active_rows:
                key = (
                    int(getattr(row, "episode_id", 0) or 0),
                    str(getattr(row, "scene_no", "") or "").strip().upper(),
                )
                if not key[1]:
                    continue
                if key in seen:
                    row.is_deleted = True
                    row.deleted_at = now
                    soft_deleted += 1
                    continue
                seen.add(key)
            if soft_deleted:
                db.commit()
                logger.info(
                    "Soft-deleted %s duplicate active scene(s) before unique index",
                    soft_deleted,
                )
            else:
                db.rollback()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Scene canonicalization/dedup before unique index failed (non-fatal): %s", exc)

    ddl = (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_scenes_episode_scene_no_active "
        "ON scenes (episode_id, upper(trim(scene_no))) "
        "WHERE scene_no IS NOT NULL AND trim(scene_no) <> '' "
        "AND coalesce(is_deleted, false) = false"
    )
    with engine.begin() as conn:
        try:
            conn.execute(text(ddl))
            logger.info("Ensured scenes episode/scene_no unique index")
        except Exception as exc:
            logger.warning("Scene unique index DDL failed (non-fatal): %s | err=%s", ddl, exc)


def _ensure_entities_episode_scoped_unique_indexes(*, is_postgres: bool) -> None:
    """Enforce entity uniqueness for project+episode+type+normalized-name at DB level."""
    # Expression/partial unique indexes are supported by PostgreSQL and SQLite.
    if not is_postgres and engine.dialect.name != "sqlite":
        logger.info("Skip entity scoped unique index migration for dialect=%s", engine.dialect.name)
        return

    # Clean up duplicates before creating unique indexes
    dedup_statements = [
        (
            "DELETE FROM entities WHERE id NOT IN ("
            "    SELECT max(id) FROM entities "
            "    GROUP BY project_id, coalesce(episode_id, -1), lower(trim(type)), coalesce(lower(trim(name)), '')"
            ")"
        ),
        (
            "DELETE FROM entities WHERE id NOT IN ("
            "    SELECT max(id) FROM entities "
            "    WHERE name_en IS NOT NULL AND trim(name_en) <> '' "
            "    GROUP BY project_id, coalesce(episode_id, -1), lower(trim(type)), lower(trim(name_en))"
            ") AND name_en IS NOT NULL AND trim(name_en) <> ''"
        )
    ]
    
    with engine.begin() as conn:
        for ddl in dedup_statements:
            try:
                conn.execute(text(ddl))
            except Exception as exc:
                logger.warning("Entity deduplication failed: %s | err=%s", ddl, exc)

    ddl_statements = [
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_entities_proj_ep_type_name_norm "
            "ON entities (project_id, COALESCE(episode_id, -1), lower(trim(type)), lower(trim(name))) "
            "WHERE name IS NOT NULL AND trim(name) <> '' "
            "AND coalesce(is_deleted, false) = false"
        ),
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_entities_proj_ep_type_name_en_norm "
            "ON entities (project_id, COALESCE(episode_id, -1), lower(trim(type)), lower(trim(name_en))) "
            "WHERE name_en IS NOT NULL AND trim(name_en) <> '' "
            "AND coalesce(is_deleted, false) = false"
        ),
    ]

    with engine.begin() as conn:
        for index_name in (
            "uq_entities_proj_ep_type_name_norm",
            "uq_entities_proj_ep_type_name_en_norm",
        ):
            try:
                conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
            except Exception as exc:
                logger.warning("Entity unique index drop failed (non-fatal): %s | err=%s", index_name, exc)
        for ddl in ddl_statements:
            try:
                conn.execute(text(ddl))
            except Exception as exc:
                # Existing duplicate rows may block unique index creation; keep startup non-fatal.
                logger.warning("Entity unique index migration failed (non-fatal): %s | err=%s", ddl, exc)


def _ensure_assets_normalized_url_unique_index(*, is_postgres: bool) -> None:
    """Backfill assets.url_normalized and enforce uniqueness for same material under same context."""
    if not is_postgres and engine.dialect.name != "sqlite":
        logger.info("Skip assets normalized url index migration for dialect=%s", engine.dialect.name)
        return

    if is_postgres:
        backfill_sql = (
            "UPDATE assets "
            "SET url_normalized = lower(split_part(coalesce(url, ''), '?', 1)) "
            "WHERE coalesce(url_normalized, '') = '' AND coalesce(url, '') <> ''"
        )
        dedup_sql = (
            "DELETE FROM assets a "
            "USING assets b "
            "WHERE a.id < b.id "
            "AND a.user_id = b.user_id "
            "AND lower(coalesce(a.type, '')) = lower(coalesce(b.type, '')) "
            "AND coalesce(a.project_id, -1) = coalesce(b.project_id, -1) "
            "AND coalesce(a.episode_id, -1) = coalesce(b.episode_id, -1) "
            "AND coalesce(a.url_normalized, '') = coalesce(b.url_normalized, '') "
            "AND coalesce(a.url_normalized, '') <> ''"
        )
        create_index_sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_user_type_scope_url_norm "
            "ON assets (user_id, lower(type), coalesce(project_id, -1), coalesce(episode_id, -1), url_normalized) "
            "WHERE url_normalized IS NOT NULL AND trim(url_normalized) <> '' "
            "AND coalesce(is_deleted, false) = false"
        )
    else:
        backfill_sql = (
            "UPDATE assets "
            "SET url_normalized = lower("
            "CASE WHEN instr(coalesce(url, ''), '?') > 0 "
            "THEN substr(coalesce(url, ''), 1, instr(coalesce(url, ''), '?') - 1) "
            "ELSE coalesce(url, '') END" 
            ") "
            "WHERE coalesce(url_normalized, '') = '' AND coalesce(url, '') <> ''"
        )
        dedup_sql = (
            "DELETE FROM assets "
            "WHERE id NOT IN ("
            "  SELECT max(id) FROM assets "
            "  WHERE coalesce(url_normalized, '') <> '' "
            "  GROUP BY user_id, lower(coalesce(type, '')), coalesce(project_id, -1), coalesce(episode_id, -1), coalesce(url_normalized, '')"
            ") "
            "AND coalesce(url_normalized, '') <> ''"
        )
        create_index_sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_user_type_scope_url_norm "
            "ON assets (user_id, lower(type), ifnull(project_id, -1), ifnull(episode_id, -1), url_normalized) "
            "WHERE url_normalized IS NOT NULL AND trim(url_normalized) <> '' "
            "AND coalesce(is_deleted, 0) = 0"
        )

    with engine.begin() as conn:
        try:
            conn.execute(text(backfill_sql))
        except Exception as exc:
            logger.warning("Assets url_normalized backfill failed (non-fatal): %s", exc)

        try:
            conn.execute(text(dedup_sql))
        except Exception as exc:
            logger.warning("Assets dedup before unique index failed (non-fatal): %s", exc)

        try:
            conn.execute(text("DROP INDEX IF EXISTS uq_assets_user_type_scope_url_norm"))
        except Exception as exc:
            logger.warning("Assets unique index drop failed (non-fatal): %s", exc)

        try:
            conn.execute(text(create_index_sql))
        except Exception as exc:
            logger.warning("Assets unique index migration failed (non-fatal): %s", exc)


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
                    "active": 1,
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


def _ensure_user_group_schema(*, is_postgres: bool) -> dict:
    """
    Ensure user-group tables/columns exist on both SQLite and Postgres.
    Safe to call repeatedly; used by critical startup bootstrap and /fix-db-schema.
    """
    status = {
        "user_groups": False,
        "user_group_memberships": False,
        "project_group_credit_allocations": False,
        "users.current_group_id": False,
        "transaction_history.target_group_id": False,
        "payment_orders.target_group_id": False,
        "invoice_profiles.group_id": False,
        "actions": [],
        "errors": [],
    }

    def _note(action: str) -> None:
        status["actions"].append(action)
        logger.info(action)

    def _fail(msg: str) -> None:
        status["errors"].append(msg)
        logger.error(msg)

    try:
        inspector = inspect(engine)

        # 1) Create group tables first (users.current_group_id FKs to user_groups).
        if hasattr(models, "UserGroup"):
            if not inspector.has_table("user_groups"):
                models.UserGroup.__table__.create(bind=engine, checkfirst=True)
                _note("Created user_groups table")
            else:
                status["actions"].append("user_groups already exists")
            # Explicit DEFAULT FALSE so existing groups do not bill from pool until opted in.
            try:
                ug_cols = {c["name"] for c in inspect(engine).get_columns("user_groups")}
                if "allow_group_credit_billing" not in ug_cols:
                    with engine.begin() as conn:
                        if is_postgres:
                            conn.execute(
                                text(
                                    "ALTER TABLE user_groups "
                                    "ADD COLUMN IF NOT EXISTS allow_group_credit_billing "
                                    "BOOLEAN NOT NULL DEFAULT FALSE"
                                )
                            )
                        else:
                            conn.execute(
                                text(
                                    "ALTER TABLE user_groups "
                                    "ADD COLUMN allow_group_credit_billing "
                                    "BOOLEAN NOT NULL DEFAULT 0"
                                )
                            )
                    _note("Added user_groups.allow_group_credit_billing (default false)")
                else:
                    with engine.begin() as conn:
                        if is_postgres:
                            conn.execute(
                                text(
                                    "UPDATE user_groups SET allow_group_credit_billing = FALSE "
                                    "WHERE allow_group_credit_billing IS NULL"
                                )
                            )
                        else:
                            conn.execute(
                                text(
                                    "UPDATE user_groups SET allow_group_credit_billing = 0 "
                                    "WHERE allow_group_credit_billing IS NULL"
                                )
                            )
            except Exception as col_exc:
                _fail(f"Failed to ensure user_groups.allow_group_credit_billing: {col_exc}")
            _ensure_missing_table_columns("user_groups", models.UserGroup, is_postgres=is_postgres)
            status["user_groups"] = inspect(engine).has_table("user_groups")

        if hasattr(models, "UserGroupMembership"):
            if not inspect(engine).has_table("user_group_memberships"):
                models.UserGroupMembership.__table__.create(bind=engine, checkfirst=True)
                _note("Created user_group_memberships table")
            else:
                status["actions"].append("user_group_memberships already exists")
            _ensure_missing_table_columns(
                "user_group_memberships",
                models.UserGroupMembership,
                is_postgres=is_postgres,
            )
            status["user_group_memberships"] = inspect(engine).has_table("user_group_memberships")

        if hasattr(models, "ProjectGroupCreditAllocation"):
            if not inspect(engine).has_table("project_group_credit_allocations"):
                models.ProjectGroupCreditAllocation.__table__.create(bind=engine, checkfirst=True)
                _note("Created project_group_credit_allocations table")
            else:
                status["actions"].append("project_group_credit_allocations already exists")
            _ensure_missing_table_columns(
                "project_group_credit_allocations",
                models.ProjectGroupCreditAllocation,
                is_postgres=is_postgres,
            )
            status["project_group_credit_allocations"] = inspect(engine).has_table(
                "project_group_credit_allocations"
            )

        # 2) Optional FK columns on existing tables (no hard REFERENCES in ALTER for portability).
        column_specs = [
            ("users", "current_group_id", "INTEGER", "users.current_group_id"),
            ("transaction_history", "target_group_id", "INTEGER", "transaction_history.target_group_id"),
            ("payment_orders", "target_group_id", "INTEGER", "payment_orders.target_group_id"),
            ("invoice_profiles", "group_id", "INTEGER", "invoice_profiles.group_id"),
        ]
        for table_name, column_name, column_type, status_key in column_specs:
            try:
                insp = inspect(engine)
                if not insp.has_table(table_name):
                    status[status_key] = False
                    continue
                cols = {c["name"] for c in insp.get_columns(table_name)}
                if column_name not in cols:
                    with engine.begin() as conn:
                        if is_postgres:
                            conn.execute(
                                text(
                                    f"ALTER TABLE {table_name} "
                                    f"ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
                                )
                            )
                        else:
                            conn.execute(
                                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                            )
                    _note(f"Added {table_name}.{column_name}")
                status[status_key] = column_name in {
                    c["name"] for c in inspect(engine).get_columns(table_name)
                }
            except Exception as col_exc:
                _fail(f"Failed to ensure {table_name}.{column_name}: {col_exc}")

        # 3) Membership uniqueness to avoid duplicate inserts under concurrency.
        if status.get("user_group_memberships"):
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text(
                                """
                                CREATE UNIQUE INDEX IF NOT EXISTS uq_user_group_memberships_user_group
                                ON user_group_memberships (user_id, group_id)
                                """
                            )
                        )
                    else:
                        conn.execute(
                            text(
                                """
                                CREATE UNIQUE INDEX IF NOT EXISTS uq_user_group_memberships_user_group
                                ON user_group_memberships (user_id, group_id)
                                """
                            )
                        )
                status["actions"].append("Ensured unique index on user_group_memberships(user_id, group_id)")
            except Exception as idx_exc:
                # Duplicate historical rows may block unique index creation; keep serving traffic.
                _fail(f"Failed to ensure membership unique index: {idx_exc}")

    except Exception as exc:
        _fail(f"Failed to ensure user group schema: {exc}")

    return status


def inspect_user_group_schema() -> dict:
    """Read-only snapshot of user-group related schema for diagnostics."""
    inspector = inspect(engine)
    result = {
        "dialect": getattr(engine.dialect, "name", None),
        "tables": {},
        "columns": {},
    }
    for table_name in (
        "user_groups",
        "user_group_memberships",
        "project_group_credit_allocations",
        "users",
        "transaction_history",
        "payment_orders",
        "invoice_profiles",
    ):
        exists = inspector.has_table(table_name)
        result["tables"][table_name] = exists
        if exists:
            result["columns"][table_name] = sorted(c["name"] for c in inspector.get_columns(table_name))
    return result


def _ensure_user_runtime_schema(*, is_postgres: bool) -> None:
    if is_postgres:
        user_columns_pg = [
            ("is_active", "INTEGER DEFAULT 1"),
            ("account_status", "INTEGER DEFAULT 1"),
            ("email_verified", "BOOLEAN DEFAULT FALSE"),
            ("email_verification_code", "VARCHAR"),
            ("email_verification_expires_at", "VARCHAR"),
            ("is_superuser", "BOOLEAN DEFAULT FALSE"),
            ("is_authorized", "BOOLEAN DEFAULT FALSE"),
            ("is_system", "BOOLEAN DEFAULT FALSE"),
            ("credits", "INTEGER DEFAULT 0"),
            ("avatar_url", "VARCHAR"),
            ("current_group_id", "INTEGER"),
        ]
        with engine.begin() as conn:
            for col_name, col_type in user_columns_pg:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                except Exception as e:
                    logger.error(f"Failed to ensure users.{col_name}: {e}")

        try:
            inspector = inspect(engine)
            existing_user_cols_meta = {c['name']: c for c in inspector.get_columns('users')}
            is_active_col = existing_user_cols_meta.get('is_active') or {}
            is_active_type_name = str(is_active_col.get('type') or '').lower()
            logger.info(
                "User runtime schema check | users.is_active type=%s nullable=%s default=%s",
                is_active_type_name or None,
                is_active_col.get('nullable'),
                is_active_col.get('default'),
            )
            if 'bool' in is_active_type_name:
                try:
                    logger.warning("users.is_active is boolean on startup; attempting ALTER COLUMN TYPE to INTEGER")
                    with engine.begin() as conn:
                        conn.execute(text("""
                            ALTER TABLE users
                            ALTER COLUMN is_active TYPE INTEGER
                            USING CASE
                                WHEN is_active IS TRUE THEN 1
                                WHEN is_active IS FALSE OR is_active IS NULL THEN 0
                                ELSE 0
                            END
                        """))
                    logger.info("Normalized users.is_active from boolean to integer via ALTER COLUMN TYPE")
                except Exception as alter_exc:
                    logger.warning(
                        "ALTER COLUMN TYPE for users.is_active failed, rebuilding column instead: %s",
                        alter_exc,
                    )
                    temp_col = "is_active_int_migrated"
                    with engine.begin() as conn:
                        existing_user_cols_meta = {c['name']: c for c in inspect(conn).get_columns('users')}
                        if temp_col in existing_user_cols_meta:
                            conn.execute(text(f"ALTER TABLE users DROP COLUMN IF EXISTS {temp_col} CASCADE"))
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {temp_col} INTEGER"))
                        conn.execute(text(f"""
                            UPDATE users
                            SET {temp_col} = CASE
                                WHEN is_active IS TRUE THEN 1
                                WHEN is_active IS FALSE OR is_active IS NULL THEN 0
                                ELSE 0
                            END
                        """))
                        conn.execute(text(f"ALTER TABLE users ALTER COLUMN {temp_col} SET DEFAULT 1"))
                        conn.execute(text("ALTER TABLE users DROP COLUMN is_active CASCADE"))
                        conn.execute(text(f"ALTER TABLE users RENAME COLUMN {temp_col} TO is_active"))
                    logger.info("Normalized users.is_active from boolean to integer via column rebuild")

            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT 1"))
                conn.execute(text("UPDATE users SET is_active = 0 WHERE is_active IS NULL"))

            final_user_cols_meta = {c['name']: c for c in inspect(engine).get_columns('users')}
            final_type_name = str((final_user_cols_meta.get('is_active') or {}).get('type') or '').lower()
            logger.info(
                "User runtime schema normalized | users.is_active final_type=%s final_nullable=%s final_default=%s",
                final_type_name or None,
                (final_user_cols_meta.get('is_active') or {}).get('nullable'),
                (final_user_cols_meta.get('is_active') or {}).get('default'),
            )
            if 'bool' in final_type_name:
                raise RuntimeError(f"users.is_active remains non-integer after migration: {final_type_name}")
        except Exception as e:
            logger.warning(f"Failed to normalize users.is_active to integer semantics: {e}")
            raise


def _ensure_script_progress_pipeline_scope_unique_index(*, is_postgres: bool) -> None:
    """Ensure scoped uniqueness for script_progress_pipeline_nodes under concurrency."""
    if not inspect(engine).has_table("script_progress_pipeline_nodes"):
        return

    dedupe_sql = """
    DELETE FROM script_progress_pipeline_nodes
    WHERE id IN (
        SELECT id
        FROM (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY project_id, episode_id, node_name, COALESCE(scene_id, ''), COALESCE(asset_type, '')
                    ORDER BY id DESC
                ) AS rn
            FROM script_progress_pipeline_nodes
        ) ranked
        WHERE ranked.rn > 1
    )
    """
    if is_postgres:
        create_unique_sql = """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_script_progress_pipeline_nodes_scope
        ON script_progress_pipeline_nodes (
            project_id,
            episode_id,
            node_name,
            COALESCE(scene_id, ''),
            COALESCE(asset_type, '')
        )
        """
    else:
        create_unique_sql = """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_script_progress_pipeline_nodes_scope
        ON script_progress_pipeline_nodes (
            project_id,
            episode_id,
            node_name,
            IFNULL(scene_id, ''),
            IFNULL(asset_type, '')
        )
        """

    with engine.begin() as conn:
        conn.execute(text(dedupe_sql))
        conn.execute(text(create_unique_sql))

    logger.info("Ensured script_progress_pipeline_nodes scoped unique index")

    inspector = inspect(engine)
    existing_columns = [c['name'] for c in inspector.get_columns('users')]

    columns_to_check = [
        ("is_active", "INTEGER DEFAULT 1"),
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

    if columns_to_add:
        with engine.begin() as conn:
            for col_name, col_type in columns_to_add:
                logger.info(f"Adding column {col_name}...")
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"Successfully added {col_name} (Standard SQL)")
                except Exception as e_pg:
                    logger.warning(f"Standard ADD COLUMN failed ({e_pg}). Trying SQLite syntax...")
                    try:
                        sqlite_type = col_type.replace("FALSE", "0").replace("TRUE", "1")
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {sqlite_type}"))
                        logger.info(f"Successfully added {col_name} (SQLite fallback)")
                    except Exception as e_sqlite:
                        logger.error(f"Failed to add {col_name} with SQLite syntax: {e_sqlite}")
                        raise e_sqlite


def _ensure_minimum_runtime_schema(*, is_postgres: bool) -> None:
    logger.info("Critical schema migration: start")

    try:
        inspector = inspect(engine)
        if inspector.has_table("users"):
            existing_user_cols = {c['name'] for c in inspector.get_columns('users')}
            if 'preferences' not in existing_user_cols:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSON"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN preferences JSON"))
                logger.info("Ensured users.preferences column")
    except Exception as e:
        logger.error(f"Failed to ensure users.preferences column: {e}")

    try:
        inspector = inspect(engine)
        if inspector.has_table("project_shares"):
            share_cols = {c['name'] for c in inspector.get_columns('project_shares')}
            with engine.begin() as conn:
                if 'role' not in share_cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE project_shares ADD COLUMN IF NOT EXISTS role VARCHAR"))
                    else:
                        conn.execute(text("ALTER TABLE project_shares ADD COLUMN role VARCHAR"))
                if 'permissions' not in share_cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE project_shares ADD COLUMN IF NOT EXISTS permissions JSON"))
                    else:
                        conn.execute(text("ALTER TABLE project_shares ADD COLUMN permissions JSON"))
                if is_postgres:
                    conn.execute(text("ALTER TABLE project_shares ALTER COLUMN role SET DEFAULT 'editor'"))
            logger.info("Ensured project_shares.role and project_shares.permissions columns")
    except Exception as e:
        logger.error(f"Failed to ensure project_shares review columns: {e}")

    _ensure_review_workflow_schema(is_postgres=is_postgres, apply_backfills=False)
    _ensure_user_runtime_schema(is_postgres=is_postgres)
    _ensure_user_group_schema(is_postgres=is_postgres)

    logger.info("Critical schema migration: complete")


def _ensure_transaction_schema(is_postgres: bool = False):
    from sqlalchemy import inspect, text
    from .session import engine
    from ..models.all_models import (
        TransactionHistory,
        TransactionAction,
        RechargePlan,
        PaymentOrder,
        InvoiceProfile,
        Invoice,
    )
    import logging
    logger = logging.getLogger(__name__)

    try:
        inspector = inspect(engine)

        # Ensure transaction_history columns
        if inspector.has_table("transaction_history"):
            cols = {c['name'] for c in inspector.get_columns("transaction_history")}
            with engine.begin() as conn:
                if "description" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN description VARCHAR"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN description VARCHAR"))
                    logger.info("Added description to transaction_history")
                if "target_group_id" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN IF NOT EXISTS target_group_id INTEGER"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN target_group_id INTEGER"))
                    logger.info("Added target_group_id to transaction_history")
                if "project_id" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                if "episode_id" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                    logger.info("Added project_id and episode_id to transaction_history")

        # Ensure billing / payment / invoice tables and columns
        for tname, tmodel in [
            ("recharge_plans", RechargePlan),
            ("payment_orders", PaymentOrder),
            ("invoice_profiles", InvoiceProfile),
            ("invoices", Invoice),
        ]:
            try:
                if not inspector.has_table(tname):
                    tmodel.__table__.create(bind=engine, checkfirst=True)
                    logger.info("Created %s table", tname)
                _ensure_missing_table_columns(tname, tmodel, is_postgres=is_postgres)
            except Exception as e:
                logger.error("Failed to ensure %s table/columns: %s", tname, e)

        # Ensure transaction_action columns
        if inspector.has_table("transaction_action"):
            cols = {c['name'] for c in inspector.get_columns("transaction_action")}
            with engine.begin() as conn:
                if "project_id" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                        
                if "episode_id" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                    logger.info("Added project_id and episode_id to transaction_action")
                    
    except Exception as e:
        logger.error(f"Failed to migrate transaction tables: {e}")

def check_and_migrate_tables(*, critical_only: bool = False):
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

        _ensure_minimum_runtime_schema(is_postgres=is_postgres)
        _ensure_transaction_schema(is_postgres=is_postgres)

        try:
            _ensure_missing_table_columns("system_api_settings", SystemAPISetting, is_postgres=is_postgres)
            try:
                _ensure_missing_table_columns("function_api_configs", models.FunctionAPIConfig, is_postgres=is_postgres)
            except Exception as e:
                logger.warning("Failed to ensure function_api_configs columns: %s", e)
        except Exception as e:
            logger.error(f"Failed to ensure critical system_api_settings columns: {e}")

        try:
            _ensure_missing_table_columns("users", User, is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure users columns: {e}")

        try:
            _ensure_missing_table_columns("assets", models.Asset, is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure assets columns: {e}")

        try:
            _ensure_missing_table_columns("entities", models.Entity, is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure entities columns: {e}")

        for tname, tmodel in [
            ("projects", models.Project),
            ("episodes", models.Episode),
            ("scenes", models.Scene),
            ("shots", models.Shot),
            ("script_segments", models.ScriptSegment),
            ("project_shares", models.ProjectShare),
            ("deletion_batches", DeletionBatch),
            ("deletion_batch_items", DeletionBatchItem),
            ("llm_call_logs", models.LLMCallLog),
            ("script_progress_scene_units", getattr(models, "ScriptProgressSceneUnit", None)),
            ("script_progress_pipeline_nodes", getattr(models, "ScriptProgressPipelineNode", None)),
            ("script_progress_issues", getattr(models, "ScriptProgressIssue", None)),
            ("market_intel_reports", getattr(models, "MarketIntelReport", None)),
            ("kb_works", getattr(models, "KbWork", None)),
            ("kb_entries", getattr(models, "KbEntry", None)),
            ("kb_entry_media", getattr(models, "KbEntryMedia", None)),
            ("kb_chunks", getattr(models, "KbChunk", None)),
            ("kb_eval_cases", getattr(models, "KbEvalCase", None)),
        ]:
            try:
                if tmodel is None:
                    continue
                if not inspector.has_table(tname):
                    tmodel.__table__.create(bind=engine, checkfirst=True)
                    logger.info(f"Created {tname} table")
                _ensure_missing_table_columns(tname, tmodel, is_postgres=is_postgres)
            except Exception as e:
                logger.error(f"Failed to ensure {tname} columns: {e}")

        try:
            _ensure_entities_episode_scoped_unique_indexes(is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure entity scoped unique indexes: {e}")

        try:
            _ensure_shots_project_episode_shot_id_unique_index(is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure shots project/episode/shot_id unique index: {e}")

        try:
            _ensure_scenes_episode_scene_no_unique_index(is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure scenes episode/scene_no unique index: {e}")

        try:
            _ensure_assets_normalized_url_unique_index(is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure assets normalized url unique index: {e}")

        try:
            _ensure_script_progress_pipeline_scope_unique_index(is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure script progress pipeline scoped unique index: {e}")

        try:
            _ensure_user_group_schema(is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure user group columns/tables: {e}")

        if critical_only:
            logger.info("Skipping non-critical legacy migrations during startup bootstrap")
            return

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

        # Ensure oss_provider_pools table exists for OSS admin/storage routing.
        try:
            if DeletedMedia is not None and not inspector.has_table("deleted_media"):
                DeletedMedia.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created deleted_media table")
            if OSSProviderPool is not None and not inspector.has_table("oss_provider_pools"):
                OSSProviderPool.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created oss_provider_pools table")
        except Exception as e:
            logger.error(f"Failed to ensure oss_provider_pools table: {e}")

        try:
            if OSSProviderPool is not None:
                _ensure_missing_table_columns("oss_provider_pools", OSSProviderPool, is_postgres=is_postgres)
        except Exception as e:
            logger.error(f"Failed to ensure oss_provider_pools columns: {e}")

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

        # Ensure dedicated wechat_pay_configs table exists (+ missing columns on upgrades)
        try:
            if not inspector.has_table("wechat_pay_configs"):
                WechatPayConfig.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created wechat_pay_configs table")
            else:
                _ensure_missing_table_columns(
                    "wechat_pay_configs", WechatPayConfig, is_postgres=is_postgres
                )
        except Exception as e:
            logger.error(f"Failed to ensure wechat_pay_configs table: {e}")

        # Ensure legacy system_api_billing_rules schema can support charge multiplier + supplier prices.
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
                supplier_cols = {
                    "supplier_price": ("DOUBLE PRECISION", "FLOAT"),
                    "supplier_price_input": ("DOUBLE PRECISION", "FLOAT"),
                    "supplier_price_output": ("DOUBLE PRECISION", "FLOAT"),
                    "supplier_currency": ("VARCHAR", "VARCHAR"),
                    "supplier_price_basis": ("VARCHAR", "VARCHAR"),
                }
                for col_name, (pg_type, sqlite_type) in supplier_cols.items():
                    if col_name in existing_rule_cols:
                        continue
                    col_type = pg_type if is_postgres else sqlite_type
                    if is_postgres:
                        conn.execute(text(f"ALTER TABLE system_api_billing_rules ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    else:
                        conn.execute(text(f"ALTER TABLE system_api_billing_rules ADD COLUMN {col_name} {col_type}"))
                    logger.info("Ensured system_api_billing_rules.%s column", col_name)
                try:
                    conn.execute(text("UPDATE system_api_billing_rules SET charge_multiplier = 2.0 WHERE charge_multiplier IS NULL OR charge_multiplier < 0"))
                except Exception as e:
                    logger.warning(f"Failed to backfill system_api_billing_rules.charge_multiplier: {e}")
                try:
                    # Backfill supplier CNY from legacy base credits when supplier columns are empty.
                    conn.execute(text("""
                        UPDATE system_api_billing_rules
                        SET supplier_currency = COALESCE(supplier_currency, 'CNY'),
                            supplier_price_basis = COALESCE(supplier_price_basis, 'money'),
                            supplier_price = CASE
                                WHEN supplier_price IS NULL AND COALESCE(billing_cost, 0) > 0 THEN CAST(billing_cost AS FLOAT) / 100.0
                                ELSE supplier_price
                            END,
                            supplier_price_input = CASE
                                WHEN supplier_price_input IS NULL AND COALESCE(billing_cost_input, 0) > 0 THEN CAST(billing_cost_input AS FLOAT) / 100.0
                                ELSE supplier_price_input
                            END,
                            supplier_price_output = CASE
                                WHEN supplier_price_output IS NULL AND COALESCE(billing_cost_output, 0) > 0 THEN CAST(billing_cost_output AS FLOAT) / 100.0
                                ELSE supplier_price_output
                            END
                    """))
                except Exception as e:
                    logger.warning(f"Failed to backfill system_api_billing_rules supplier prices: {e}")
        except Exception as e:
            logger.error(f"Failed to migrate system_api_billing_rules schema: {e}")

        # Ensure transaction_action table exists
        try:
            if not inspector.has_table("transaction_action"):
                TransactionAction.__table__.create(bind=engine, checkfirst=True)
                logger.info("Created transaction_action table")
            else:
                # Add project_id and episode_id to existing transaction_action table
                ta_cols = {c['name'] for c in inspector.get_columns('transaction_action')}
                with engine.begin() as conn:
                    if "project_id" not in ta_cols:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                        logger.info("Added project_id to transaction_action")
                    if "episode_id" not in ta_cols:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                        logger.info("Added episode_id to transaction_action")
        except Exception as e:
            logger.error(f"Failed to ensure/migrate transaction_action table: {e}")

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
                # Persisted pricing summary columns (model-level + provider-level)
                ("price_avg_cost", "INTEGER"),
                ("price_source", "VARCHAR"),
                ("price_min_cost", "INTEGER"),
                ("price_max_cost", "INTEGER"),
                ("price_sample_prices", "JSON"),
                ("price_updated_at", "VARCHAR"),
                ("provider_price_avg_cost", "INTEGER"),
                ("provider_price_source", "VARCHAR"),
                ("provider_price_min_cost", "INTEGER"),
                ("provider_price_max_cost", "INTEGER"),
                ("provider_price_sample_prices", "JSON"),
                ("provider_price_updated_at", "VARCHAR"),
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

                inspector = inspect(conn)
                existing_legacy_cols = {
                    c["name"] for c in inspector.get_columns("system_api_settings")
                } if inspector.has_table("system_api_settings") else set()

                for legacy_col in [
                    "billing_unit_type",
                    "billing_cost",
                    "billing_cost_input",
                    "billing_cost_output",
                    "has_granular_billing_rules",
                ]:
                    try:
                        # Skip drop when the legacy column is already absent.
                        if legacy_col not in existing_legacy_cols:
                            continue

                        if is_postgres:
                            conn.execute(text(f"ALTER TABLE system_api_settings DROP COLUMN IF EXISTS {legacy_col}"))
                        else:
                            conn.execute(text(f"ALTER TABLE system_api_settings DROP COLUMN {legacy_col}"))
                        existing_legacy_cols.discard(legacy_col)
                    except Exception as e:
                        logger.warning(f"Failed to drop legacy column system_api_settings.{legacy_col}: {e}")
        except Exception as e:
            logger.error(f"Failed to migrate system_api_settings schema: {e}")

        # --- Migrate user api_settings to explicit per-category binding ---
        try:
            inspector = inspect(engine)
            if inspector.has_table("api_settings"):
                existing_api_cols = {c["name"] for c in inspector.get_columns("api_settings")}
                with engine.begin() as conn:
                    if "system_api_id" not in existing_api_cols:
                        if is_postgres:
                            conn.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS system_api_id INTEGER"))
                        else:
                            conn.execute(text("ALTER TABLE api_settings ADD COLUMN system_api_id INTEGER"))
                    if "mode" not in existing_api_cols:
                        if is_postgres:
                            conn.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS mode VARCHAR"))
                        else:
                            conn.execute(text("ALTER TABLE api_settings ADD COLUMN mode VARCHAR"))
                    if "api_strategy" not in existing_api_cols:
                        if is_postgres:
                            conn.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS api_strategy VARCHAR"))
                        else:
                            conn.execute(text("ALTER TABLE api_settings ADD COLUMN api_strategy VARCHAR"))

                with SessionLocal() as session:
                    rows = session.query(APISetting).order_by(APISetting.id.desc()).all()
                    seen_keys = set()
                    dropped = 0
                    changed = 0

                    for row in rows:
                        category = str(getattr(row, "category", "") or "").strip() or "LLM"
                        if category != (getattr(row, "category", None) or ""):
                            row.category = category
                            changed += 1

                        row_mode = str(getattr(row, "mode", "") or "").strip().lower()
                        normalized_mode = row_mode or None
                        if normalized_mode != getattr(row, "mode", None):
                            row.mode = normalized_mode
                            changed += 1

                        row_strategy = str(getattr(row, "api_strategy", "") or "").strip().lower()
                        if row_strategy not in {"fixed", "smart_default", "low_price_replace"}:
                            row_strategy = "smart_default"
                        if row_strategy != str(getattr(row, "api_strategy", "") or ""):
                            row.api_strategy = row_strategy
                            changed += 1

                        system_api_id = int(getattr(row, "system_api_id", 0) or 0)

                        key = (int(getattr(row, "user_id", 0) or 0), category)
                        if key in seen_keys:
                            session.delete(row)
                            dropped += 1
                            continue
                        seen_keys.add(key)

                    if changed > 0 or dropped > 0:
                        session.commit()
                        logger.info(
                            "Migrated api_settings per-category binding | updated=%s dropped_duplicates=%s",
                            changed,
                            dropped,
                        )

                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_api_settings_user_category_idx ON api_settings (user_id, category)"))
                    else:
                        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_api_settings_user_category_idx ON api_settings (user_id, category)"))

                    # Remove deprecated user-scoped payload columns.
                    legacy_api_cols = ["name", "is_active", "provider", "api_key", "base_url", "model", "config"]
                    existing_api_cols = {c["name"] for c in inspect(conn).get_columns("api_settings")}
                    for legacy_col in legacy_api_cols:
                        if legacy_col not in existing_api_cols:
                            continue
                        try:
                            if is_postgres:
                                conn.execute(text(f"ALTER TABLE api_settings DROP COLUMN IF EXISTS {legacy_col}"))
                            else:
                                conn.execute(text(f"ALTER TABLE api_settings DROP COLUMN {legacy_col}"))
                            logger.info("Dropped deprecated api_settings column: %s", legacy_col)
                        except Exception as drop_err:
                            logger.warning("Failed to drop deprecated api_settings.%s: %s", legacy_col, drop_err)
        except Exception as e:
            logger.error(f"Failed to migrate api_settings schema: {e}")

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
                    extra_conditions = {"rule_kind": "base_pricing"}
                    ap_extra = ap.get("extra_conditions") if isinstance(ap.get("extra_conditions"), dict) else None
                    cfg_extra = cfg.get("billing_rule_extra_conditions") if isinstance(cfg.get("billing_rule_extra_conditions"), dict) else None
                    if cfg_extra:
                        extra_conditions.update(cfg_extra)
                    if ap_extra:
                        extra_conditions.update(ap_extra)
                    extra_conditions["rule_kind"] = "base_pricing"
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
                        extra_conditions=extra_conditions,
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

        _deactivate_legacy_duplicate_base_billing_rules()
        _backfill_system_api_retry_metadata()

        # Migrate legacy system-owned rows from api_settings into system_api_settings (opt-in only).
        if _should_manage_api_settings_on_init():
            try:
                with SessionLocal() as session:
                    system_count = session.query(SystemAPISetting).count()
                    if system_count == 0:
                        logger.info(
                            "Skipped legacy api_settings -> system_api_settings migration: "
                            "api_settings no longer stores provider/model/key payload fields"
                        )
            except Exception as e:
                logger.error(f"Failed migrating legacy system API settings: {e}")
        else:
            logger.info("Skip legacy API settings migration on init (AISTORY_MANAGE_API_SETTINGS_ON_INIT is disabled)")

        _ensure_user_runtime_schema(is_postgres=is_postgres)

        # --- Episodes table migrations ---
        try:
            inspector = inspect(engine)
            existing_episode_columns = [c['name'] for c in inspector.get_columns('episodes')]
            episode_columns_to_check = [
                ("ai_scene_analysis_result", "TEXT"),
                ("ai_scene_analysis_scene_markdown", "TEXT"),
                ("ai_entity_design_result", "TEXT"),
                ("ai_scene_analysis_subject_index", "TEXT"),
                ("ai_scene_analysis_adaptation", "TEXT"),
                ("ai_stage_outputs", "TEXT"),
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

        try:
            inspector = inspect(engine)
            if inspector.has_table('script_progress_scene_units'):
                existing_scene_unit_columns = [c['name'] for c in inspector.get_columns('script_progress_scene_units')]
                if 'scene_markdown' not in existing_scene_unit_columns:
                    with engine.begin() as conn:
                        if engine.dialect.name == 'postgresql':
                            conn.execute(text("ALTER TABLE script_progress_scene_units ADD COLUMN IF NOT EXISTS scene_markdown TEXT"))
                        else:
                            conn.execute(text("ALTER TABLE script_progress_scene_units ADD COLUMN scene_markdown TEXT"))
                    logger.info("Ensured script_progress_scene_units.scene_markdown exists")
        except Exception as e:
            logger.error(f"script_progress_scene_units migration failed: {e}")

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
            entity_cols_to_add = []
            if 'generation_prompt_cn' not in existing_entity_columns:
                entity_cols_to_add.append(('generation_prompt_cn', 'TEXT'))
            if 'video_url' not in existing_entity_columns:
                entity_cols_to_add.append(('video_url', 'TEXT'))
            if 'audio_url' not in existing_entity_columns:
                entity_cols_to_add.append(('audio_url', 'TEXT'))
            for col_name, col_type in entity_cols_to_add:
                with engine.begin() as conn:
                    if engine.dialect.name == 'postgresql':
                        conn.execute(text(f"ALTER TABLE entities ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    else:
                        conn.execute(text(f"ALTER TABLE entities ADD COLUMN {col_name} {col_type}"))
                logger.info(f"Ensured entities.{col_name} exists")
        except Exception as e:
            logger.error(f"Failed to migrate entities table: {e}")

        # Ensure core performance indexes are always present at startup.
        try:
            _ensure_core_performance_indexes()
        except Exception as e:
            logger.error(f"Failed to ensure core performance indexes: {e}")
        
    except Exception as e:
        logger.critical(f"Migration CRITICAL FAILURE: {e}")
        if critical_only:
            raise

def init_api_settings(db):
    # No-op: user api_settings rows are now lightweight bindings to system_api_settings.
    # Defaults are seeded by selection helpers based on system task defaults.
    del db
    logger.info("Skip legacy init_api_settings: api_settings now stores only user/category -> system_api_id mapping")


def cleanup_api_settings_active_conflicts(db):
    """
    Ensure only one API setting row per (user_id, category).
    Keeps newest row and deletes older duplicates.
    Safe to run repeatedly.
    """
    rows = db.query(APISetting).order_by(
        APISetting.user_id.asc(),
        APISetting.category.asc(),
        APISetting.id.desc(),
    ).all()

    seen = set()
    changed = 0

    for row in rows:
        key = (row.user_id, row.category or "LLM")
        if key in seen:
            db.delete(row)
            changed += 1
        else:
            seen.add(key)

    if changed > 0:
        db.commit()
        logger.info(f"API settings cleanup: deleted {changed} duplicate rows.")
    else:
        logger.info("API settings cleanup: no duplicate rows found.")


def normalize_grsai_user_api_settings(db):
    """No-op: api_settings no longer stores provider/model/base_url fields."""
    return None


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

        if row_category == "image":
            has_oss_id = bool(str(cfg.get("oss-id") or cfg.get("oss_id") or cfg.get("ossId") or "").strip())
            current_oss_path = str(cfg.get("oss-path") or cfg.get("oss_path") or cfg.get("ossPath") or "").strip()
            has_oss_path = bool(current_oss_path)
            oss_path_changed = False
            if not has_oss_id:
                cfg["oss-id"] = "69c890a3a0a438550965e9ff"
            if not has_oss_path:
                cfg["oss-path"] = "file/images/{yyyymm}/{user_id}"
                oss_path_changed = True
            elif "{yyyymm}" not in current_oss_path and current_oss_path in {
                "file/images",
                "file/images/{user_id}",
            }:
                # Align legacy grsai direct-write paths with OSS yyyymm layout.
                cfg["oss-path"] = "file/images/{yyyymm}/{user_id}"
                oss_path_changed = True
            if (not has_oss_id) or oss_path_changed:
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

        config_payload = {}
        if item["category"] == "Image":
            config_payload = {
                "endpoint": (
                    grsai_nano_banana_endpoint
                    if "nano-banana" in item["name"]
                    else grsai_gpt_image_endpoint
                ),
                "oss-id": "69c890a3a0a438550965e9ff",
                "oss-path": "file/images/{yyyymm}/{user_id}",
            }
        elif item["category"] == "Video" and "sora-2" in item["name"]:
            config_payload = {"endpoint": grsai_sora2_endpoint}
        elif item["category"] == "Video" and "veo" in item["name"]:
            config_payload = {"endpoint": grsai_veo_endpoint}

        db.add(SystemAPISetting(
            name=f"Grsai {item['name']}",
            category=item["category"],
            provider=grsai_provider,
            api_key=shared_api_key,
            base_url=grsai_base_url,
            model=item["model"],
            modality=item.get("modality"),
            config=config_payload,
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
        _kie_item("Kie Gemini Omni Video", "Video", "gemini-omni-video", "text-to-video,image-to-video,video-to-video,audio-to-video"),
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

    # Seed NukoAi video adapter models (names are account-specific; these match a common SD2.0 lineup).
    nukoai_provider = "nukoai"
    nukoai_base_url = "https://www.nukoai.com/api/ext/v1"
    from app.services.modality_utils import migrate_legacy_modality_string

    nukoai_model_items = [
        ("NukoAi SD 2.0 720P_官转", "SD 2.0 720P_官转"),
        ("NukoAi SD2.0 480P", "SD2.0 480P"),
        ("NukoAi SD2.0 720P", "SD2.0 720P"),
        ("NukoAi SD2.0 Fast 480P", "SD2.0 Fast 480P"),
        ("NukoAi SD2.0 Fast 720P", "SD2.0 Fast 720P"),
    ]
    existing_nukoai_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == nukoai_provider,
        SystemAPISetting.category == "Video",
    ).all()
    existing_nukoai_models = {
        str(row.model or "").strip().lower()
        for row in existing_nukoai_rows
    }
    nukoai_shared_api_key = ""
    for row in existing_nukoai_rows:
        if (row.api_key or "").strip():
            nukoai_shared_api_key = row.api_key.strip()
            break

    nukoai_added = 0
    for display_name, model_name in nukoai_model_items:
        key = str(model_name or "").strip().lower()
        if not key or key in existing_nukoai_models:
            continue
        db.add(SystemAPISetting(
            name=display_name,
            category="Video",
            provider=nukoai_provider,
            api_key=nukoai_shared_api_key,
            base_url=nukoai_base_url,
            model=model_name,
            base_model="seedance-2",
            modality=migrate_legacy_modality_string("text-to-video,image-to-video"),
            config={
                "provider_api_key_strategy": "random",
                "poll_interval_seconds": 4,
                "poll_timeout_seconds": 600,
                "endpoint": f"{nukoai_base_url}/videos",
                "query_endpoint": f"{nukoai_base_url}/videos",
                "poll_only": True,
                "notes": "NukoAi poll-only. Confirm model via GET /models for this account.",
            },
            is_active=False,
        ))
        existing_nukoai_models.add(key)
        nukoai_added += 1

    if nukoai_added > 0:
        db.commit()
        logger.info("Seeded %s nukoai video models into system_api_settings", nukoai_added)
    else:
        logger.info("System nukoai video settings already initialized")

    # Unify legacy NukoAi provider spellings (nokuai/nokoai/...) -> nukoai.
    try:
        aliases = {
            "nokoai",
            "nokuai",
            "nuko",
            "noko",
            "noku",
            "nuko ai",
            "noko ai",
            "noku ai",
        }
        updated = 0
        for row in db.query(SystemAPISetting).filter(SystemAPISetting.provider.isnot(None)).all():
            raw = str(row.provider or "").strip().lower()
            if raw in aliases:
                row.provider = "nukoai"
                updated += 1

        try:
            from sqlalchemy import func as sa_func

            canonical = db.query(ProviderKeyPool).filter(ProviderKeyPool.provider == "nukoai").first()
            alias_rows = (
                db.query(ProviderKeyPool)
                .filter(sa_func.lower(sa_func.trim(ProviderKeyPool.provider)).in_(sorted(aliases)))
                .all()
            )
            for row in alias_rows:
                if canonical is None:
                    row.provider = "nukoai"
                    if not str(getattr(row, "provider_alias", "") or "").strip():
                        row.provider_alias = "NukoAi"
                    canonical = row
                    updated += 1
                    continue
                existing_keys = []
                for src in (getattr(canonical, "api_keys", None) or [], getattr(row, "api_keys", None) or []):
                    if isinstance(src, list):
                        existing_keys.extend([str(k).strip() for k in src if str(k).strip()])
                    elif isinstance(src, str) and src.strip():
                        existing_keys.append(src.strip())
                canonical.api_keys = list(dict.fromkeys(existing_keys))
                if not str(getattr(canonical, "provider_alias", "") or "").strip():
                    canonical.provider_alias = str(getattr(row, "provider_alias", "") or "").strip() or "NukoAi"
                db.delete(row)
                updated += 1
            if canonical is not None and not str(getattr(canonical, "provider_alias", "") or "").strip():
                canonical.provider_alias = "NukoAi"
        except Exception as pool_err:
            logger.warning("Failed to canonicalize nukoai provider_key_pool: %s", pool_err)

        if updated > 0:
            db.commit()
            logger.info("Canonicalized %s NukoAi provider rows to nukoai", updated)
    except Exception as e:
        logger.warning(f"Failed to canonicalize NukoAi provider names: {e}")

    # Seed ShiShiKeJi (虾客漫) video adapter models — poll-only, license_key auth.
    shishikeji_provider = "shishikeji"
    shishikeji_base_url = "https://api.shishikeji.com"
    shishikeji_model_items = [
        ("ShiShiKeJi 星河 2.0", "xinghe-2.0"),
        ("ShiShiKeJi 星河 FAST", "xinghe-fast"),
        ("ShiShiKeJi 星河 2.0 12s", "xinghe-2.0-12s"),
        ("ShiShiKeJi 加班 2.0", "jiaban-2.0"),
        ("ShiShiKeJi 星喵 2.5", "xingmiao-2.5"),
    ]
    existing_ssk_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == shishikeji_provider,
        SystemAPISetting.category == "Video",
    ).all()
    existing_ssk_models = {
        str(row.model or "").strip().lower()
        for row in existing_ssk_rows
    }
    ssk_shared_api_key = ""
    for row in existing_ssk_rows:
        if (row.api_key or "").strip():
            ssk_shared_api_key = row.api_key.strip()
            break

    ssk_added = 0
    for display_name, model_name in shishikeji_model_items:
        key = str(model_name or "").strip().lower()
        if not key or key in existing_ssk_models:
            continue
        db.add(SystemAPISetting(
            name=display_name,
            category="Video",
            provider=shishikeji_provider,
            api_key=ssk_shared_api_key,
            base_url=shishikeji_base_url,
            model=model_name,
            base_model=model_name,
            modality=migrate_legacy_modality_string("image-to-video"),
            config={
                "provider_api_key_strategy": "random",
                "poll_interval_seconds": 4,
                "poll_timeout_seconds": 600,
                "endpoint": f"{shishikeji_base_url}/api/generate-video",
                "query_endpoint": f"{shishikeji_base_url}/api/task",
                "poll_only": True,
                "durations_seconds": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                "notes": "ShiShiKeJi poll-only. Auth via X-License-Key / license_key. Requires image/video/audio refs.",
            },
            is_active=False,
        ))
        existing_ssk_models.add(key)
        ssk_added += 1

    if ssk_added > 0:
        db.commit()
        logger.info("Seeded %s shishikeji video models into system_api_settings", ssk_added)
    else:
        logger.info("System shishikeji video settings already initialized")

    # Seed DdiMatuo video adapter models — poll-only Bearer auth.
    ddimatuo_provider = "ddimatuo"
    ddimatuo_base_url = "https://api.ddimatuo.top"
    ddimatuo_model_items = [
        ("DdiMatuo SD 2.0", "SD_2.0"),
    ]
    existing_ddi_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == ddimatuo_provider,
        SystemAPISetting.category == "Video",
    ).all()
    existing_ddi_models = {
        str(row.model or "").strip().lower()
        for row in existing_ddi_rows
    }
    ddi_shared_api_key = ""
    for row in existing_ddi_rows:
        if (row.api_key or "").strip():
            ddi_shared_api_key = row.api_key.strip()
            break

    # Migrate legacy sd2-pro rows to SD_2.0 contract.
    try:
        ddi_model_migrated = 0
        for row in existing_ddi_rows:
            legacy_model = str(row.model or "").strip()
            if legacy_model.lower() not in {"sd2-pro", "sd2_pro", "sd_2.0"}:
                continue
            if legacy_model == "SD_2.0" and str(row.base_model or "").strip() == "SD_2.0":
                continue
            row.model = "SD_2.0"
            row.base_model = "SD_2.0"
            if not str(row.name or "").strip() or "sd2" in str(row.name or "").lower():
                row.name = "DdiMatuo SD 2.0"
            cfg = row.config if isinstance(row.config, dict) else {}
            if not isinstance(cfg, dict):
                cfg = {}
            cfg = dict(cfg)
            cfg["resolution"] = "1080P"
            cfg["watermark"] = False
            cfg["auto_retry_busy"] = True
            cfg["mode"] = str(cfg.get("mode") or "omni_reference")
            cfg["endpoint"] = f"{ddimatuo_base_url}/v1/videos/generations"
            cfg["query_endpoint"] = f"{ddimatuo_base_url}/v1/videos"
            cfg["notes"] = (
                "DdiMatuo poll-only. POST /v1/videos/generations; model=SD_2.0; "
                "mode=omni_reference|first_last; duration 4-15; ratio; "
                "images/videos/audios; resolution 720P|1080P; watermark=false; "
                "Idempotency-Key reuse on timeout."
            )
            row.config = cfg
            ddi_model_migrated += 1
            existing_ddi_models.add("sd_2.0")
        if ddi_model_migrated > 0:
            db.commit()
            logger.info("Migrated %s ddimatuo rows to model=SD_2.0", ddi_model_migrated)
    except Exception as ddi_mig_err:
        logger.warning("Failed to migrate ddimatuo model to SD_2.0: %s", ddi_mig_err)

    ddi_added = 0
    for display_name, model_name in ddimatuo_model_items:
        key = str(model_name or "").strip().lower()
        if not key or key in existing_ddi_models:
            continue
        db.add(SystemAPISetting(
            name=display_name,
            category="Video",
            provider=ddimatuo_provider,
            api_key=ddi_shared_api_key,
            base_url=ddimatuo_base_url,
            model=model_name,
            base_model=model_name,
            modality=migrate_legacy_modality_string("text-to-video,image-to-video"),
            config={
                "provider_api_key_strategy": "random",
                "poll_interval_seconds": 5,
                "poll_timeout_seconds": 600,
                "endpoint": f"{ddimatuo_base_url}/v1/videos/generations",
                "query_endpoint": f"{ddimatuo_base_url}/v1/videos",
                "poll_only": True,
                "auto_retry_busy": True,
                "mode": "omni_reference",
                "resolution": "1080P",
                "watermark": False,
                "aspect_ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                "durations_seconds": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                "notes": (
                    "DdiMatuo poll-only. POST /v1/videos/generations; model=SD_2.0; "
                    "mode=omni_reference|first_last; duration 4-15; ratio; "
                    "images/videos/audios; resolution 720P|1080P; watermark=false; "
                    "Idempotency-Key reuse on timeout."
                ),
            },
            is_active=False,
        ))
        existing_ddi_models.add(key)
        ddi_added += 1

    # Force existing ddimatuo rows onto generations endpoint + 1080P default.
    try:
        ddi_cfg_updated = 0
        for row in existing_ddi_rows:
            cfg = row.config if isinstance(row.config, dict) else {}
            if not isinstance(cfg, dict):
                cfg = {}
            cfg = dict(cfg)
            changed = False
            endpoint = str(cfg.get("endpoint") or "").strip().rstrip("/")
            if not endpoint or endpoint.lower().endswith("/v1/videos"):
                cfg["endpoint"] = f"{ddimatuo_base_url}/v1/videos/generations"
                changed = True
            elif "/v1/videos/generations" not in endpoint.lower() and "ddimatuo" in endpoint.lower():
                cfg["endpoint"] = f"{ddimatuo_base_url}/v1/videos/generations"
                changed = True
            query_ep = str(cfg.get("query_endpoint") or "").strip().rstrip("/")
            if not query_ep or query_ep.lower().endswith("/generations"):
                cfg["query_endpoint"] = f"{ddimatuo_base_url}/v1/videos"
                changed = True
            raw_res = str(cfg.get("resolution") or "").strip()
            if raw_res.upper() != "1080P" or raw_res != "1080P":
                cfg["resolution"] = "1080P"
                changed = True
            if cfg.get("watermark") is not False:
                cfg["watermark"] = False
                changed = True
            if cfg.get("auto_retry_busy") is not True:
                cfg["auto_retry_busy"] = True
                changed = True
            if changed:
                row.config = cfg
                ddi_cfg_updated += 1
        if ddi_cfg_updated > 0:
            db.commit()
            logger.info("Updated %s ddimatuo rows to generations endpoint / 1080P", ddi_cfg_updated)
    except Exception as ddi_res_err:
        logger.warning("Failed to backfill ddimatuo endpoint/resolution: %s", ddi_res_err)

    if ddi_added > 0:
        db.commit()
        logger.info("Seeded %s ddimatuo video models into system_api_settings", ddi_added)
    else:
        logger.info("System ddimatuo video settings already initialized")

    # Seed Dubai / 星耀 video adapter — poll-only Bearer auth; /v1 stays on the path.
    # Public model names only (星耀视频 API 下游接入说明 2026-08-12).
    dubai_provider = "dubai"
    dubai_base_url = "https://dubai3000.xyz"
    dubai_default_ratios = ["16:9", "9:16", "1:1"]
    dubai_model_items = [
        ("星耀 sd-2-fast", "sd-2-fast", "seedance-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 sd-2-c3", "sd-2-c3", "seedance-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 sd-2.5 480p", "sd-2.5-480p", "seedance-2.5", "text-to-video,image-to-video", list(range(4, 31)), "480p", dubai_default_ratios, 9, 3, 3),
        ("星耀 sd-2.5 720p", "sd-2.5-720p", "seedance-2.5", "text-to-video,image-to-video", list(range(4, 31)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xinqi-2.0-fast-v4", "xinqi-2.0-fast-v4", "xinqi-2", "text-to-video,image-to-video", list(range(5, 16)), "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 xinqi-2.0-fast-v5", "xinqi-2.0-fast-v5", "xinqi-2", "text-to-video,image-to-video", list(range(10, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xinqi-2.0-v5", "xinqi-2.0-v5", "xinqi-2", "text-to-video,image-to-video", list(range(10, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 sora2", "sora2", "sora-2", "text-to-video,image-to-video", [4, 8, 12], "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 veo-fast", "veo-fast", "veo", "text-to-video,image-to-video", [4, 6, 8], "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 xingyao-2.0", "xingyao-2.0", "xingyao-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xingyao-2.0fast", "xingyao-2.0fast", "xingyao-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xingyao-2.0max", "xingyao-2.0max", "xingyao-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xingyao-2.0S", "xingyao-2.0S", "xingyao-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 官-sd-2.0-720p", "官-sd-2.0-720p", "seedance-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 官-sd-2.0-1080p", "官-sd-2.0-1080p", "seedance-2", "text-to-video,image-to-video", list(range(4, 16)), "1080p", dubai_default_ratios, 9, 3, 3),
        ("星耀 官-sd-2.0-2k", "官-sd-2.0-2k", "seedance-2", "text-to-video,image-to-video", list(range(4, 16)), "2k", dubai_default_ratios, 9, 3, 3),
        ("星耀 官-sd-2.0-4k", "官-sd-2.0-4k", "seedance-2", "text-to-video,image-to-video", list(range(4, 16)), "4k", dubai_default_ratios, 9, 3, 3),
        ("星耀 官-sd-2.0-fast-720p", "官-sd-2.0-fast-720p", "seedance-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xinghe-2.0", "xinghe-2.0", "xinghe-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xinghe-2.0s", "xinghe-2.0s", "xinghe-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 xinghe-2.0vip", "xinghe-2.0vip", "xinghe-2", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 3, 3),
        ("星耀 grok-imagine-1.0-video-16s", "grok-imagine-1.0-video-16s", "grok-imagine", "text-to-video,image-to-video", [16], "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 grok-imagine-video-1.5-fast", "grok-imagine-video-1.5-fast", "grok-imagine", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 grok-imagine-video-1.5-fast-16s", "grok-imagine-video-1.5-fast-16s", "grok-imagine", "text-to-video,image-to-video", [16], "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 grok-imagine-video-1.5-preview", "grok-imagine-video-1.5-preview", "grok-imagine", "text-to-video,image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 happyhorse t2v 720p", "happyhorse-1.0-t2v-720p", "happyhorse-1.0", "text-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 0, 0, 0),
        ("星耀 happyhorse t2v 1080p", "happyhorse-1.0-t2v-1080p", "happyhorse-1.0", "text-to-video", list(range(4, 16)), "1080p", dubai_default_ratios, 0, 0, 0),
        ("星耀 happyhorse i2v 720p", "happyhorse-1.0-i2v-720p", "happyhorse-1.0", "image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 1, 0, 0),
        ("星耀 happyhorse i2v 1080p", "happyhorse-1.0-i2v-1080p", "happyhorse-1.0", "image-to-video", list(range(4, 16)), "1080p", dubai_default_ratios, 1, 0, 0),
        ("星耀 happyhorse r2v 720p", "happyhorse-1.0-r2v-720p", "happyhorse-1.0", "image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 9, 0, 0),
        ("星耀 happyhorse r2v 1080p", "happyhorse-1.0-r2v-1080p", "happyhorse-1.0", "image-to-video", list(range(4, 16)), "1080p", dubai_default_ratios, 9, 0, 0),
        ("星耀 happyhorse video-edit 720p", "happyhorse-1.0-video-edit-720p", "happyhorse-1.0", "image-to-video", list(range(4, 16)), "720p", dubai_default_ratios, 5, 1, 0),
        ("星耀 happyhorse video-edit 1080p", "happyhorse-1.0-video-edit-1080p", "happyhorse-1.0", "image-to-video", list(range(4, 16)), "1080p", dubai_default_ratios, 5, 1, 0),
        ("星耀 PL-2.0-720p", "PL-2.0-720p", "PL-2.0", "text-to-video,image-to-video", [5, 10, 15], "720p", ["1:1", "16:9", "9:16", "4:3", "3:4"], 9, 3, 3),
    ]
    existing_dubai_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.provider == dubai_provider,
        SystemAPISetting.category == "Video",
    ).all()
    existing_dubai_models = {
        str(row.model or "").strip().lower()
        for row in existing_dubai_rows
    }
    dubai_shared_api_key = ""
    for row in existing_dubai_rows:
        if (row.api_key or "").strip():
            dubai_shared_api_key = row.api_key.strip()
            break

    # Legacy invented model id from the first adapter drop; map to the public name.
    try:
        dubai_migrated = 0
        for row in existing_dubai_rows:
            legacy = str(row.model or "").strip().lower()
            if legacy not in {"seedance-2.0-fast", "seedance-2.0"}:
                continue
            row.model = "sd-2-fast"
            row.base_model = "seedance-2"
            if not str(row.name or "").strip() or "seedance" in str(row.name or "").lower():
                row.name = "星耀 sd-2-fast"
            cfg = dict(row.config) if isinstance(row.config, dict) else {}
            cfg["durations_seconds"] = list(range(4, 16))
            cfg["resolution"] = "720p"
            cfg["aspect_ratios"] = list(dubai_default_ratios)
            row.config = cfg
            dubai_migrated += 1
            existing_dubai_models.discard(legacy)
            existing_dubai_models.add("sd-2-fast")
        if dubai_migrated > 0:
            db.commit()
            logger.info("Migrated %s dubai rows from seedance-2.0-fast to sd-2-fast", dubai_migrated)
    except Exception as dubai_mig_err:
        logger.warning("Failed to migrate dubai seedance-2.0-fast rows: %s", dubai_mig_err)

    dubai_added = 0
    for (
        display_name,
        model_name,
        base_model,
        modality_text,
        durations,
        resolution,
        ratios,
        max_images,
        max_videos,
        max_audios,
    ) in dubai_model_items:
        key = str(model_name or "").strip().lower()
        if not key or key in existing_dubai_models:
            continue
        poll_timeout = 900 if str(model_name).startswith("sd-2.5") else 600
        db.add(SystemAPISetting(
            name=display_name,
            category="Video",
            provider=dubai_provider,
            api_key=dubai_shared_api_key,
            base_url=dubai_base_url,
            model=model_name,
            base_model=base_model,
            modality=migrate_legacy_modality_string(modality_text),
            config={
                "provider_api_key_strategy": "random",
                "poll_interval_seconds": 4,
                "poll_timeout_seconds": poll_timeout,
                "endpoint": f"{dubai_base_url}/v1/videos",
                "query_endpoint": f"{dubai_base_url}/v1/videos",
                "poll_only": True,
                "aspect_ratios": list(ratios),
                "durations_seconds": list(durations),
                "resolution": resolution,
                "max_reference_images": int(max_images),
                "max_reference_videos": int(max_videos),
                "max_reference_audios": int(max_audios),
                "notes": (
                    "Dubai/星耀 poll-only. Base URL is the host only (no /v1). "
                    "POST /v1/videos; GET /v1/videos/{id}; GET /v1/videos/{id}/content. "
                    "JSON refs must be public http/https URLs; local files use multipart "
                    "reference_images / reference_audios / reference_videos. "
                    "Use public model names from GET /v1/models only."
                ),
            },
            is_active=False,
        ))
        existing_dubai_models.add(key)
        dubai_added += 1

    if dubai_added > 0:
        db.commit()
        logger.info("Seeded %s dubai video models into system_api_settings", dubai_added)
    else:
        logger.info("System dubai video settings already initialized")


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

