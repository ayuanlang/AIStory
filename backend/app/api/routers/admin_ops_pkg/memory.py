# -*- coding: utf-8 -*-
"""Admin memory monitor routes."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.api.routers.admin_ops_pkg import shared as _shared
from app.models.all_models import User
from app.services.runtime_memory_monitor import (
    collect_memory_stats,
    run_memory_reclaim,
    set_tracemalloc_enabled,
)

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)


class MemoryReclaimRequest(BaseModel):
    prune_caches: bool = True
    collect_gc: bool = True
    malloc_trim: bool = True
    generations: Optional[int] = Field(default=None, ge=0, le=2)


class TracemallocToggleRequest(BaseModel):
    enabled: bool = True


@router.get("/admin/memory-stats")
def get_admin_memory_stats(
    include_tracemalloc: bool = True,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser required")
    return collect_memory_stats(include_tracemalloc=bool(include_tracemalloc))


@router.post("/admin/memory-reclaim")
def post_admin_memory_reclaim(
    body: MemoryReclaimRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser required")
    return run_memory_reclaim(
        prune_caches=bool(body.prune_caches),
        collect_gc=bool(body.collect_gc),
        malloc_trim=bool(body.malloc_trim),
        generations=body.generations,
    )


@router.post("/admin/memory-tracemalloc")
def post_admin_memory_tracemalloc(
    body: TracemallocToggleRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser required")
    return set_tracemalloc_enabled(bool(body.enabled))
