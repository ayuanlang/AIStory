import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "aistory.db"
CSV_PATH = ROOT / "_kie_all_models_param_matrix_vetted_clean.csv"


GENERIC_MODEL_WORDS = {
    "pro",
    "standard",
    "quality",
    "fast",
    "turbo",
    "master",
    "std",
    "default",
}


def normalize_category(raw: str) -> str:
    value = (raw or "").strip().lower()
    return {
        "chat": "LLM",
        "image": "Image",
        "video": "Video",
        "audio": "Voice",
        "voice": "Voice",
        "music": "Music",
        "tools": "Tools",
        "llm": "LLM",
    }.get(value, "Tools")


def split_values(raw: str) -> List[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    parts = re.split(r"[;,|]", text)
    out: List[str] = []
    seen = set()
    for p in parts:
        token = p.strip()
        if not token:
            continue
        if token.lower() in seen:
            continue
        seen.add(token.lower())
        out.append(token)
    return out


def parse_durations_seconds(raw: str) -> List[float]:
    text = str(raw or "")
    values: List[float] = []
    seen = set()
    for m in re.finditer(r"(\d+(?:\.\d+)?)", text):
        num = float(m.group(1))
        if num <= 0:
            continue
        key = round(num, 6)
        if key in seen:
            continue
        seen.add(key)
        values.append(num)
    return values


def parse_bool(raw: str) -> Optional[bool]:
    text = str(raw or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on", "supported"}:
        return True
    if text in {"0", "false", "no", "n", "off", "unsupported"}:
        return False
    return None


def parse_model_from_url(url: str) -> Optional[str]:
    text = str(url or "").strip()
    if not text:
        return None

    # Special mappings where KIE docs slug does not equal our DB model key.
    special_by_suffix = {
        "/market/kling/image-to-video.md": "kling-2.6/image-to-video",
        "/market/kling/text-to-video.md": "kling-2.6/text-to-video",
        "/market/kling/motion-control.md": "kling-2.6/motion-control",
        "/market/kling/kling-3-0.md": "kling-3.0/video",
        "/market/sora-2-pro-storyboard.md": "sora-2-pro-storyboard",
    }
    for suffix, mapped in special_by_suffix.items():
        if text.endswith(suffix):
            return mapped

    market = re.search(r"/market/([^/]+)/([^/.]+)\.md$", text)
    if market:
        return f"{market.group(1)}/{market.group(2)}"

    if text.endswith("/4o-image-api/generate-4-o-image.md"):
        return "gpt4o-image"
    if text.endswith("/flux-kontext-api/generate-or-edit-image.md"):
        return "flux-kontext-pro"
    if text.endswith("/runway-api/generate-ai-video.md"):
        return "runwayml/gen3a-turbo"
    if text.endswith("/runway-api/generate-aleph-video.md"):
        return "runwayml/gen3a-turbo"
    if text.endswith("/runway-api/extend-ai-video.md"):
        return "runwayml/gen3a-turbo"
    if text.endswith("/runway-api/extend-ai-video-callbacks.md"):
        return "runwayml/gen3a-turbo"

    return None


def normalize_free(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())


def model_fuzzy_keys(token: str) -> Set[str]:
    value = str(token or "").strip().lower()
    if not value:
        return set()
    keys = {normalize_free(value)}
    if "/" in value:
        parts = [p for p in value.split("/") if p]
        if parts:
            keys.add(normalize_free(parts[-1]))
        if len(parts) > 1:
            keys.add(normalize_free("/".join(parts[1:])))
    return {k for k in keys if k}


def candidate_models(row: Dict[str, str]) -> List[str]:
    candidates: List[str] = []

    model_raw = str(row.get("model") or "").strip()
    if model_raw and model_raw.lower() not in GENERIC_MODEL_WORDS:
        candidates.extend([m.strip() for m in model_raw.split(",") if m.strip()])

    by_url = parse_model_from_url(str(row.get("url") or ""))
    if by_url:
        candidates.append(by_url)

    expanded: List[str] = []
    for c in candidates:
        expanded.append(c)
        if "/" in c:
            tail = c.rsplit("/", 1)[-1].strip()
            if tail:
                expanded.append(tail)

    out: List[str] = []
    seen = set()
    for c in expanded:
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(system_api_settings)").fetchall()}
    required = {
        "image_size_values": "JSON",
        "quality_values": "JSON",
        "sound_supported": "BOOLEAN",
        "multi_shots_supported": "BOOLEAN",
    }
    for name, ctype in required.items():
        if name in cols:
            continue
        conn.execute(f"ALTER TABLE system_api_settings ADD COLUMN {name} {ctype}")


def merge_json_array(existing_raw: Optional[str], incoming: List) -> Optional[str]:
    if not incoming:
        return existing_raw
    existing: List = []
    if existing_raw:
        try:
            parsed = json.loads(existing_raw)
            if isinstance(parsed, list):
                existing = parsed
        except Exception:
            existing = []

    out = []
    seen = set()
    for item in existing + incoming:
        key = str(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return json.dumps(out, ensure_ascii=False)


def put_unique(index: Dict[Tuple[str, str], Optional[Dict]], key: Tuple[str, str], row: Dict) -> None:
    if key in index:
        index[key] = None
    else:
        index[key] = row


def build_index(conn: sqlite3.Connection) -> Dict[str, Dict]:
    rows = conn.execute(
        "SELECT id, category, name, model FROM system_api_settings WHERE lower(provider)='kie'"
    ).fetchall()

    by_category_model: Dict[Tuple[str, str], Dict] = {}
    by_model_global: Dict[str, Dict] = {}
    by_category_fuzzy_model: Dict[Tuple[str, str], Optional[Dict]] = {}
    by_fuzzy_model_global: Dict[str, Optional[Dict]] = {}
    by_category_fuzzy_name: Dict[Tuple[str, str], Optional[Dict]] = {}

    for row in rows:
        item = {
            "id": int(row[0]),
            "category": str(row[1] or "").strip(),
            "name": str(row[2] or "").strip(),
            "model": str(row[3] or ""),
        }
        category = str(row[1] or "").strip()
        model = str(row[3] or "").strip().lower()
        if not model:
            continue
        by_category_model[(category, model)] = item
        if model not in by_model_global:
            by_model_global[model] = item

        for fk in model_fuzzy_keys(model):
            put_unique(by_category_fuzzy_model, (category, fk), item)
            put_unique(by_fuzzy_model_global, fk, item)

        name_key = normalize_free(item["name"])
        if name_key:
            put_unique(by_category_fuzzy_name, (category, name_key), item)

    return {
        "by_category_model": by_category_model,
        "by_model_global": by_model_global,
        "by_category_fuzzy_model": by_category_fuzzy_model,
        "by_fuzzy_model_global": by_fuzzy_model_global,
        "by_category_fuzzy_name": by_category_fuzzy_name,
    }


def resolve_target(indexes: Dict[str, Dict], category: str, model_candidates: List[str], title: str) -> Optional[Dict]:
    by_category_model = indexes["by_category_model"]
    by_model_global = indexes["by_model_global"]
    by_category_fuzzy_model = indexes["by_category_fuzzy_model"]
    by_fuzzy_model_global = indexes["by_fuzzy_model_global"]
    by_category_fuzzy_name = indexes["by_category_fuzzy_name"]

    for m in model_candidates:
        hit = by_category_model.get((category, m.lower()))
        if hit:
            return hit
    for m in model_candidates:
        hit = by_model_global.get(m.lower())
        if hit:
            return hit

    for m in model_candidates:
        for fk in model_fuzzy_keys(m):
            hit = by_category_fuzzy_model.get((category, fk))
            if hit:
                return hit

    for m in model_candidates:
        for fk in model_fuzzy_keys(m):
            hit = by_fuzzy_model_global.get(fk)
            if hit:
                return hit

    title_key = normalize_free(title)
    if title_key:
        hit = by_category_fuzzy_name.get((category, title_key))
        if hit:
            return hit

    return None


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH}")
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None
    try:
        conn.execute("BEGIN")
        ensure_columns(conn)
        indexes = build_index(conn)

        updated = 0
        skipped = 0
        unmatched = []

        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            for row in rd:
                category = normalize_category(str(row.get("category") or ""))
                cands = candidate_models(row)
                if not cands:
                    skipped += 1
                    continue

                title = str(row.get("title") or "")
                target = resolve_target(indexes, category, cands, title)
                if not target:
                    unmatched.append((category, cands[0], title))
                    skipped += 1
                    continue

                sid = int(target["id"])
                current = conn.execute(
                    "SELECT supported_resolutions, aspect_ratios, durations_seconds, mode_values, image_size_values, quality_values, output_format, has_audio, sound_supported, multi_shots_supported FROM system_api_settings WHERE id=?",
                    (sid,),
                ).fetchone()

                resolutions = split_values(str(row.get("resolution") or ""))
                image_sizes = split_values(str(row.get("image_size") or ""))
                ratios = split_values(str(row.get("aspect_ratio") or ""))
                durations = parse_durations_seconds(str(row.get("duration") or ""))
                modes = split_values(str(row.get("mode") or ""))
                qualities = split_values(str(row.get("quality") or ""))
                output_format = str(row.get("output_format") or "").strip() or None
                sound = parse_bool(str(row.get("sound") or ""))
                multi_shots = parse_bool(str(row.get("multi_shots") or ""))

                supported_resolutions = merge_json_array(current[0], resolutions)
                aspect_ratios = merge_json_array(current[1], ratios)
                durations_seconds = merge_json_array(current[2], durations)
                # mode_values is governed by backend/align_kie_mode_values.py using curated mode catalog.
                # Do not merge from the broad matrix here, otherwise stale/generic values are reintroduced.
                mode_values = current[3]
                image_size_values = merge_json_array(current[4], image_sizes)
                quality_values = merge_json_array(current[5], qualities)

                max_duration = None
                if durations:
                    max_duration = int(max(durations))

                next_output_format = output_format or current[6]
                next_has_audio = current[7]
                next_sound_supported = current[8]
                next_multi_shots_supported = current[9]

                if sound is not None:
                    next_sound_supported = int(sound)
                    next_has_audio = int(sound)
                if multi_shots is not None:
                    next_multi_shots_supported = int(multi_shots)

                conn.execute(
                    """
                    UPDATE system_api_settings
                    SET supported_resolutions=?,
                        aspect_ratios=?,
                        durations_seconds=?,
                        max_duration=COALESCE(?, max_duration),
                        mode_values=?,
                        image_size_values=?,
                        quality_values=?,
                        output_format=?,
                        has_audio=?,
                        sound_supported=?,
                        multi_shots_supported=?
                    WHERE id=?
                    """,
                    (
                        supported_resolutions,
                        aspect_ratios,
                        durations_seconds,
                        max_duration,
                        mode_values,
                        image_size_values,
                        quality_values,
                        next_output_format,
                        next_has_audio,
                        next_sound_supported,
                        next_multi_shots_supported,
                        sid,
                    ),
                )
                updated += 1

        conn.execute("COMMIT")
        print(f"DB: {DB_PATH}")
        print(f"CSV: {CSV_PATH}")
        print(f"Updated rows: {updated}")
        print(f"Skipped rows: {skipped}")
        print(f"Unmatched sample (first 20): {unmatched[:20]}")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
