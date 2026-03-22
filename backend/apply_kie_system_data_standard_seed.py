import csv
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text, and_, create_engine, select

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DICT_CSV = ROOT / "_kie_system_data_standard_dictionary.csv"
DEFAULT_MAP_CSV = ROOT / "_kie_system_to_model_enum_mapping.csv"

EXCLUDED_STANDARD_DIMENSIONS = {"MODEL_ID", "VOICE_ID"}

RULE_DESCRIPTIONS = {
    "exact": "标准值与API枚举值精确匹配",
    "semantic_token": "按语义token匹配",
    "semantic_alias": "按别名语义匹配",
    "nearest": "按数值绝对距离就近匹配",
    "nearest_lower": "按数值就近取不高于标准值",
    "nearest_ratio": "按比例最接近匹配",
    "semantic_prefix": "按前缀语义匹配",
    "fallback_baseline": "回退到基线枚举值",
    "fallback_min": "回退到最小可用枚举值",
}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _is_excluded(dimension: str) -> bool:
    return _clean(dimension).upper() in EXCLUDED_STANDARD_DIMENSIONS


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _read_csv_rows(path: Path) -> Iterable[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k: _clean(v) for k, v in (row or {}).items()}


def _resolve_input_path(raw: str, default_path: Path) -> Path:
    candidate = _clean(raw)
    if not candidate:
        return default_path
    p = Path(candidate)
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    return p


def _ensure_tables(metadata: MetaData):
    values = Table(
        "kie_system_data_standard_values",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("standard_dimension", String(100), nullable=False),
        Column("standard_value", String(255), nullable=False),
        Column("value_type", String(50), nullable=False),
        Column("definition", Text),
        Column("alias_values", Text),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        extend_existing=True,
    )

    mappings = Table(
        "kie_system_data_standard_mappings",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("provider", String(32), nullable=False),
        Column("model_key_inferred", String(255), nullable=False),
        Column("model_title", String(255)),
        Column("model_url", String(500)),
        Column("source_field", String(255), nullable=False),
        Column("source_enum_value", String(255), nullable=False),
        Column("standard_dimension", String(100), nullable=False),
        Column("standard_value", String(255), nullable=False),
        Column("confidence", String(16), nullable=False, default="LOW"),
        Column("note", Text),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        extend_existing=True,
    )

    rules = Table(
        "kie_system_data_standard_mapping_rules",
        metadata,
        Column("rule_code", String(64), primary_key=True),
        Column("rule_name", String(128)),
        Column("rule_description", Text),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        extend_existing=True,
    )

    metadata.create_all(bind=metadata.bind)
    return values, mappings, rules


def _upsert_value(conn, values, row: Dict[str, str], now_dt: datetime):
    dim = _clean(row.get("standard_dimension")).upper()
    val = _clean(row.get("standard_value"))
    if not dim or not val or _is_excluded(dim):
        return False

    stmt = select(values.c.id).where(
        and_(
            values.c.standard_dimension == dim,
            values.c.standard_value == val,
        )
    )
    existing_id = conn.execute(stmt).scalar()

    payload = {
        "standard_dimension": dim,
        "standard_value": val,
        "value_type": _clean(row.get("value_type")) or "enum",
        "definition": _clean(row.get("definition")),
        "alias_values": _clean(row.get("alias_values")),
        "is_active": True,
        "updated_at": now_dt,
    }

    if existing_id:
        conn.execute(values.update().where(values.c.id == existing_id).values(**payload))
    else:
        payload["created_at"] = now_dt
        conn.execute(values.insert().values(**payload))
    return True


