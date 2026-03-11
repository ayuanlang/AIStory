import json
import os
import sys
from typing import Any, Dict, List

from sqlalchemy import create_engine, inspect, text

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

from app.core.config import settings  # noqa: E402


WIDE_COLUMNS = [
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
    ("text_capabilities", "JSON"),
    ("image_capabilities", "JSON"),
    ("video_capabilities", "JSON"),
    ("digital_human_capabilities", "JSON"),
    ("voice_capabilities", "JSON"),
    ("music_capabilities", "JSON"),
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


def _safe_json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _pick_first_non_empty(*values: Any) -> Any:
    for v in values:
        if isinstance(v, list) and len(v) > 0:
            return v
        if isinstance(v, dict) and len(v) > 0:
            return v
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _to_int_or_none(value: Any) -> Any:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _to_float_or_none(value: Any) -> Any:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def migrate() -> None:
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1 and str(sys.argv[1]).strip():
        db_url = str(sys.argv[1]).strip()

    print(f"[migrate] connecting: {db_url}")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    is_postgres = engine.dialect.name == "postgresql"

    with engine.begin() as conn:
        existing = {c["name"] for c in inspector.get_columns("system_api_settings")}

        # 1) Add missing wide columns
        for col_name, col_type in WIDE_COLUMNS:
            if col_name in existing:
                continue
            if is_postgres:
                sql = f"ALTER TABLE system_api_settings ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            else:
                sql = f"ALTER TABLE system_api_settings ADD COLUMN {col_name} {col_type}"
            conn.execute(text(sql))
            print(f"[migrate] added system_api_settings.{col_name}")

        # 2) Data migration from modality JSON into wide columns
        rows = conn.execute(text("SELECT id, category, base_model, model, modality, supplier_info FROM system_api_settings")).mappings().all()

        updated = 0
        for row in rows:
            row_id = int(row["id"])
            category = str(row.get("category") or "")
            base_model = str(row.get("base_model") or "").strip() or str(row.get("model") or "").strip() or None

            modality = _safe_json_dict(row.get("modality"))
            supplier_info = _safe_json_dict(row.get("supplier_info"))
            pre = _safe_json_dict(supplier_info.get("llms_txt_preupdate"))
            doc_extracted = _safe_json_dict(pre.get("doc_extracted"))

            generation_modes = _pick_first_non_empty(modality.get("generation_modes"))
            input_formats = _pick_first_non_empty(modality.get("input_formats"))
            output_format = _pick_first_non_empty(modality.get("output_format"))
            supported_resolutions = _pick_first_non_empty(modality.get("supported_resolutions"), doc_extracted.get("supported_resolutions"))
            aspect_ratios = _pick_first_non_empty(modality.get("aspect_ratios"), doc_extracted.get("aspect_ratios"))
            max_images_per_call = _to_int_or_none(modality.get("max_images_per_call"))
            reference_image_limit = _pick_first_non_empty(modality.get("reference_image_limit"), doc_extracted.get("reference_image_limit"))
            reference_video_limit = _pick_first_non_empty(modality.get("reference_video_limit"))
            durations_seconds = _pick_first_non_empty(modality.get("durations_seconds"))
            max_duration = _to_int_or_none(_pick_first_non_empty(modality.get("max_duration"), doc_extracted.get("max_duration")))
            fps_options = _pick_first_non_empty(modality.get("fps_options"))
            has_audio = _pick_first_non_empty(modality.get("has_audio"), doc_extracted.get("has_audio"))
            mode_values = _pick_first_non_empty(modality.get("mode_values"), doc_extracted.get("mode_values"))

            text_capabilities = _pick_first_non_empty(modality.get("text_capabilities"))
            image_capabilities = _pick_first_non_empty(modality.get("image_capabilities"))
            video_capabilities = _pick_first_non_empty(modality.get("video_capabilities"))
            digital_human_capabilities = _pick_first_non_empty(modality.get("digital_human_capabilities"))
            voice_capabilities = _pick_first_non_empty(modality.get("voice_capabilities"))
            music_capabilities = _pick_first_non_empty(modality.get("music_capabilities"))

            # Billing hints may appear inside any capability object.
            cap_sources = [
                _safe_json_dict(text_capabilities),
                _safe_json_dict(image_capabilities),
                _safe_json_dict(video_capabilities),
                _safe_json_dict(digital_human_capabilities),
                _safe_json_dict(voice_capabilities),
                _safe_json_dict(music_capabilities),
            ]

            def pick_cap_key(key: str) -> Any:
                for cap in cap_sources:
                    if key in cap and cap.get(key) not in (None, "", [], {}):
                        return cap.get(key)
                return None

            pricing_unit = _pick_first_non_empty(pick_cap_key("pricing_unit"))
            token_billing_supported = _pick_first_non_empty(pick_cap_key("token_billing_supported"))
            input_token_price = _to_float_or_none(_pick_first_non_empty(pick_cap_key("input_token_price")))
            output_token_price = _to_float_or_none(_pick_first_non_empty(pick_cap_key("output_token_price")))
            per_resolution_price_map = _pick_first_non_empty(pick_cap_key("per_resolution_price_map"))
            per_duration_price_map = _pick_first_non_empty(pick_cap_key("per_duration_price_map"))
            has_tiered_pricing = _pick_first_non_empty(pick_cap_key("has_tiered_pricing"))
            free_quota = _pick_first_non_empty(pick_cap_key("free_quota"))
            currency = _pick_first_non_empty(pick_cap_key("currency"))

            if category == "LLM" and not text_capabilities:
                text_capabilities = {"supported": True}
            if category == "Image" and not image_capabilities:
                image_capabilities = {"supported": True}
            if category == "Video" and not video_capabilities:
                video_capabilities = {"supported": True}
            if category == "DigitalHuman" and not digital_human_capabilities:
                digital_human_capabilities = {"supported": True}
            if category == "Voice" and not voice_capabilities:
                voice_capabilities = {"supported": True}
            if category == "Music" and not music_capabilities:
                music_capabilities = {"supported": True}

            conn.execute(
                text(
                    """
                    UPDATE system_api_settings
                    SET generation_modes = :generation_modes,
                        input_formats = :input_formats,
                        output_format = :output_format,
                        supported_resolutions = :supported_resolutions,
                        aspect_ratios = :aspect_ratios,
                        max_images_per_call = :max_images_per_call,
                        reference_image_limit = :reference_image_limit,
                        reference_video_limit = :reference_video_limit,
                        durations_seconds = :durations_seconds,
                        max_duration = :max_duration,
                        fps_options = :fps_options,
                        has_audio = :has_audio,
                        mode_values = :mode_values,
                        text_capabilities = :text_capabilities,
                        image_capabilities = :image_capabilities,
                        video_capabilities = :video_capabilities,
                        digital_human_capabilities = :digital_human_capabilities,
                        voice_capabilities = :voice_capabilities,
                        music_capabilities = :music_capabilities,
                        pricing_unit = :pricing_unit,
                        token_billing_supported = :token_billing_supported,
                        input_token_price = :input_token_price,
                        output_token_price = :output_token_price,
                        per_resolution_price_map = :per_resolution_price_map,
                        per_duration_price_map = :per_duration_price_map,
                        has_tiered_pricing = :has_tiered_pricing,
                        free_quota = :free_quota,
                        currency = :currency,
                        base_model = COALESCE(base_model, :base_model)
                    WHERE id = :id
                    """
                ),
                {
                    "id": row_id,
                    "generation_modes": _json_value(_safe_json_list(generation_modes) if isinstance(generation_modes, list) else generation_modes),
                    "input_formats": _json_value(_safe_json_list(input_formats) if isinstance(input_formats, list) else input_formats),
                    "output_format": output_format,
                    "supported_resolutions": _json_value(_safe_json_list(supported_resolutions) if isinstance(supported_resolutions, list) else supported_resolutions),
                    "aspect_ratios": _json_value(_safe_json_list(aspect_ratios) if isinstance(aspect_ratios, list) else aspect_ratios),
                    "max_images_per_call": max_images_per_call,
                    "reference_image_limit": reference_image_limit,
                    "reference_video_limit": reference_video_limit,
                    "durations_seconds": _json_value(_safe_json_list(durations_seconds) if isinstance(durations_seconds, list) else durations_seconds),
                    "max_duration": max_duration,
                    "fps_options": _json_value(_safe_json_list(fps_options) if isinstance(fps_options, list) else fps_options),
                    "has_audio": has_audio,
                    "mode_values": _json_value(_safe_json_list(mode_values) if isinstance(mode_values, list) else mode_values),
                    "text_capabilities": _json_value(_safe_json_dict(text_capabilities) if isinstance(text_capabilities, dict) else text_capabilities),
                    "image_capabilities": _json_value(_safe_json_dict(image_capabilities) if isinstance(image_capabilities, dict) else image_capabilities),
                    "video_capabilities": _json_value(_safe_json_dict(video_capabilities) if isinstance(video_capabilities, dict) else video_capabilities),
                    "digital_human_capabilities": _json_value(_safe_json_dict(digital_human_capabilities) if isinstance(digital_human_capabilities, dict) else digital_human_capabilities),
                    "voice_capabilities": _json_value(_safe_json_dict(voice_capabilities) if isinstance(voice_capabilities, dict) else voice_capabilities),
                    "music_capabilities": _json_value(_safe_json_dict(music_capabilities) if isinstance(music_capabilities, dict) else music_capabilities),
                    "pricing_unit": pricing_unit,
                    "token_billing_supported": token_billing_supported,
                    "input_token_price": input_token_price,
                    "output_token_price": output_token_price,
                    "per_resolution_price_map": _json_value(_safe_json_dict(per_resolution_price_map) if isinstance(per_resolution_price_map, dict) else per_resolution_price_map),
                    "per_duration_price_map": _json_value(_safe_json_dict(per_duration_price_map) if isinstance(per_duration_price_map, dict) else per_duration_price_map),
                    "has_tiered_pricing": has_tiered_pricing,
                    "free_quota": free_quota,
                    "currency": currency,
                    "base_model": base_model,
                },
            )
            updated += 1

    print(f"[migrate] data backfill updated rows: {updated}")
    print("[migrate] done")


if __name__ == "__main__":
    migrate()
