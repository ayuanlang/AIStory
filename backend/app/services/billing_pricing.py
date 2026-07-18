"""Canonical pricing program for AIStory billing.

Layers:
1) Supplier price (CNY, money) — persisted on billing rules
2) Base credits — ceil(supplier_cny * 100), cached on billing_cost*
3) User charge — base * charge_multiplier (odds) * quantity(by unit_type) * runtime multipliers
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional


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
) -> Dict[str, Any]:
    """
    Video token pricing uses one rate on total tokens, not LLM input/output split.

    Convention (supplier CNY already converted to base credits):
      - cost_input  = with video input (e.g. 28 CNY / million tokens)
      - cost_output = without video input (e.g. 46 CNY / million tokens)
      - cost        = fallback when the preferred tier rate is unset
    """
    with_rate = float(cost_input) if cost_input > 0 else (float(cost) if cost > 0 else float(cost_output))
    without_rate = float(cost_output) if cost_output > 0 else (float(cost) if cost > 0 else float(cost_input))
    rate = with_rate if has_video_input else without_rate
    return {
        "rate": max(0.0, float(rate or 0.0)),
        "rate_branch": "with_video_input" if has_video_input else "without_video_input",
        "rate_with_video_input": max(0.0, float(with_rate or 0.0)),
        "rate_without_video_input": max(0.0, float(without_rate or 0.0)),
    }


def estimate_base_amount_by_unit(config: Dict[str, Any], usage: Optional[Dict[str, Any]] = None) -> float:
    if not config:
        return 0.0
    unit_type = normalize_unit_type(config.get("unit_type", "per_call"))
    base_cost = float(safe_non_negative_int(config.get("cost", 0), 0))
    cost_input = float(safe_non_negative_int(config.get("cost_input", 0), 0))
    cost_output = float(safe_non_negative_int(config.get("cost_output", 0), 0))
    payload = dict(usage or {})

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
            selected = resolve_video_token_unit_rate(
                cost=base_cost,
                cost_input=cost_input,
                cost_output=cost_output,
                has_video_input=has_video_input,
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
