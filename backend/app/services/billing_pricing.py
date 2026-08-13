"""Canonical pricing program for AIStory billing.

Layers:
1) Supplier price (CNY, money) — persisted on billing rules
2) Base credits — ceil(supplier_cny * 100), cached on billing_cost*
3) User charge — base * charge_multiplier (odds) * quantity(by unit_type) * runtime multipliers
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional, Tuple


TOKEN_UNIT_TYPES = {"per_token", "per_1k_tokens", "per_million_tokens"}
ALLOWED_UNIT_TYPES = {
    "per_call",
    "per_second",
    "per_minute",
    "per_token",
    "per_1k_tokens",
    "per_million_tokens",
}


def safe_non_negative_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        parsed = float(value)
        if not math.isfinite(parsed) or parsed < 0:
            return float(default)
        return float(parsed)
    except Exception:
        return float(default)


def safe_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return int(default)
        parsed = float(value)
        if not math.isfinite(parsed) or parsed < 0:
            return int(default)
        return int(math.floor(parsed))
    except Exception:
        return int(default)


def normalize_unit_type(value: Any, default: str = "per_call") -> str:
    unit = str(value or default).strip() or default
    return unit if unit in ALLOWED_UNIT_TYPES else default


def normalize_charge_multiplier(value: Any, default: float = 2.0) -> float:
    parsed = safe_non_negative_float(value, default)
    if parsed < 0:
        return float(default)
    return float(parsed if parsed > 0 else default)


def normalize_currency(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return "CNY"
    aliases = {"RMB": "CNY", "CNH": "CNY"}
    return aliases.get(text, text)


def normalize_price_basis(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "money"
    aliases = {
        "amount": "money",
        "cash": "money",
        "currency": "money",
        "point": "points",
        "credit": "points",
        "credits": "points",
        "score": "points",
    }
    return aliases.get(text, text)


def supplier_cny_to_base_credits(value: Any) -> int:
    """Convert supplier CNY money to raw system credits (1 credit = 0.01 CNY)."""
    return max(0, int(math.ceil(safe_non_negative_float(value) * 100.0)))


def base_credits_to_supplier_cny(value: Any) -> float:
    """Inverse display helper: credits to CNY (not used for charging)."""
    return round(float(safe_non_negative_int(value)) / 100.0, 6)


def apply_function_billing_adjustment(
    api_cost: Any,
    *,
    multiplier: Any = 1.0,
    add_credits: Any = 0,
) -> Dict[str, Any]:
    """
    Apply function-level user billing on top of rule-odds result.

    final = ceil(api_cost * multiplier) + add_credits
    Missing/invalid multiplier -> 1.0; missing/invalid add -> 0.
    """
    base = max(0, safe_non_negative_int(api_cost, 0))
    try:
        if multiplier is None or multiplier == "":
            mult = 1.0
        else:
            mult = float(multiplier)
            if not math.isfinite(mult) or mult < 0:
                mult = 1.0
    except Exception:
        mult = 1.0
    add = max(0, safe_non_negative_int(add_credits, 0))
    scaled = int(math.ceil(float(base) * float(mult))) if base > 0 and mult > 0 else 0
    if base > 0 and mult == 0:
        scaled = 0
    final = max(0, int(scaled) + int(add))
    return {
        "api_cost_before": int(base),
        "function_multiplier": float(mult),
        "function_add_credits": int(add),
        "api_cost_after": int(final),
    }


def apply_odds_to_credits(base_credits: Any, charge_multiplier: Any, runtime_multiplier: Any = 1.0) -> int:
    """User credits = ceil(base * odds * runtime)."""
    amount = safe_non_negative_float(base_credits)
    odds = normalize_charge_multiplier(charge_multiplier, default=2.0)
    runtime = safe_non_negative_float(runtime_multiplier, 1.0)
    if runtime <= 0:
        runtime = 1.0
    charged = amount * odds * runtime
    return max(0, int(math.ceil(charged))) if charged > 0 else 0


def extract_supplier_pricing(source: Any) -> Dict[str, Any]:
    get = source.get if isinstance(source, dict) else (lambda k, d=None: getattr(source, k, d))
    price = get("supplier_price")
    price_in = get("supplier_price_input")
    price_out = get("supplier_price_output")
    return {
        "supplier_price": None if price is None or price == "" else safe_non_negative_float(price),
        "supplier_price_input": None if price_in is None or price_in == "" else safe_non_negative_float(price_in),
        "supplier_price_output": None if price_out is None or price_out == "" else safe_non_negative_float(price_out),
        "supplier_currency": normalize_currency(get("supplier_currency")),
        "supplier_price_basis": normalize_price_basis(get("supplier_price_basis")),
    }


def derive_base_credits_from_supplier(supplier: Dict[str, Any]) -> Dict[str, int]:
    return {
        "cost": supplier_cny_to_base_credits(supplier.get("supplier_price")),
        "cost_input": supplier_cny_to_base_credits(supplier.get("supplier_price_input")),
        "cost_output": supplier_cny_to_base_credits(supplier.get("supplier_price_output")),
    }


def resolve_rule_base_credits(rule: Any) -> Dict[str, Any]:
    unit_type = normalize_unit_type(
        getattr(rule, "billing_unit_type", None) if not isinstance(rule, dict) else rule.get("billing_unit_type")
    )
    supplier = extract_supplier_pricing(rule)
    has_any_supplier = any(
        supplier.get(k) is not None
        for k in ("supplier_price", "supplier_price_input", "supplier_price_output")
    )
    if has_any_supplier and supplier.get("supplier_price_basis") == "money" and supplier.get("supplier_currency") == "CNY":
        derived = derive_base_credits_from_supplier(supplier)
        return {
            "unit_type": unit_type,
            "cost": derived["cost"],
            "cost_input": derived["cost_input"],
            "cost_output": derived["cost_output"],
            "source": "supplier_price",
            "supplier": supplier,
        }

    get = rule.get if isinstance(rule, dict) else (lambda k, d=None: getattr(rule, k, d))
    return {
        "unit_type": unit_type,
        "cost": safe_non_negative_int(get("billing_cost", 0), 0),
        "cost_input": safe_non_negative_int(get("billing_cost_input", 0), 0),
        "cost_output": safe_non_negative_int(get("billing_cost_output", 0), 0),
        "source": "billing_cost_cache",
        "supplier": supplier,
    }



VIDEO_RESOLUTION_TIERS = ("480p", "720p", "1080p", "4k")

# Official Ark Seedance output pixel tables (resolution × aspect → WxH).
# Source: Volcengine / Seedance published size matrix (2.0 / 1.5 Pro / 1.0).
SEEDANCE_ASPECT_RATIOS = ("16:9", "4:3", "1:1", "3:4", "9:16", "21:9")

SEEDANCE_PIXEL_TABLES: Dict[str, Dict[str, Dict[str, Tuple[int, int]]]] = {
    # Seedance 2.0 series (standard / fast / mini share the same size matrix;
    # 1080p unavailable on Fast/Mini is a capability constraint, not a size remap).
    "2.0": {
        "480p": {
            "16:9": (864, 496),
            "4:3": (752, 560),
            "1:1": (640, 640),
            "3:4": (560, 752),
            "9:16": (496, 864),
            "21:9": (992, 432),
        },
        "720p": {
            "16:9": (1280, 720),
            "4:3": (1112, 834),
            "1:1": (960, 960),
            "3:4": (834, 1112),
            "9:16": (720, 1280),
            "21:9": (1470, 630),
        },
        "1080p": {
            "16:9": (1920, 1080),
            "4:3": (1664, 1248),
            "1:1": (1440, 1440),
            "3:4": (1248, 1664),
            "9:16": (1080, 1920),
            "21:9": (2206, 946),
        },
        "4k": {
            "16:9": (3840, 2160),
            "4:3": (3326, 2494),
            "1:1": (2880, 2880),
            "3:4": (2494, 3326),
            "9:16": (2160, 3840),
            "21:9": (4398, 1886),
        },
    },
    # Seedance 1.5 Pro shares the 2.0 matrix for 480p/720p/1080p (no 4k).
    "1.5": {
        "480p": {
            "16:9": (864, 496),
            "4:3": (752, 560),
            "1:1": (640, 640),
            "3:4": (560, 752),
            "9:16": (496, 864),
            "21:9": (992, 432),
        },
        "720p": {
            "16:9": (1280, 720),
            "4:3": (1112, 834),
            "1:1": (960, 960),
            "3:4": (834, 1112),
            "9:16": (720, 1280),
            "21:9": (1470, 630),
        },
        "1080p": {
            "16:9": (1920, 1080),
            "4:3": (1664, 1248),
            "1:1": (1440, 1440),
            "3:4": (1248, 1664),
            "9:16": (1080, 1920),
            "21:9": (2206, 946),
        },
    },
    # Seedance 1.0 series
    "1.0": {
        "480p": {
            "16:9": (864, 480),
            "4:3": (736, 544),
            "1:1": (640, 640),
            "3:4": (544, 736),
            "9:16": (480, 864),
            "21:9": (960, 416),
        },
        "720p": {
            "16:9": (1248, 704),
            "4:3": (1120, 832),
            "1:1": (960, 960),
            "3:4": (832, 1120),
            "9:16": (704, 1248),
            "21:9": (1504, 640),
        },
        "1080p": {
            "16:9": (1920, 1088),
            "4:3": (1664, 1248),
            "1:1": (1440, 1440),
            "3:4": (1248, 1664),
            "9:16": (1088, 1920),
            "21:9": (2176, 928),
        },
    },
}


def normalize_seedance_aspect_ratio(aspect_ratio: Any) -> str:
    raw = str(aspect_ratio or "").strip().lower().replace(" ", "")
    if not raw:
        return "16:9"
    aliases = {
        "landscape": "16:9",
        "portrait": "9:16",
        "square": "1:1",
        "16/9": "16:9",
        "9/16": "9:16",
        "4/3": "4:3",
        "3/4": "3:4",
        "21/9": "21:9",
        "2.35:1": "21:9",
        "2.35/1": "21:9",
    }
    if raw in aliases:
        return aliases[raw]
    if raw in SEEDANCE_ASPECT_RATIOS:
        return raw
    m = re.match(r"^(\d+(?:\.\d+)?)[:/](\d+(?:\.\d+)?)$", raw)
    if not m:
        return "16:9"
    try:
        left = float(m.group(1))
        right = float(m.group(2))
    except Exception:
        return "16:9"
    if left <= 0 or right <= 0:
        return "16:9"
    target = left / right
    best = "16:9"
    best_delta = float("inf")
    for candidate in SEEDANCE_ASPECT_RATIOS:
        cw, ch = candidate.split(":")
        try:
            ratio = float(cw) / float(ch)
        except Exception:
            continue
        delta = abs(ratio - target)
        if delta < best_delta:
            best_delta = delta
            best = candidate
    return best


def resolve_seedance_model_family(*identity_parts: Any) -> str:
    """
    Return Seedance size-matrix family: '2.0' | '1.5' | '1.0'.
    Defaults to 2.0 when Seedance is implied without a clear older version.
    """
    text = " ".join(str(part or "") for part in identity_parts).strip().lower()
    if not text:
        return "2.0"
    if any(marker in text for marker in ("1.5", "1-5", "1_5", "seedance15", "seedance-1.5", "seedance_1.5")):
        return "1.5"
    if any(marker in text for marker in ("seedance-1-0", "seedance_1_0", "seedance1.0", "seedance-1.0", "seedance_1.0")):
        return "1.0"
    # "seedance-1" / "seedance 1" without 1.5 → 1.0
    if re.search(r"seedance[\s_\-]*1([^.\d]|$)", text) and "1.5" not in text and "1-5" not in text:
        return "1.0"
    if "seedance" in text or "ark" in text:
        return "2.0"
    return "2.0"


def resolve_seedance_pixel_dims(
    aspect_ratio: Any = None,
    resolution: Any = None,
    *,
    model_family: Any = None,
    model: Any = None,
    provider: Any = None,
) -> Optional[Tuple[int, int]]:
    """Look up official Seedance WxH for family + resolution tier + aspect ratio."""
    family = str(model_family or "").strip()
    if family not in SEEDANCE_PIXEL_TABLES:
        family = resolve_seedance_model_family(provider, model, model_family)
    tier = resolve_video_resolution_tier(resolution=resolution)
    if not tier:
        raw_tier = str(resolution or "").strip().lower().replace(" ", "")
        if raw_tier in {"480", "720", "1080", "4k"}:
            tier = "4k" if raw_tier == "4k" else f"{raw_tier}p"
    if not tier:
        return None
    aspect = normalize_seedance_aspect_ratio(aspect_ratio)
    table = SEEDANCE_PIXEL_TABLES.get(family) or SEEDANCE_PIXEL_TABLES["2.0"]
    tier_row = table.get(tier)
    if not tier_row:
        # Unsupported combo for this family (e.g. 4k on 1.5/1.0) → fall back to 2.0 size if present.
        tier_row = (SEEDANCE_PIXEL_TABLES.get("2.0") or {}).get(tier)
    if not tier_row:
        return None
    dims = tier_row.get(aspect)
    if not dims:
        dims = tier_row.get("16:9")
    if not dims:
        return None
    try:
        width = int(dims[0])
        height = int(dims[1])
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return (width, height)


# KIE FX: ~200 KIE credits / 1 USD, USD:CNY = 1:7
# => 1 KIE credit = 7/200 CNY = 0.035 CNY = 3.5 system credits (1 credit = 0.01 CNY)
KIE_CREDITS_PER_USD = 200.0
USD_TO_CNY_RATE = 7.0
KIE_CREDIT_TO_CNY = USD_TO_CNY_RATE / KIE_CREDITS_PER_USD  # 0.035
KIE_TO_SYSTEM_CREDIT_RATIO = KIE_CREDIT_TO_CNY * 100.0  # 3.5

# Official KIE Seedance 2 published rates (KIE credits / second)
DEFAULT_KIE_SEEDANCE_SECOND_RATES_KIE = {
    "480p": {"with_video_input": 11.5, "without_video_input": 19.0},
    "720p": {"with_video_input": 25.0, "without_video_input": 41.0},
    "1080p": {"with_video_input": 62.0, "without_video_input": 102.0},
    "4k": {"with_video_input": 128.0, "without_video_input": 208.0},
}

# Same table folded to supplier CNY / second for Pricing Rules (money basis)
DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES = {
    tier: {
        "with_video_input": round(float(row["with_video_input"]) * KIE_CREDIT_TO_CNY, 6),
        "without_video_input": round(float(row["without_video_input"]) * KIE_CREDIT_TO_CNY, 6),
    }
    for tier, row in DEFAULT_KIE_SEEDANCE_SECOND_RATES_KIE.items()
}

# Backward-compatible alias (now CNY/s). Prefer DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES.
DEFAULT_KIE_SEEDANCE_SECOND_RATES = DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES


# Official KIE Gemini Omni Video published rates (KIE credits).
# Without video: flat by output duration bucket × resolution.
# With video: flat per generation by resolution (duration ignored by provider).
KIE_OMNI_DURATION_BUCKETS = (4, 6, 8, 10)
KIE_OMNI_RESOLUTION_TIERS = ("720p", "1080p", "4k")
DEFAULT_KIE_OMNI_DURATION_RATES_KIE = {
    "without_video_input": {
        "720p": {"4": 63.0, "6": 84.0, "8": 105.0, "10": 126.0},
        "1080p": {"4": 63.0, "6": 84.0, "8": 105.0, "10": 126.0},
        "4k": {"4": 147.0, "6": 168.0, "8": 189.0, "10": 210.0},
    },
    "with_video_input": {
        "720p": 168.0,
        "1080p": 168.0,
        "4k": 252.0,
    },
}


# RunningHub SparkVideo 2.0 resolution tiers (API + native variants)
SPARKVIDEO_RESOLUTION_TIERS = (
    "480p",
    "720p",
    "1080p_native",
    "4k_native",
    "1080p",
    "2k",
    "4k",
)

# Published CNY / second rates (supplier money)
DEFAULT_SPARKVIDEO_SECOND_CNY_RATES = {
    "480p": {"without_video_input": 0.6, "with_video_input": 0.4},
    "720p": {"without_video_input": 1.2, "with_video_input": 0.8},
    "1080p_native": {"without_video_input": 3.0, "with_video_input": 2.0},
    "4k_native": {"without_video_input": 6.0, "with_video_input": 4.0},
    # Upscale from 720p native
    "1080p": {
        "without_video_input": 1.48,
        "with_video_base": 0.8,
        "with_video_addon": 0.28,
        "pricing_kind": "upscale",
    },
    "2k": {
        "without_video_input": 1.62,
        "with_video_base": 0.8,
        "with_video_addon": 0.42,
        "pricing_kind": "upscale",
    },
    "4k": {
        "without_video_input": 1.83,
        "with_video_base": 0.8,
        "with_video_addon": 0.63,
        "pricing_kind": "upscale",
    },
}

# With reference video: billable_seconds = max(input+output, min_by_output[output])
SPARKVIDEO_MIN_BILLABLE_BY_OUTPUT = {
    4: 7,
    5: 9,
    6: 10,
    7: 12,
    8: 14,
    9: 15,
    10: 17,
    11: 19,
    12: 20,
    13: 22,
    14: 24,
    15: 25,
}


def resolve_video_resolution_tier(
    width: Any = None,
    height: Any = None,
    resolution: Any = None,
) -> Optional[str]:
    """Map explicit label or pixel size to Seedance-style resolution tier."""
    text = str(resolution or "").strip().lower().replace(" ", "")
    aliases = {
        "480": "480p", "480p": "480p", "p480": "480p", "sd": "480p",
        "720": "720p", "720p": "720p", "p720": "720p", "hd": "720p",
        "1080": "1080p", "1080p": "1080p", "p1080": "1080p", "fhd": "1080p",
        "2160": "4k", "2160p": "4k", "4k": "4k", "uhd": "4k", "3840": "4k",
    }
    if text in aliases:
        return aliases[text]
    m = re.search(r"(480|720|1080|2160|3840)\s*p?", text)
    if m:
        return aliases.get(m.group(1))

    try:
        w = int(float(width)) if width not in (None, "") else 0
    except Exception:
        w = 0
    try:
        h = int(float(height)) if height not in (None, "") else 0
    except Exception:
        h = 0
    if w <= 0 and h <= 0:
        return None

    # Prefer nearest official Seedance size (handles non-canonical short edges like 496/834).
    try:
        best_tier = None
        best_delta = None
        for family_table in SEEDANCE_PIXEL_TABLES.values():
            for tier_key, aspect_map in (family_table or {}).items():
                for dims in (aspect_map or {}).values():
                    try:
                        tw, th = int(dims[0]), int(dims[1])
                    except Exception:
                        continue
                    if tw <= 0 or th <= 0:
                        continue
                    delta = abs(tw - w) + abs(th - h)
                    if best_delta is None or delta < best_delta:
                        best_delta = delta
                        best_tier = tier_key
        if best_tier and best_delta is not None and best_delta <= 48:
            return best_tier
    except Exception:
        pass

    short_edge = min(v for v in (w, h) if v > 0)
    # Seedance official short-edge bands (approx): 480p<=640, 720p<=960, 1080p<=1440, else 4k
    if short_edge <= 640:
        return "480p"
    if short_edge <= 960:
        return "720p"
    if short_edge <= 1440:
        return "1080p"
    return "4k"



def _pick_tier_rate(tier_val: Dict[str, Any], keys: list) -> Optional[float]:
    for k in keys:
        if k in tier_val and tier_val.get(k) is not None and tier_val.get(k) != "":
            try:
                v = float(tier_val.get(k))
                if math.isfinite(v) and v >= 0:
                    return v
            except Exception:
                continue
    return None


def normalize_resolution_rate_map(raw: Any) -> Dict[str, Dict[str, Optional[float]]]:
    """Normalize {tier: {with_video_input, without_video_input}} numeric rate map."""
    out: Dict[str, Dict[str, Optional[float]]] = {}
    if not isinstance(raw, dict):
        return out
    for tier_key, tier_val in raw.items():
        tier = resolve_video_resolution_tier(resolution=tier_key) or str(tier_key or "").strip().lower()
        if tier not in VIDEO_RESOLUTION_TIERS:
            continue
        if not isinstance(tier_val, dict):
            continue
        with_rate = _pick_tier_rate(tier_val, ["with_video_input", "with", "input"])
        without_rate = _pick_tier_rate(tier_val, ["without_video_input", "without", "output"])
        if with_rate is None and without_rate is None:
            continue
        out[tier] = {
            "with_video_input": with_rate,
            "without_video_input": without_rate,
        }
    return out


def normalize_video_token_resolution_rates(raw: Any) -> Dict[str, Dict[str, Optional[float]]]:
    """Normalize {tier: {with_video_input, without_video_input}} CNY / MTok map."""
    return normalize_resolution_rate_map(raw)


def normalize_video_second_resolution_rates(raw: Any) -> Dict[str, Dict[str, Optional[float]]]:
    """Normalize {tier: {with_video_input, without_video_input}} KIE credits / second map."""
    return normalize_resolution_rate_map(raw)


def kie_credits_to_cny(value: Any) -> float:
    """Convert KIE credits to CNY (1 USD ~= 200 KIE, USD:CNY = 1:7)."""
    return max(0.0, safe_non_negative_float(value) * float(KIE_CREDIT_TO_CNY))


def kie_credits_to_system_credits(value: Any) -> float:
    """Convert KIE credits to system credits (may be fractional before ceil)."""
    return max(0.0, kie_credits_to_cny(value) * 100.0)


def resolve_kie_omni_duration_bucket(duration: Any) -> int:
    """Snap duration seconds to nearest published Omni bucket (4/6/8/10)."""
    seconds = safe_non_negative_float(duration, 4.0)
    if seconds <= 0:
        return 4
    return min(KIE_OMNI_DURATION_BUCKETS, key=lambda bucket: abs(float(bucket) - seconds))


def resolve_kie_omni_resolution_tier(
    width: Any = None,
    height: Any = None,
    resolution: Any = None,
) -> str:
    """Map label/pixels to Omni resolution tier; default 720p."""
    tier = resolve_video_resolution_tier(width, height, resolution)
    if tier in KIE_OMNI_RESOLUTION_TIERS:
        return str(tier)
    text = str(resolution or "").strip().lower().replace(" ", "")
    if text in {"720", "720p", "p720", "hd"}:
        return "720p"
    if text in {"1080", "1080p", "p1080", "fhd"}:
        return "1080p"
    if text in {"2160", "2160p", "4k", "uhd", "3840"}:
        return "4k"
    return "720p"


def normalize_video_duration_kie_credit_rates(raw: Any) -> Dict[str, Any]:
    """
    Normalize Omni-style duration matrix:
      {
        without_video_input: {tier: {duration: kie_credits}},
        with_video_input: {tier: kie_credits}  # flat per generation
      }
    """
    src = raw if isinstance(raw, dict) else {}
    out: Dict[str, Any] = {"without_video_input": {}, "with_video_input": {}}

    without_src = src.get("without_video_input") if isinstance(src.get("without_video_input"), dict) else {}
    with_src = src.get("with_video_input") if isinstance(src.get("with_video_input"), dict) else {}

    for tier in KIE_OMNI_RESOLUTION_TIERS:
        tier_row = without_src.get(tier) if isinstance(without_src.get(tier), dict) else {}
        if not tier_row and isinstance(src.get(tier), dict):
            nested = src.get(tier) or {}
            if any(str(k).isdigit() for k in nested.keys()):
                tier_row = nested
        bucket_map: Dict[str, float] = {}
        for bucket in KIE_OMNI_DURATION_BUCKETS:
            key = str(bucket)
            val = safe_non_negative_float(
                tier_row.get(key, tier_row.get(bucket, tier_row.get(f"{bucket}s"))),
                -1.0,
            )
            if val >= 0:
                bucket_map[key] = float(val)
        if bucket_map:
            out["without_video_input"][tier] = bucket_map

        with_val = with_src.get(tier)
        if with_val is None and isinstance(src.get(tier), dict):
            with_val = (src.get(tier) or {}).get("with_video_input")
        parsed_with = safe_non_negative_float(with_val, -1.0)
        if parsed_with >= 0:
            out["with_video_input"][tier] = float(parsed_with)

    if not out["without_video_input"] and not out["with_video_input"]:
        return {}
    return out


def estimate_kie_omni_duration_credits(
    *,
    rates: Any = None,
    resolution_tier: Any = None,
    has_video_input: bool = False,
    output_duration: Any = None,
    width: Any = None,
    height: Any = None,
    resolution: Any = None,
) -> Dict[str, Any]:
    """Look up Omni KIE credits and convert to system base credits."""
    rate_map = normalize_video_duration_kie_credit_rates(rates)
    if not rate_map:
        rate_map = normalize_video_duration_kie_credit_rates(DEFAULT_KIE_OMNI_DURATION_RATES_KIE)

    tier = resolve_kie_omni_resolution_tier(
        width,
        height,
        resolution_tier or resolution,
    )
    duration_bucket = resolve_kie_omni_duration_bucket(output_duration)

    kie_credits = 0.0
    rate_branch = "without_video_input"
    if has_video_input:
        with_map = rate_map.get("with_video_input") if isinstance(rate_map.get("with_video_input"), dict) else {}
        if tier in with_map:
            kie_credits = float(with_map[tier])
            rate_branch = "with_video_input"
        elif "1080p" in with_map and tier in {"720p", "1080p"}:
            kie_credits = float(with_map["1080p"])
            rate_branch = "with_video_input"
        elif "720p" in with_map and tier in {"720p", "1080p"}:
            kie_credits = float(with_map["720p"])
            rate_branch = "with_video_input"
    if kie_credits <= 0:
        without_map = rate_map.get("without_video_input") if isinstance(rate_map.get("without_video_input"), dict) else {}
        tier_buckets = without_map.get(tier) if isinstance(without_map.get(tier), dict) else {}
        if not tier_buckets and tier in {"720p", "1080p"}:
            tier_buckets = without_map.get("720p") if isinstance(without_map.get("720p"), dict) else {}
            if not tier_buckets:
                tier_buckets = without_map.get("1080p") if isinstance(without_map.get("1080p"), dict) else {}
        kie_credits = safe_non_negative_float(tier_buckets.get(str(duration_bucket)), 0.0)
        rate_branch = "without_video_input"

    system_credits = float(kie_credits_to_system_credits(kie_credits))
    return {
        "resolution_tier": tier,
        "duration_bucket": int(duration_bucket),
        "has_video_input": bool(has_video_input),
        "rate_branch": rate_branch,
        "kie_credits": float(kie_credits),
        "system_credits": float(system_credits),
        "estimation_method": "video_duration_kie_omni",
    }


def resolve_sparkvideo_resolution_tier(
    width: Any = None,
    height: Any = None,
    resolution: Any = None,
) -> Optional[str]:
    """Map SparkVideo labels including native vs upscale and 2k."""
    text = str(resolution or "").strip().lower().replace(" ", "").replace("-", "_")
    aliases = {
        "480": "480p", "480p": "480p", "p480": "480p",
        "720": "720p", "720p": "720p", "p720": "720p",
        "1080p_native": "1080p_native",
        "1080pnative": "1080p_native",
        "native1080p": "1080p_native",
        "4k_native": "4k_native",
        "4knative": "4k_native",
        "native4k": "4k_native",
        "2160p_native": "4k_native",
        "1080": "1080p", "1080p": "1080p", "p1080": "1080p",
        "2k": "2k", "1440": "2k", "1440p": "2k", "p1440": "2k",
        "2160": "4k", "2160p": "4k", "4k": "4k", "uhd": "4k", "3840": "4k",
    }
    # Chinese "原生" markers often arrive url-encoded or as unicode in labels
    if "原生" in str(resolution or "") or "native" in text:
        if "1080" in text:
            return "1080p_native"
        if "4k" in text or "2160" in text:
            return "4k_native"
    if text in aliases:
        return aliases[text]
    m = re.search(r"(480|720|1080|1440|2160|3840|2k|4k)\s*p?", text)
    if m:
        token = m.group(1)
        return aliases.get(token) or aliases.get(f"{token}p")
    try:
        w = int(float(width)) if width not in (None, "") else 0
    except Exception:
        w = 0
    try:
        h = int(float(height)) if height not in (None, "") else 0
    except Exception:
        h = 0
    if w <= 0 and h <= 0:
        return None
    short_edge = min(v for v in (w, h) if v > 0)
    if short_edge <= 480:
        return "480p"
    if short_edge <= 720:
        return "720p"
    if short_edge <= 1080:
        return "1080p"
    if short_edge <= 1440:
        return "2k"
    return "4k"


def normalize_sparkvideo_second_cny_rates(raw: Any) -> Dict[str, Dict[str, Any]]:
    """Normalize SparkVideo CNY/s rate map (supports upscale base+addon)."""
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return out
    for tier_key, tier_val in raw.items():
        tier = resolve_sparkvideo_resolution_tier(resolution=tier_key) or str(tier_key or "").strip().lower()
        if tier not in SPARKVIDEO_RESOLUTION_TIERS:
            continue
        if not isinstance(tier_val, dict):
            continue
        row: Dict[str, Any] = {}
        without = _pick_tier_rate(tier_val, ["without_video_input", "without", "output", "no_ref"])
        with_flat = _pick_tier_rate(tier_val, ["with_video_input", "with", "input", "with_ref"])
        with_base = _pick_tier_rate(tier_val, ["with_video_base", "base", "base_rate"])
        with_addon = _pick_tier_rate(tier_val, ["with_video_addon", "addon", "addon_rate", "upscale_addon"])
        kind = str(tier_val.get("pricing_kind") or "").strip().lower()
        if without is not None:
            row["without_video_input"] = without
        if with_flat is not None:
            row["with_video_input"] = with_flat
        if with_base is not None:
            row["with_video_base"] = with_base
        if with_addon is not None:
            row["with_video_addon"] = with_addon
        if kind:
            row["pricing_kind"] = kind
        elif with_base is not None or with_addon is not None:
            row["pricing_kind"] = "upscale"
        if not row:
            continue
        out[tier] = row
    return out


def normalize_sparkvideo_min_billable_by_output(raw: Any) -> Dict[int, int]:
    """Normalize min-billable table. Empty/missing => no floor (KIE CNY/s path)."""
    out: Dict[int, int] = {}
    src = raw if isinstance(raw, dict) else {}
    if not src:
        return {}
    for k, v in src.items():
        try:
            out_key = int(float(k))
            out_val = int(float(v))
        except Exception:
            continue
        if out_key > 0 and out_val > 0:
            out[out_key] = out_val
    return out


def resolve_sparkvideo_min_billable_seconds(output_duration: Any, table: Any = None) -> float:
    out_s = safe_non_negative_float(output_duration, 0.0)
    mapping = normalize_sparkvideo_min_billable_by_output(table)
    if out_s <= 0:
        return 0.0
    key = int(round(out_s))
    if key in mapping:
        return float(mapping[key])
    keys = sorted(mapping.keys())
    if not keys:
        return out_s
    if key < keys[0]:
        return float(mapping[keys[0]])
    if key > keys[-1]:
        return float(mapping[keys[-1]])
    # nearest neighbor
    nearest = min(keys, key=lambda x: abs(x - key))
    return float(mapping[nearest])


def resolve_sparkvideo_billable_seconds(
    *,
    output_duration: Any,
    input_duration: Any = 0,
    has_video_input: bool = False,
    min_billable_table: Any = None,
) -> Dict[str, float]:
    output_s = safe_non_negative_float(output_duration, 0.0)
    input_s = safe_non_negative_float(input_duration, 0.0)
    if not has_video_input:
        return {
            "output_seconds": output_s,
            "input_seconds": input_s,
            "combined_seconds": output_s,
            "min_billable_seconds": 0.0,
            "billable_seconds": output_s,
            "billable_mode": "output_only",
        }
    combined = input_s + output_s
    mapping = normalize_sparkvideo_min_billable_by_output(min_billable_table)
    if mapping:
        # SparkVideo: max(input+output, min_table[output])
        min_bill = resolve_sparkvideo_min_billable_seconds(output_s, mapping)
        billable = max(combined, min_bill) if (combined > 0 or min_bill > 0) else 0.0
        mode = "max_combined_or_min_table"
    elif has_video_input:
        # KIE Seedance: With video = Price x (Input + Output)
        min_bill = 0.0
        billable = combined if combined > 0 else output_s
        mode = "combined_input_output"
    else:
        # KIE Seedance: No video = Price x Output
        min_bill = 0.0
        billable = output_s
        mode = "output_only"
    return {
        "output_seconds": output_s,
        "input_seconds": input_s,
        "combined_seconds": combined,
        "min_billable_seconds": float(min_bill),
        "billable_seconds": float(billable),
        "billable_mode": mode,
    }


def estimate_sparkvideo_second_cny_amount(
    *,
    rates: Any,
    resolution_tier: Any,
    has_video_input: bool,
    output_duration: Any,
    input_duration: Any = 0,
    min_billable_table: Any = None,
) -> Dict[str, Any]:
    """
    RunningHub SparkVideo 2.0 supplier CNY amount (before credit conversion).

    without ref / KIE no-video: CNY = rate * output_seconds
    KIE with-video (flat, no min table): CNY = rate * (input + output)
    with ref + min table (SparkVideo): CNY = rate * max(input+output, min_table[output])
    with ref (upscale): CNY = base_rate * billable_seconds + addon_rate * output_seconds
    """
    tier = resolve_sparkvideo_resolution_tier(resolution=resolution_tier) or str(resolution_tier or "").strip().lower()
    rate_map = normalize_sparkvideo_second_cny_rates(rates)
    row = rate_map.get(tier) if tier else None
    billable_meta = resolve_sparkvideo_billable_seconds(
        output_duration=output_duration,
        input_duration=input_duration,
        has_video_input=has_video_input,
        min_billable_table=min_billable_table,
    )
    output_s = float(billable_meta["output_seconds"])
    billable_s = float(billable_meta["billable_seconds"])
    if not row or output_s <= 0 and billable_s <= 0:
        return {
            "cny_amount": 0.0,
            "resolution_tier": tier,
            "rate_branch": "with_video_input" if has_video_input else "without_video_input",
            **billable_meta,
        }

    if has_video_input:
        base = row.get("with_video_base")
        addon = row.get("with_video_addon")
        if base is not None or addon is not None:
            base_v = float(base or 0.0)
            addon_v = float(addon or 0.0)
            cny = (billable_s * base_v) + (output_s * addon_v)
            return {
                "cny_amount": max(0.0, float(cny)),
                "resolution_tier": tier,
                "rate_branch": "with_video_input_upscale",
                "with_video_base_cny": base_v,
                "with_video_addon_cny": addon_v,
                "pricing_kind": row.get("pricing_kind") or "upscale",
                **billable_meta,
            }
        rate = row.get("with_video_input")
        if rate is None:
            rate = row.get("without_video_input")
        cny = billable_s * float(rate or 0.0)
        return {
            "cny_amount": max(0.0, float(cny)),
            "resolution_tier": tier,
            "rate_branch": "with_video_input",
            "unit_rate_cny": float(rate or 0.0),
            "pricing_kind": row.get("pricing_kind") or "native",
            **billable_meta,
        }

    rate = row.get("without_video_input")
    if rate is None:
        rate = row.get("with_video_input")
    cny = output_s * float(rate or 0.0)
    return {
        "cny_amount": max(0.0, float(cny)),
        "resolution_tier": tier,
        "rate_branch": "without_video_input",
        "unit_rate_cny": float(rate or 0.0),
        "pricing_kind": row.get("pricing_kind") or "native",
        **billable_meta,
    }


def resolve_video_second_unit_rate(
    *,
    cost: float,
    cost_input: float,
    cost_output: float,
    has_video_input: bool,
    resolution_tier: Any = None,
    resolution_rates_kie: Any = None,
) -> Dict[str, Any]:
    """
    KIE Seedance 2 style: one rate per second, by resolution + has_video_input.

    Priority:
      1) resolution_rates_kie[tier][with/without] as KIE credits / second
      2) cost_input / cost_output base credits (legacy dual rate)
      3) cost fallback
    """
    tier = resolve_video_resolution_tier(resolution=resolution_tier) if resolution_tier else None
    rates = normalize_video_second_resolution_rates(resolution_rates_kie)
    if tier and tier in rates:
        tier_rates = rates[tier]
        key = "with_video_input" if has_video_input else "without_video_input"
        kie_rate = tier_rates.get(key)
        if kie_rate is None:
            kie_rate = tier_rates.get("without_video_input" if has_video_input else "with_video_input")
        if kie_rate is not None:
            rate_credits = float(kie_credits_to_system_credits(kie_rate))
            return {
                "rate": max(0.0, rate_credits),
                "rate_branch": "with_video_input" if has_video_input else "without_video_input",
                "rate_with_video_input": float(kie_credits_to_system_credits(tier_rates.get("with_video_input") or 0)),
                "rate_without_video_input": float(kie_credits_to_system_credits(tier_rates.get("without_video_input") or 0)),
                "resolution_tier": tier,
                "rate_source": "resolution_rates_kie_per_second",
                "rate_kie_credits_per_second": float(kie_rate),
            }

    with_rate = float(cost_input) if cost_input > 0 else (float(cost) if cost > 0 else float(cost_output))
    without_rate = float(cost_output) if cost_output > 0 else (float(cost) if cost > 0 else float(cost_input))
    rate = with_rate if has_video_input else without_rate
    return {
        "rate": max(0.0, float(rate or 0.0)),
        "rate_branch": "with_video_input" if has_video_input else "without_video_input",
        "rate_with_video_input": max(0.0, float(with_rate or 0.0)),
        "rate_without_video_input": max(0.0, float(without_rate or 0.0)),
        "resolution_tier": tier,
        "rate_source": "rule_base_credits",
    }


def is_video_token_usage(usage: Optional[Dict[str, Any]] = None) -> bool:
    """True when usage is billed as a single video-token pool (Seedance / Ark formula)."""
    payload = dict(usage or {})
    if payload.get("video_token_estimate"):
        return True
    method = str(payload.get("estimation_method") or "").strip().lower()
    if method.startswith("video_token") or method.startswith("seedance2_video_token"):
        return True
    if payload.get("video_token_branch"):
        return True
    # Settle/reserve payloads that carry has_video_input with a single token pool
    # (no LLM prompt/completion split) should also use dual-tier video rates.
    if payload.get("has_video_input") is not None:
        input_tokens = safe_non_negative_int(payload.get("input_tokens", payload.get("prompt_tokens", 0)), 0)
        output_tokens = safe_non_negative_int(payload.get("output_tokens", payload.get("completion_tokens", 0)), 0)
        total_tokens = safe_non_negative_int(payload.get("total_tokens", 0), 0)
        if input_tokens == 0 and (output_tokens > 0 or total_tokens > 0):
            return True
    return False


def resolve_video_token_unit_rate(
    *,
    cost: float,
    cost_input: float,
    cost_output: float,
    has_video_input: bool,
    resolution_tier: Any = None,
    resolution_rates_cny: Any = None,
) -> Dict[str, Any]:
    """
    Video token pricing uses one rate on total tokens, not LLM input/output split.

    Priority:
      1) resolution_rates_cny[tier][with/without] as CNY / million tokens
      2) cost_input / cost_output base credits (legacy dual rate)
      3) cost fallback
    """
    tier = resolve_video_resolution_tier(resolution=resolution_tier) if resolution_tier else None
    rates = normalize_video_token_resolution_rates(resolution_rates_cny)
    if tier and tier in rates:
        tier_rates = rates[tier]
        key = "with_video_input" if has_video_input else "without_video_input"
        cny = tier_rates.get(key)
        # If preferred side missing, fall back to the other side of same tier.
        if cny is None:
            cny = tier_rates.get("without_video_input" if has_video_input else "with_video_input")
        if cny is not None:
            rate_credits = float(supplier_cny_to_base_credits(cny))
            return {
                "rate": max(0.0, rate_credits),
                "rate_branch": "with_video_input" if has_video_input else "without_video_input",
                "rate_with_video_input": float(supplier_cny_to_base_credits(tier_rates.get("with_video_input") or 0)),
                "rate_without_video_input": float(supplier_cny_to_base_credits(tier_rates.get("without_video_input") or 0)),
                "resolution_tier": tier,
                "rate_source": "resolution_rates_cny",
                "rate_cny_per_mtok": float(cny),
            }

    with_rate = float(cost_input) if cost_input > 0 else (float(cost) if cost > 0 else float(cost_output))
    without_rate = float(cost_output) if cost_output > 0 else (float(cost) if cost > 0 else float(cost_input))
    rate = with_rate if has_video_input else without_rate
    return {
        "rate": max(0.0, float(rate or 0.0)),
        "rate_branch": "with_video_input" if has_video_input else "without_video_input",
        "rate_with_video_input": max(0.0, float(with_rate or 0.0)),
        "rate_without_video_input": max(0.0, float(without_rate or 0.0)),
        "resolution_tier": tier,
        "rate_source": "rule_base_credits",
    }


def resolve_provider_kie_credits(usage: Optional[Dict[str, Any]] = None) -> float:
    """Resolve actual KIE credits from settle/callback usage (creditsConsumed)."""
    payload = dict(usage or {})
    direct = safe_non_negative_float(
        payload.get("kie_credits_consumed")
        or payload.get("credits_consumed")
        or payload.get("creditsConsumed")
        , 0.0,
    )
    if direct > 0:
        return float(direct)
    for nested_key in ("provider_usage", "usage"):
        nested = payload.get(nested_key)
        if not isinstance(nested, dict):
            continue
        nested_val = safe_non_negative_float(
            nested.get("kie_credits_consumed")
            or nested.get("credits_consumed")
            or nested.get("creditsConsumed")
            or nested.get("credits")
            , 0.0,
        )
        if nested_val > 0:
            return float(nested_val)
    return 0.0


def resolve_provider_cost_total_cents(usage: Optional[Dict[str, Any]] = None) -> float:
    """Resolve actual supplier CNY cents (e.g. DdiMatuo cost_total_cents). 1 credit = 1 cent."""
    payload = dict(usage or {})

    def _from(src: Dict[str, Any]) -> float:
        if not isinstance(src, dict):
            return 0.0
        direct = safe_non_negative_float(
            src.get("cost_total_cents") if src.get("cost_total_cents") not in (None, "") else src.get("costTotalCents"),
            0.0,
        )
        if direct > 0:
            currency = str(src.get("currency") or "CNY").strip().upper()
            if currency in {"", "CNY"}:
                return float(direct)
        return 0.0

    found = _from(payload)
    if found > 0:
        return found
    for nested_key in ("provider_usage", "usage", "raw"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            found = _from(nested)
            if found > 0:
                return found
    return 0.0


def estimate_base_amount_by_unit(config: Dict[str, Any], usage: Optional[Dict[str, Any]] = None) -> float:
    if not config:
        return 0.0
    unit_type = normalize_unit_type(config.get("unit_type", "per_call"))
    base_cost = float(safe_non_negative_int(config.get("cost", 0), 0))
    cost_input = float(safe_non_negative_int(config.get("cost_input", 0), 0))
    cost_output = float(safe_non_negative_int(config.get("cost_output", 0), 0))
    payload = dict(usage or {})

    # Prefer actual provider-reported KIE credits (callback data.creditsConsumed).
    # Reserve payloads never carry this field, so estimate matrices remain unchanged.
    kie_credits = resolve_provider_kie_credits(payload)
    if kie_credits > 0:
        return float(kie_credits_to_system_credits(kie_credits))

    # Prefer actual supplier CNY cents (DdiMatuo cost_total_cents); 1 credit = 0.01 CNY.
    cost_total_cents = resolve_provider_cost_total_cents(payload)
    if cost_total_cents > 0:
        return float(cost_total_cents)

    # KIE Gemini Omni: duration-bucket × resolution flat KIE credits (or flat with video input).
    omni_rates = (
        payload.get("video_duration_kie_credit_rates")
        or config.get("video_duration_kie_credit_rates")
    )
    if omni_rates:
        has_video_input = bool(payload.get("has_video_input"))
        if not has_video_input and isinstance(payload.get("video_token_estimate"), dict):
            has_video_input = bool(payload["video_token_estimate"].get("has_video_input"))
        omni_est = estimate_kie_omni_duration_credits(
            rates=omni_rates,
            resolution_tier=payload.get("resolution_tier") or payload.get("resolution"),
            has_video_input=has_video_input,
            output_duration=payload.get("duration_seconds", payload.get("duration", 4)),
            width=payload.get("width"),
            height=payload.get("height"),
            resolution=payload.get("resolution"),
        )
        return max(0.0, float(omni_est.get("system_credits") or 0.0))

    if unit_type in TOKEN_UNIT_TYPES:
        input_tokens = safe_non_negative_int(payload.get("input_tokens", payload.get("prompt_tokens", 0)), 0)
        output_tokens = safe_non_negative_int(payload.get("output_tokens", payload.get("completion_tokens", 0)), 0)
        total_tokens = safe_non_negative_int(payload.get("total_tokens", 0), 0)
        if input_tokens == 0 and output_tokens == 0 and total_tokens > 0:
            input_tokens = total_tokens

        divisor = 1_000_000.0 if unit_type == "per_million_tokens" else 1_000.0 if unit_type == "per_1k_tokens" else 1.0
        if unit_type == "per_token":
            raw_divisor = config.get("per_token_divisor")
            if raw_divisor is None:
                raw_divisor = payload.get("per_token_divisor")
            parsed_divisor = safe_non_negative_float(raw_divisor, 1_000_000.0)
            divisor = parsed_divisor if parsed_divisor > 0 else 1_000_000.0

        # Video token pool: one rate x total tokens, selected by has_video_input.
        if is_video_token_usage(payload):
            tokens = max(total_tokens, output_tokens, input_tokens)
            if tokens <= 0:
                estimate = payload.get("video_token_estimate")
                if isinstance(estimate, dict):
                    tokens = safe_non_negative_int(estimate.get("tokens", 0), 0)
            has_video_input = bool(payload.get("has_video_input"))
            if not has_video_input and isinstance(payload.get("video_token_estimate"), dict):
                has_video_input = bool(payload["video_token_estimate"].get("has_video_input"))
            tier = resolve_video_resolution_tier(
                payload.get("width"),
                payload.get("height"),
                payload.get("resolution_tier") or payload.get("resolution"),
            )
            selected = resolve_video_token_unit_rate(
                cost=base_cost,
                cost_input=cost_input,
                cost_output=cost_output,
                has_video_input=has_video_input,
                resolution_tier=tier,
                resolution_rates_cny=(
                    payload.get("video_token_resolution_rates")
                    or config.get("video_token_resolution_rates")
                ),
            )
            token_cost = (float(tokens) * float(selected["rate"])) / divisor
            return max(0.0, float(token_cost))

        token_cost = ((float(input_tokens) * cost_input) + (float(output_tokens) * cost_output)) / divisor
        if cost_input == 0 and cost_output == 0 and base_cost > 0:
            token_cost = (float(max(total_tokens, input_tokens + output_tokens)) * base_cost) / divisor
        return max(0.0, float(token_cost))

    quantity = safe_non_negative_float(payload.get("billing_quantity", 1), 1.0)
    if unit_type == "per_call":
        success_output_count = safe_non_negative_int(
            payload.get("success_output_count", payload.get("successful_outputs", 0)),
            0,
        )
        if success_output_count > 0:
            quantity = float(success_output_count)
        return float(base_cost) * float(max(quantity, 1.0))

    if unit_type == "per_second":
        quantity = safe_non_negative_float(payload.get("duration_seconds", payload.get("duration", 0)), 0.0)
        if quantity <= 0 and payload.get("image_count"):
            quantity = float(safe_non_negative_int(payload.get("image_count"), 1))
    elif unit_type == "per_minute":
        seconds = safe_non_negative_float(payload.get("duration_seconds", payload.get("duration", 0)), 0.0)
        quantity = seconds / 60.0
        if quantity <= 0 and payload.get("image_count"):
            quantity = float(safe_non_negative_int(payload.get("image_count"), 1))
    else:
        return 0.0

    if quantity <= 0:
        return 0.0

    # Per-second resolution matrices (SparkVideo CNY/s, then KIE credits/s).
    if unit_type == "per_second":
        has_video_input = bool(payload.get("has_video_input"))
        if not has_video_input and isinstance(payload.get("video_token_estimate"), dict):
            has_video_input = bool(payload["video_token_estimate"].get("has_video_input"))

        cny_rates = (
            payload.get("video_second_cny_resolution_rates")
            or config.get("video_second_cny_resolution_rates")
        )
        if cny_rates:
            out_duration = safe_non_negative_float(
                payload.get("duration_seconds", payload.get("duration", quantity)),
                0.0,
            )
            in_duration = safe_non_negative_float(
                payload.get("input_duration_seconds", payload.get("input_duration", 0)),
                0.0,
            )
            tier = resolve_sparkvideo_resolution_tier(
                payload.get("width"),
                payload.get("height"),
                payload.get("resolution_tier") or payload.get("resolution"),
            )
            min_table = (
                payload.get("video_second_min_billable_by_output")
                or config.get("video_second_min_billable_by_output")
            )
            # Auto-apply SparkVideo min-duration table only when rates include upscale base/addon.
            if not min_table:
                _rate_map = normalize_sparkvideo_second_cny_rates(cny_rates)
                if any(
                    (isinstance(row, dict) and (
                        row.get("with_video_base") is not None
                        or row.get("with_video_addon") is not None
                        or str(row.get("pricing_kind") or "").lower() == "upscale"
                    ))
                    for row in _rate_map.values()
                ):
                    min_table = dict(SPARKVIDEO_MIN_BILLABLE_BY_OUTPUT)
            estimate = estimate_sparkvideo_second_cny_amount(
                rates=cny_rates,
                resolution_tier=tier,
                has_video_input=has_video_input,
                output_duration=out_duration,
                input_duration=in_duration,
                min_billable_table=min_table,
            )
            # Convert supplier CNY total -> system credits (1 credit = 0.01 CNY).
            return max(0.0, float(estimate.get("cny_amount") or 0.0) * 100.0)

        second_rates = (
            payload.get("video_second_resolution_rates")
            or config.get("video_second_resolution_rates")
        )
        if second_rates:
            tier = resolve_video_resolution_tier(
                payload.get("width"),
                payload.get("height"),
                payload.get("resolution_tier") or payload.get("resolution"),
            )
            selected = resolve_video_second_unit_rate(
                cost=base_cost,
                cost_input=cost_input,
                cost_output=cost_output,
                has_video_input=has_video_input,
                resolution_tier=tier,
                resolution_rates_kie=second_rates,
            )
            # KIE: no video = output; with video = input + output
            out_s = safe_non_negative_float(
                payload.get("duration_seconds", payload.get("duration", quantity)),
                0.0,
            )
            in_s = safe_non_negative_float(
                payload.get("input_duration_seconds", payload.get("input_duration", 0)),
                0.0,
            )
            billable_s = (in_s + out_s) if has_video_input else out_s
            if billable_s <= 0:
                billable_s = float(quantity)
            return max(0.0, float(selected["rate"]) * float(billable_s))

        # Dual rate without resolution matrix: with/without video input.
        if cost_input > 0 or cost_output > 0:
            has_video_input = bool(payload.get("has_video_input"))
            rate = float(cost_input) if has_video_input else float(cost_output)
            if rate <= 0:
                rate = float(cost_output if has_video_input else cost_input)
            if rate <= 0:
                rate = float(base_cost)
            return max(0.0, float(rate) * float(quantity))

    return float(base_cost) * float(quantity)


def compute_user_charge(
    *,
    unit_type: str,
    base_cost: int,
    base_cost_input: int,
    base_cost_output: int,
    charge_multiplier: Any,
    usage: Optional[Dict[str, Any]] = None,
    runtime_multiplier: float = 1.0,
) -> Dict[str, Any]:
    cfg = {
        "unit_type": normalize_unit_type(unit_type),
        "cost": safe_non_negative_int(base_cost, 0),
        "cost_input": safe_non_negative_int(base_cost_input, 0),
        "cost_output": safe_non_negative_int(base_cost_output, 0),
    }
    odds = normalize_charge_multiplier(charge_multiplier, default=2.0)
    runtime = safe_non_negative_float(runtime_multiplier, 1.0) or 1.0
    base_amount = estimate_base_amount_by_unit(cfg, usage)
    base_credits = max(0, int(math.ceil(base_amount))) if base_amount > 0 else 0
    user_credits = apply_odds_to_credits(base_amount, odds, runtime)
    return {
        "unit_type": cfg["unit_type"],
        "base_amount": float(base_amount),
        "base_credits": int(base_credits),
        "charge_multiplier": float(odds),
        "runtime_multiplier": float(runtime),
        "user_credits": int(user_credits),
        "unit_user_cost": apply_odds_to_credits(cfg["cost"], odds, 1.0),
        "unit_user_cost_input": apply_odds_to_credits(cfg["cost_input"], odds, 1.0),
        "unit_user_cost_output": apply_odds_to_credits(cfg["cost_output"], odds, 1.0),
    }


def merge_billing_payload_for_upsert(
    payload: Dict[str, Any],
    *,
    existing_rule: Any = None,
    default_multiplier: float = 2.0,
) -> Dict[str, Any]:
    raw = dict(payload or {})
    unit_type = normalize_unit_type(
        raw.get("unit_type") or raw.get("billing_unit_type") or getattr(existing_rule, "billing_unit_type", None),
        "per_call",
    )

    supplier_keys = (
        "supplier_price",
        "supplier_price_input",
        "supplier_price_output",
        "supplier_currency",
        "supplier_price_basis",
    )
    supplier_touched = any(key in raw for key in supplier_keys)
    existing_supplier = extract_supplier_pricing(existing_rule) if existing_rule is not None else {
        "supplier_price": None,
        "supplier_price_input": None,
        "supplier_price_output": None,
        "supplier_currency": "CNY",
        "supplier_price_basis": "money",
    }

    if supplier_touched:
        def _merge_price(key: str):
            if key in raw and raw.get(key) is not None and raw.get(key) != "":
                return safe_non_negative_float(raw.get(key))
            return existing_supplier.get(key)

        supplier = {
            "supplier_price": _merge_price("supplier_price"),
            "supplier_price_input": _merge_price("supplier_price_input"),
            "supplier_price_output": _merge_price("supplier_price_output"),
            "supplier_currency": normalize_currency(
                raw.get("supplier_currency") if "supplier_currency" in raw else existing_supplier.get("supplier_currency")
            ),
            "supplier_price_basis": normalize_price_basis(
                raw.get("supplier_price_basis") if "supplier_price_basis" in raw else existing_supplier.get("supplier_price_basis")
            ),
        }
    else:
        supplier = existing_supplier

    has_any_supplier = any(
        supplier.get(k) is not None
        for k in ("supplier_price", "supplier_price_input", "supplier_price_output")
    )

    if has_any_supplier and supplier.get("supplier_price_basis") == "money" and supplier.get("supplier_currency") == "CNY":
        derived = derive_base_credits_from_supplier(supplier)
        cost = derived["cost"]
        cost_input = derived["cost_input"]
        cost_output = derived["cost_output"]
    else:
        def _pick(plain: str, billing: str, attr: str) -> int:
            if plain in raw and raw.get(plain) is not None:
                return safe_non_negative_int(raw.get(plain), 0)
            if billing in raw and raw.get(billing) is not None:
                return safe_non_negative_int(raw.get(billing), 0)
            if existing_rule is not None:
                return safe_non_negative_int(getattr(existing_rule, attr, 0), 0)
            return 0

        cost = _pick("cost", "billing_cost", "billing_cost")
        cost_input = _pick("cost_input", "billing_cost_input", "billing_cost_input")
        cost_output = _pick("cost_output", "billing_cost_output", "billing_cost_output")
        if not has_any_supplier and (cost > 0 or cost_input > 0 or cost_output > 0):
            supplier = {
                "supplier_price": base_credits_to_supplier_cny(cost) if cost > 0 else None,
                "supplier_price_input": base_credits_to_supplier_cny(cost_input) if cost_input > 0 else None,
                "supplier_price_output": base_credits_to_supplier_cny(cost_output) if cost_output > 0 else None,
                "supplier_currency": "CNY",
                "supplier_price_basis": "money",
            }

    if "charge_multiplier" in raw and raw.get("charge_multiplier") is not None:
        multiplier = normalize_charge_multiplier(raw.get("charge_multiplier"), default_multiplier)
    elif existing_rule is not None and getattr(existing_rule, "charge_multiplier", None) is not None:
        multiplier = normalize_charge_multiplier(getattr(existing_rule, "charge_multiplier"), default_multiplier)
    else:
        multiplier = float(default_multiplier)

    return {
        "unit_type": unit_type,
        "billing_unit_type": unit_type,
        "supplier_price": supplier.get("supplier_price"),
        "supplier_price_input": supplier.get("supplier_price_input"),
        "supplier_price_output": supplier.get("supplier_price_output"),
        "supplier_currency": supplier.get("supplier_currency") or "CNY",
        "supplier_price_basis": supplier.get("supplier_price_basis") or "money",
        "cost": int(cost),
        "cost_input": int(cost_input),
        "cost_output": int(cost_output),
        "billing_cost": int(cost),
        "billing_cost_input": int(cost_input),
        "billing_cost_output": int(cost_output),
        "charge_multiplier": float(multiplier),
        "unit_user_cost": apply_odds_to_credits(cost, multiplier),
        "unit_user_cost_input": apply_odds_to_credits(cost_input, multiplier),
        "unit_user_cost_output": apply_odds_to_credits(cost_output, multiplier),
    }
