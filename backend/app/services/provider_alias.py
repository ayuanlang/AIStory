# -*- coding: utf-8 -*-
"""Provider display-alias helpers for billing/meta payloads."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import all_models as models

ProviderKeyPool = models.ProviderKeyPool


def _build_provider_alias_lookup(db: Session) -> Dict[str, str]:
    rows = db.query(ProviderKeyPool.provider, ProviderKeyPool.provider_alias).all()
    alias_map: Dict[str, str] = {}
    for row in rows:
        provider_key = str(getattr(row, "provider", "") or "").strip().lower()
        alias_text = str(getattr(row, "provider_alias", "") or "").strip()
        if provider_key and alias_text:
            alias_map[provider_key] = alias_text
    return alias_map


def _resolve_provider_alias(alias_map: Dict[str, str], provider: Any) -> Optional[str]:
    provider_key = str(provider or "").strip().lower()
    if not provider_key:
        return None
    alias_text = str((alias_map or {}).get(provider_key) or "").strip()
    return alias_text or None


def _attach_provider_alias_to_dict(meta: Any, alias_map: Dict[str, str]) -> Any:
    if not isinstance(meta, dict):
        return meta
    out = dict(meta)
    provider_text = str(out.get("provider") or "").strip()
    if provider_text and not str(out.get("provider_alias") or "").strip():
        alias_text = _resolve_provider_alias(alias_map, provider_text)
        if alias_text:
            out["provider_alias"] = alias_text
    return out


def _attach_provider_alias_deep(payload: Any, alias_map: Dict[str, str]) -> Any:
    if isinstance(payload, dict):
        out = {k: _attach_provider_alias_deep(v, alias_map) for k, v in payload.items()}
        provider_text = str(out.get("provider") or "").strip()
        if provider_text and not str(out.get("provider_alias") or "").strip():
            alias_text = _resolve_provider_alias(alias_map, provider_text)
            if alias_text:
                out["provider_alias"] = alias_text
        return out
    if isinstance(payload, list):
        return [_attach_provider_alias_deep(item, alias_map) for item in payload]
    return payload