def _upsert_mapping(conn, mappings, row: Dict[str, str], now_dt: datetime):
    dim = _clean(row.get("standard_dimension")).upper()
    if _is_excluded(dim):
        return False, ""

    payload = {
        "provider": _clean(row.get("provider")) or "kie",
        "model_key_inferred": _clean(row.get("model_key_inferred")),
        "model_title": _clean(row.get("model_title")),
        "model_url": _clean(row.get("model_url")),
        "source_field": _clean(row.get("source_field")),
        "source_enum_value": _clean(row.get("source_enum_value")),
        "standard_dimension": dim,
        "standard_value": _clean(row.get("standard_value")),
        "confidence": _clean(row.get("confidence")) or "LOW",
        "note": _clean(row.get("note")),
        "is_active": True,
        "updated_at": now_dt,
    }

    if not payload["model_key_inferred"] or not payload["source_field"] or not payload["source_enum_value"]:
        return False, ""

    existing_stmt = select(mappings.c.id).where(
        and_(
            mappings.c.provider == payload["provider"],
            mappings.c.model_key_inferred == payload["model_key_inferred"],
            mappings.c.source_field == payload["source_field"],
            mappings.c.source_enum_value == payload["source_enum_value"],
            mappings.c.standard_dimension == payload["standard_dimension"],
            mappings.c.standard_value == payload["standard_value"],
        )
    )
    existing_id = conn.execute(existing_stmt).scalar()

    if existing_id:
        conn.execute(mappings.update().where(mappings.c.id == existing_id).values(**payload))
    else:
        payload["created_at"] = now_dt
        conn.execute(mappings.insert().values(**payload))

    rule_code = ""
    if payload["note"].startswith("std_to_api:"):
        rule_code = payload["note"].split(":", 1)[1].strip()
    return True, rule_code


def _upsert_rule(conn, rules, rule_code: str, now_dt: datetime):
    rule_code = _clean(rule_code)
    if not rule_code:
        return

    desc = RULE_DESCRIPTIONS.get(rule_code, "映射规则")
    existing_stmt = select(rules.c.rule_code).where(rules.c.rule_code == rule_code)
    exists = conn.execute(existing_stmt).scalar()

    payload = {
        "rule_code": rule_code,
        "rule_name": rule_code,
        "rule_description": desc,
        "is_active": True,
        "updated_at": now_dt,
    }
    if exists:
        conn.execute(rules.update().where(rules.c.rule_code == rule_code).values(**payload))
    else:
        payload["created_at"] = now_dt
        conn.execute(rules.insert().values(**payload))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load KIE standard dictionary/mapping config into DB")
    parser.add_argument("--dict-csv", dest="dict_csv", default=str(DEFAULT_DICT_CSV), help="Path to standard dictionary CSV")
    parser.add_argument("--map-csv", dest="map_csv", default=str(DEFAULT_MAP_CSV), help="Path to system mapping CSV")
    args = parser.parse_args()

    dict_csv = _resolve_input_path(args.dict_csv, DEFAULT_DICT_CSV)
    map_csv = _resolve_input_path(args.map_csv, DEFAULT_MAP_CSV)

    if not dict_csv.exists() or not map_csv.exists():
        missing: List[str] = []
        if not dict_csv.exists():
            missing.append(str(dict_csv))
        if not map_csv.exists():
            missing.append(str(map_csv))
        raise FileNotFoundError(f"Missing required files: {', '.join(missing)}")

    engine = create_engine(settings.DATABASE_URL)
    metadata = MetaData()
    metadata.bind = engine
    values, mappings, rules = _ensure_tables(metadata)

    now_dt = _now_dt()
    values_count = 0
    mappings_count = 0
    rule_codes = set()

    with engine.begin() as conn:
        conn.execute(values.delete().where(values.c.standard_dimension.in_(sorted(EXCLUDED_STANDARD_DIMENSIONS))))
        conn.execute(mappings.delete().where(mappings.c.standard_dimension.in_(sorted(EXCLUDED_STANDARD_DIMENSIONS))))
        conn.execute(
            mappings.delete().where(
                and_(
                    mappings.c.provider == "kie",
                    ~mappings.c.standard_dimension.in_(sorted(EXCLUDED_STANDARD_DIMENSIONS)),
                )
            )
        )

        for row in _read_csv_rows(dict_csv):
            if _upsert_value(conn, values, row, now_dt):
                values_count += 1

        for row in _read_csv_rows(map_csv):
            ok, rule_code = _upsert_mapping(conn, mappings, row, now_dt)
            if ok:
                mappings_count += 1
            if rule_code:
                rule_codes.add(rule_code)

        for rc in sorted(rule_codes):
            _upsert_rule(conn, rules, rc, now_dt)

    print("[kie-standard-seed] completed")
    print(f"[kie-standard-seed] dict_csv={dict_csv}")
    print(f"[kie-standard-seed] map_csv={map_csv}")
    print(f"[kie-standard-seed] values_rows={values_count} mappings_rows={mappings_count} rules_rows={len(rule_codes)}")


if __name__ == "__main__":
    main()
