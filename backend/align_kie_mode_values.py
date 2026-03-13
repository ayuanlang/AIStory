import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "aistory.db"
MODE_CATALOG_PATH = ROOT / "_kie_field_mode_like_values_catalog_clean.csv"


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


def parse_model_from_url(url: str) -> Optional[str]:
    text = str(url or "").strip()
    if not text:
        return None

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


def resolve_target(indexes: Dict[str, Dict], category: str, model: Optional[str], title: str) -> Optional[Dict]:
    by_category_model = indexes["by_category_model"]
    by_model_global = indexes["by_model_global"]
    by_category_fuzzy_model = indexes["by_category_fuzzy_model"]
    by_fuzzy_model_global = indexes["by_fuzzy_model_global"]
    by_category_fuzzy_name = indexes["by_category_fuzzy_name"]

    candidates = [model] if model else []
    candidates = [c for c in candidates if c]

    for m in candidates:
        hit = by_category_model.get((category, str(m).lower()))
        if hit:
            return hit
    for m in candidates:
        hit = by_model_global.get(str(m).lower())
        if hit:
            return hit
    for m in candidates:
        for fk in model_fuzzy_keys(str(m)):
            hit = by_category_fuzzy_model.get((category, fk))
            if hit:
                return hit
    for m in candidates:
        for fk in model_fuzzy_keys(str(m)):
            hit = by_fuzzy_model_global.get(fk)
            if hit:
                return hit

    title_key = normalize_free(title)
    if title_key:
        hit = by_category_fuzzy_name.get((category, title_key))
        if hit:
            return hit

    return None


def split_allowed_values(raw: str) -> List[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    out: List[str] = []
    seen = set()
    for item in text.split(";"):
        token = str(item).strip().lower()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH}")
    if not MODE_CATALOG_PATH.exists():
        raise FileNotFoundError(f"Mode catalog not found: {MODE_CATALOG_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None

    try:
        conn.execute("BEGIN")
        indexes = build_index(conn)

        mode_map_by_id: Dict[int, List[str]] = {}
        unresolved: List[Tuple[str, str]] = []

        with MODE_CATALOG_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if str(row.get("field") or "").strip().lower() != "mode":
                    continue

                category = normalize_category("video")
                title = str(row.get("title") or "").strip()
                model = parse_model_from_url(str(row.get("url") or ""))
                values = split_allowed_values(str(row.get("allowed_values") or ""))
                if not values:
                    continue

                target = resolve_target(indexes, category, model, title)
                if not target:
                    unresolved.append((title, model or ""))
                    continue

                sid = int(target["id"])
                merged = []
                seen = set(mode_map_by_id.get(sid, []))
                for v in mode_map_by_id.get(sid, []):
                    merged.append(v)
                for v in values:
                    if v in seen:
                        continue
                    seen.add(v)
                    merged.append(v)
                mode_map_by_id[sid] = merged

        rows = conn.execute(
            "SELECT id, mode_values FROM system_api_settings WHERE lower(provider)='kie'"
        ).fetchall()

        changed = 0
        cleared = 0
        aligned = 0

        for sid, old_raw in rows:
            sid = int(sid)
            if sid in mode_map_by_id:
                new_raw = json.dumps(mode_map_by_id[sid], ensure_ascii=False)
                if (old_raw or "") != new_raw:
                    conn.execute(
                        "UPDATE system_api_settings SET mode_values=? WHERE id=?",
                        (new_raw, sid),
                    )
                    changed += 1
                aligned += 1
            else:
                if old_raw is not None and str(old_raw).strip() != "":
                    conn.execute(
                        "UPDATE system_api_settings SET mode_values=NULL WHERE id=?",
                        (sid,),
                    )
                    changed += 1
                    cleared += 1

        conn.execute("COMMIT")

        print(f"DB: {DB_PATH}")
        print(f"Mode catalog: {MODE_CATALOG_PATH}")
        print(f"Models with curated mode_values: {aligned}")
        print(f"Rows cleared (stale mode_values removed): {cleared}")
        print(f"Total rows changed: {changed}")
        print(f"Unresolved mode rows: {len(unresolved)}")
        if unresolved:
            print(f"Unresolved sample: {unresolved[:10]}")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
