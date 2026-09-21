# -*- coding: utf-8 -*-
"""Independent commercial promo project APIs."""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routers.workspace import shared as _shared
from app.core.time_utils import now_bj_iso
from app.db.session import get_db
from app.models.all_models import PromoBrand, PromoCatalogAsset, PromoEnterprise, PromoProduct, PromoProject, User
from app.schemas.promo_planner import (
    PromoBrandCreate,
    PromoBrandOut,
    PromoBrandUpdate,
    PromoCatalogAssetAnalyzeRequest,
    PromoCatalogAssetCreate,
    PromoCatalogAssetOut,
    PromoCatalogAssetUpdate,
    PromoEnterpriseCreate,
    PromoEnterpriseOut,
    PromoEnterpriseUpdate,
    PromoAssetAnalyzeRequest,
    PromoPlannerGenerateRequest,
    PromoPlannerInputSaveRequest,
    PromoPlannerResultSaveRequest,
    PromoScriptGenerateRequest,
    PromoScriptSaveRequest,
    PromoProductCreate,
    PromoProductOut,
    PromoProductUpdate,
    PromoProjectCreate,
    PromoProjectOut,
    PromoProjectUpdate,
)
from app.services.promo_planner import (
    bind_promo_catalog,
    analyze_and_persist_catalog_asset,
    analyze_and_persist_promo_asset,
    generate_promo_planner_scheme,
    generate_promo_script,
    ensure_promo_linked_story_project,
    list_catalog_assets,
    load_planner_state,
    merge_planner_result,
    normalize_image_type,
    normalize_media_kind,
    normalize_owner_kind,
    persist_promo_project_extra_info,
    normalize_planner_input,
    persist_planner_state,
    selected_planner_image_assets,
    backfill_enterprise_catalog_from_projects,
    sync_historical_promo_assets_to_enterprises,
    require_catalog_owner,
    require_promo_brand_access,
    require_promo_enterprise_access,
    require_promo_product_access,
    require_promo_project_access,
    result_to_promo_markdown,
    serialize_promo_brand,
    serialize_promo_catalog_asset,
    serialize_promo_enterprise,
    serialize_promo_product,
    serialize_promo_project,
    serialize_promo_script,
    save_promo_script_content,
    soft_delete_promo_linked_story,
    snapshot_from_catalog,
    _active_promo_clause,
    _as_list,
    _text,
)
from app.services.task_manager import submit_async_endpoint as _submit_async

router = _shared.router


@router.get("/promo-projects/", response_model=List[PromoProjectOut])
@router.get("/promo-projects", response_model=List[PromoProjectOut], include_in_schema=False)
def list_promo_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(PromoProject)
        .filter(_active_promo_clause(), PromoProject.owner_id == current_user.id)
        .order_by(PromoProject.updated_at.desc(), PromoProject.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [serialize_promo_project(db, row, current_user) for row in rows]


@router.post("/promo-projects/", response_model=PromoProjectOut)
@router.post("/promo-projects", response_model=PromoProjectOut, include_in_schema=False)
def create_promo_project(
    payload: PromoProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    title = str(payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    incoming = dict(payload.extra_info or {})
    if payload.global_info:
        incoming["global_info"] = dict(payload.global_info)
    extra_info = persist_promo_project_extra_info(
        incoming,
        title=title,
        description=payload.description or "",
        require_aspect_ratio=True,
        require_type=True,
    )
    row = PromoProject(
        title=title,
        description=(payload.description or "").strip() or None,
        extra_info=extra_info,
        owner_id=current_user.id,
    )
    db.add(row)
    db.flush()
    bind_promo_catalog(
        db,
        row,
        current_user,
        enterprise_id=payload.enterprise_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_project(db, row, current_user)


@router.get("/promo-projects/{promo_project_id}", response_model=PromoProjectOut)
def get_promo_project(
    promo_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user)
    return serialize_promo_project(db, row, current_user)


@router.put("/promo-projects/{promo_project_id}", response_model=PromoProjectOut)
def update_promo_project(
    promo_project_id: int,
    payload: PromoProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user)
    if payload.title is not None:
        title = str(payload.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        row.title = title
    if payload.description is not None:
        row.description = str(payload.description or "").strip() or None
    if payload.extra_info is not None or payload.global_info is not None:
        incoming = dict(payload.extra_info or {})
        if payload.global_info:
            incoming["global_info"] = dict(payload.global_info)
        row.extra_info = persist_promo_project_extra_info(
            incoming,
            title=row.title or "",
            description=row.description or "",
            current=dict(row.extra_info or {}),
        )
    elif payload.title is not None or payload.description is not None:
        row.extra_info = persist_promo_project_extra_info(
            {},
            title=row.title or "",
            description=row.description or "",
            current=dict(row.extra_info or {}),
        )
    if payload.enterprise_id is not None or payload.brand_id is not None or payload.product_id is not None:
        bind_promo_catalog(
            db,
            row,
            current_user,
            enterprise_id=payload.enterprise_id if payload.enterprise_id is not None else row.enterprise_id,
            brand_id=payload.brand_id if payload.brand_id is not None else row.brand_id,
            product_id=payload.product_id if payload.product_id is not None else row.product_id,
        )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_project(db, row, current_user)


@router.delete("/promo-projects/{promo_project_id}")
def delete_promo_project(
    promo_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user, owner_only=True)
    now = now_bj_iso()
    row.is_deleted = True
    row.deleted_at = now
    row.updated_at = now
    soft_delete_promo_linked_story(db, row, now)
    db.add(row)
    db.commit()
    return {"status": "deleted", "kind": "promo", "id": promo_project_id}


@router.post("/promo-projects/{promo_project_id}/planner/analyze-asset")
async def analyze_promo_project_asset(
    promo_project_id: int,
    req: PromoAssetAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            analyze_promo_project_asset,
            user_id=current_user.id,
            kind="promo_asset_analysis",
            promo_project_id=promo_project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    row = require_promo_project_access(db, promo_project_id, current_user)
    return await analyze_and_persist_promo_asset(db, project=row, current_user=current_user, req=req)


@router.post("/promo-projects/{promo_project_id}/planner/generate", response_model=PromoProjectOut)
async def generate_promo_project_planner(
    promo_project_id: int,
    req: PromoPlannerGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            generate_promo_project_planner,
            user_id=current_user.id,
            kind="promo_planner",
            promo_project_id=promo_project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    row = require_promo_project_access(db, promo_project_id, current_user)
    return await generate_promo_planner_scheme(db, project=row, current_user=current_user, req=req)


@router.put("/promo-projects/{promo_project_id}/planner/input", response_model=PromoProjectOut)
def save_promo_project_planner_input(
    promo_project_id: int,
    req: PromoPlannerInputSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user)
    overlay = req.enterprise_info.model_dump() if hasattr(req.enterprise_info, "model_dump") else dict(req.enterprise_info or {})
    enterprise, brand, product = bind_promo_catalog(
        db,
        row,
        current_user,
        enterprise_id=req.enterprise_id,
        brand_id=req.brand_id,
        product_id=req.product_id,
        overlay=overlay,
    )
    planner_input = normalize_planner_input(
        snapshot_from_catalog(
            enterprise,
            product,
            brand=brand,
            image_assets=selected_planner_image_assets(overlay),
            overlay=overlay,
        ),
        req.campaign_demand,
    )
    persist_planner_state(db, row, planner_input=planner_input)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_project(db, row, current_user)


@router.put("/promo-projects/{promo_project_id}/planner/result", response_model=PromoProjectOut)
def save_promo_project_planner_result(
    promo_project_id: int,
    req: PromoPlannerResultSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user)
    state = load_planner_state(db, row)
    planner_input = state.get("promo_planner_input") or {}
    result = merge_planner_result(req.promo_planner_result or {})
    incoming_md = (req.promo_dna_global_md or "").strip()
    if not incoming_md and state.get("promo_planner_result") == result:
        return serialize_promo_project(db, row, current_user)
    markdown = incoming_md or result_to_promo_markdown(result, planner_input)
    persist_planner_state(db, row, planner_result=result, markdown=markdown)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_project(db, row, current_user)


@router.post("/promo-projects/{promo_project_id}/scripts/generate", response_model=PromoProjectOut)
async def generate_promo_project_script(
    promo_project_id: int,
    req: PromoScriptGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            generate_promo_project_script,
            user_id=current_user.id,
            kind="promo_script",
            promo_project_id=promo_project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    row = require_promo_project_access(db, promo_project_id, current_user)
    return await generate_promo_script(db, project=row, current_user=current_user, req=req)


@router.post("/promo-projects/{promo_project_id}/script/ensure", response_model=PromoProjectOut)
def ensure_promo_project_script(
    promo_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user)
    state = load_planner_state(db, row)
    ensure_promo_linked_story_project(
        db,
        row,
        current_user=current_user,
        planner_input=state.get("promo_planner_input") or {},
        planner_result=state.get("promo_planner_result") or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_script(db, row, current_user)


@router.get("/promo-projects/{promo_project_id}/script", response_model=PromoProjectOut)
def get_promo_project_script(
    promo_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user)
    return serialize_promo_script(db, row, current_user)


@router.put("/promo-projects/{promo_project_id}/script", response_model=PromoProjectOut)
def save_promo_project_script(
    promo_project_id: int,
    req: PromoScriptSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_project_access(db, promo_project_id, current_user)
    return save_promo_script_content(
        db,
        project=row,
        current_user=current_user,
        script_content=req.script_content,
    )


@router.get("/promo-enterprises/", response_model=List[PromoEnterpriseOut])
@router.get("/promo-enterprises", response_model=List[PromoEnterpriseOut], include_in_schema=False)
def list_promo_enterprises(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(PromoEnterprise)
        .filter(PromoEnterprise.is_deleted.is_(False), PromoEnterprise.owner_id == current_user.id)
        .order_by(PromoEnterprise.updated_at.desc(), PromoEnterprise.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    sync_historical_promo_assets_to_enterprises(db, owner_id=current_user.id)
    db.commit()
    return [serialize_promo_enterprise(db, row) for row in rows]


@router.post("/promo-enterprises/", response_model=PromoEnterpriseOut)
@router.post("/promo-enterprises", response_model=PromoEnterpriseOut, include_in_schema=False)
def create_promo_enterprise(
    payload: PromoEnterpriseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = str(payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    row = PromoEnterprise(
        name=name,
        intro=(payload.intro or "").strip() or None,
        extra_info=dict(payload.extra_info or {}),
        owner_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_enterprise(db, row)


@router.put("/promo-enterprises/{enterprise_id}", response_model=PromoEnterpriseOut)
def update_promo_enterprise(
    enterprise_id: int,
    payload: PromoEnterpriseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_enterprise_access(db, enterprise_id, current_user)
    if payload.name is not None:
        name = str(payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if payload.intro is not None:
        row.intro = str(payload.intro or "").strip() or None
    if payload.extra_info is not None:
        row.extra_info = dict(payload.extra_info or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_enterprise(db, row)


@router.delete("/promo-enterprises/{enterprise_id}")
def delete_promo_enterprise(
    enterprise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_enterprise_access(db, enterprise_id, current_user, owner_only=True)
    now = now_bj_iso()
    row.is_deleted = True
    row.deleted_at = now
    row.updated_at = now
    brands = (
        db.query(PromoBrand)
        .filter(PromoBrand.enterprise_id == enterprise_id, PromoBrand.is_deleted.is_(False))
        .all()
    )
    for brand in brands:
        brand.is_deleted = True
        brand.deleted_at = now
        brand.updated_at = now
        db.add(brand)
    products = (
        db.query(PromoProduct)
        .filter(PromoProduct.enterprise_id == enterprise_id, PromoProduct.is_deleted.is_(False))
        .all()
    )
    for product in products:
        product.is_deleted = True
        product.deleted_at = now
        product.updated_at = now
        db.add(product)
    db.add(row)
    db.commit()
    return {"status": "deleted", "kind": "promo_enterprise", "id": enterprise_id}


@router.get("/promo-brands/", response_model=List[PromoBrandOut])
@router.get("/promo-brands", response_model=List[PromoBrandOut], include_in_schema=False)
def list_promo_brands(
    enterprise_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PromoBrand).filter(PromoBrand.is_deleted.is_(False), PromoBrand.owner_id == current_user.id)
    if enterprise_id:
        query = query.filter(PromoBrand.enterprise_id == int(enterprise_id))
    rows = query.order_by(PromoBrand.updated_at.desc(), PromoBrand.id.desc()).offset(skip).limit(limit).all()
    return [serialize_promo_brand(db, row) for row in rows]


@router.post("/promo-brands/", response_model=PromoBrandOut)
@router.post("/promo-brands", response_model=PromoBrandOut, include_in_schema=False)
def create_promo_brand(
    payload: PromoBrandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = str(payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    enterprise = require_promo_enterprise_access(db, int(payload.enterprise_id), current_user)
    row = PromoBrand(
        name=name,
        intro=(payload.intro or "").strip() or None,
        extra_info=dict(payload.extra_info or {}),
        enterprise_id=enterprise.id,
        owner_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_brand(db, row)


@router.put("/promo-brands/{brand_id}", response_model=PromoBrandOut)
def update_promo_brand(
    brand_id: int,
    payload: PromoBrandUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_brand_access(db, brand_id, current_user)
    if payload.enterprise_id is not None:
        enterprise = require_promo_enterprise_access(db, int(payload.enterprise_id), current_user)
        row.enterprise_id = enterprise.id
    if payload.name is not None:
        name = str(payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if payload.intro is not None:
        row.intro = str(payload.intro or "").strip() or None
    if payload.extra_info is not None:
        row.extra_info = dict(payload.extra_info or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_brand(db, row)


@router.delete("/promo-brands/{brand_id}")
def delete_promo_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_brand_access(db, brand_id, current_user, owner_only=True)
    now = now_bj_iso()
    row.is_deleted = True
    row.deleted_at = now
    row.updated_at = now
    products = (
        db.query(PromoProduct)
        .filter(PromoProduct.brand_id == brand_id, PromoProduct.is_deleted.is_(False))
        .all()
    )
    for product in products:
        product.is_deleted = True
        product.deleted_at = now
        product.updated_at = now
        db.add(product)
    db.add(row)
    db.commit()
    return {"status": "deleted", "kind": "promo_brand", "id": brand_id}


@router.get("/promo-products/", response_model=List[PromoProductOut])
@router.get("/promo-products", response_model=List[PromoProductOut], include_in_schema=False)
def list_promo_products(
    enterprise_id: Optional[int] = Query(None),
    brand_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PromoProduct).filter(PromoProduct.is_deleted.is_(False), PromoProduct.owner_id == current_user.id)
    if brand_id:
        query = query.filter(PromoProduct.brand_id == int(brand_id))
    elif enterprise_id:
        query = query.filter(PromoProduct.enterprise_id == int(enterprise_id))
    rows = query.order_by(PromoProduct.updated_at.desc(), PromoProduct.id.desc()).offset(skip).limit(limit).all()
    return [serialize_promo_product(row, db) for row in rows]


@router.post("/promo-products/", response_model=PromoProductOut)
@router.post("/promo-products", response_model=PromoProductOut, include_in_schema=False)
def create_promo_product(
    payload: PromoProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = str(payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    brand = None
    if payload.brand_id:
        brand = require_promo_brand_access(db, int(payload.brand_id), current_user)
    enterprise = None
    if payload.enterprise_id:
        enterprise = require_promo_enterprise_access(db, int(payload.enterprise_id), current_user)
    elif brand is not None:
        enterprise = require_promo_enterprise_access(db, int(brand.enterprise_id), current_user)
    if enterprise is None:
        raise HTTPException(status_code=400, detail="brand_id or enterprise_id is required")
    if brand is not None and int(brand.enterprise_id) != int(enterprise.id):
        raise HTTPException(status_code=400, detail="Brand does not belong to the selected enterprise")
    row = PromoProduct(
        name=name,
        enterprise_id=enterprise.id,
        brand_id=brand.id if brand else None,
        owner_id=current_user.id,
        product_info=(payload.product_info or "").strip() or None,
        core_selling_points=[_text(x) for x in _as_list(payload.core_selling_points) if _text(x)],
        differentiation=(payload.differentiation or "").strip() or None,
        target_user=(payload.target_user or "").strip() or None,
        pain_points=[_text(x) for x in _as_list(payload.pain_points) if _text(x)],
        competitor_problem=(payload.competitor_problem or "").strip() or None,
        extra_info=dict(payload.extra_info or {}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_product(row, db)


@router.put("/promo-products/{product_id}", response_model=PromoProductOut)
def update_promo_product(
    product_id: int,
    payload: PromoProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_product_access(db, product_id, current_user)
    if payload.brand_id is not None:
        brand = require_promo_brand_access(db, int(payload.brand_id), current_user)
        row.brand_id = brand.id
        row.enterprise_id = brand.enterprise_id
    elif payload.enterprise_id is not None:
        enterprise = require_promo_enterprise_access(db, int(payload.enterprise_id), current_user)
        row.enterprise_id = enterprise.id
    if payload.name is not None:
        name = str(payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if payload.product_info is not None:
        row.product_info = str(payload.product_info or "").strip() or None
    if payload.core_selling_points is not None:
        row.core_selling_points = [_text(x) for x in _as_list(payload.core_selling_points) if _text(x)]
    if payload.differentiation is not None:
        row.differentiation = str(payload.differentiation or "").strip() or None
    if payload.target_user is not None:
        row.target_user = str(payload.target_user or "").strip() or None
    if payload.pain_points is not None:
        row.pain_points = [_text(x) for x in _as_list(payload.pain_points) if _text(x)]
    if payload.competitor_problem is not None:
        row.competitor_problem = str(payload.competitor_problem or "").strip() or None
    if payload.extra_info is not None:
        row.extra_info = dict(payload.extra_info or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_product(row, db)


@router.delete("/promo-products/{product_id}")
def delete_promo_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = require_promo_product_access(db, product_id, current_user, owner_only=True)
    now = now_bj_iso()
    row.is_deleted = True
    row.deleted_at = now
    row.updated_at = now
    db.add(row)
    db.commit()
    return {"status": "deleted", "kind": "promo_product", "id": product_id}


@router.get("/promo-catalog-assets/", response_model=List[PromoCatalogAssetOut])
@router.get("/promo-catalog-assets", response_model=List[PromoCatalogAssetOut], include_in_schema=False)
def list_promo_catalog_assets(
    owner_kind: str = Query(...),
    owner_entity_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_catalog_owner(db, current_user, owner_kind, owner_entity_id)
    kind = normalize_owner_kind(owner_kind)
    if kind == "enterprise":
        rows = backfill_enterprise_catalog_from_projects(
            db,
            enterprise_id=int(owner_entity_id),
            owner_id=current_user.id,
        )
        db.commit()
        return rows
    return list_catalog_assets(db, owner_kind=kind, owner_entity_id=int(owner_entity_id))


@router.post("/promo-catalog-assets/", response_model=PromoCatalogAssetOut)
@router.post("/promo-catalog-assets", response_model=PromoCatalogAssetOut, include_in_schema=False)
def create_promo_catalog_asset(
    payload: PromoCatalogAssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kind = normalize_owner_kind(payload.owner_kind)
    require_catalog_owner(db, current_user, kind, int(payload.owner_entity_id))
    file_url = _text(payload.file_url or payload.img_url)
    if not file_url:
        raise HTTPException(status_code=400, detail="file_url is required")
    image_id = _text(payload.image_id) or f"promo-asset-{int(payload.owner_entity_id)}-{now_bj_iso()}"
    row = PromoCatalogAsset(
        owner_id=current_user.id,
        owner_kind=kind,
        owner_entity_id=int(payload.owner_entity_id),
        media_kind=normalize_media_kind(payload.media_kind),
        asset_type=normalize_image_type(payload.asset_type),
        image_id=image_id,
        file_url=file_url,
        object_name=_text(payload.object_name),
        user_remark=_text(payload.user_remark),
        extra_info=dict(payload.extra_info or {}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_catalog_asset(row)


@router.post("/promo-catalog-assets/{asset_id}/analyze")
async def analyze_promo_catalog_asset(
    asset_id: int,
    req: Optional[PromoCatalogAssetAnalyzeRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            analyze_promo_catalog_asset,
            user_id=current_user.id,
            kind="promo_catalog_asset_analysis",
            asset_id=asset_id,
            req=req or PromoCatalogAssetAnalyzeRequest(),
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    row = (
        db.query(PromoCatalogAsset)
        .filter(PromoCatalogAsset.id == asset_id, PromoCatalogAsset.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_catalog_owner(db, current_user, row.owner_kind, int(row.owner_entity_id))
    return await analyze_and_persist_catalog_asset(
        db,
        row=row,
        current_user=current_user,
        req=req or PromoCatalogAssetAnalyzeRequest(),
    )


@router.put("/promo-catalog-assets/{asset_id}", response_model=PromoCatalogAssetOut)
def update_promo_catalog_asset(
    asset_id: int,
    payload: PromoCatalogAssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(PromoCatalogAsset)
        .filter(PromoCatalogAsset.id == asset_id, PromoCatalogAsset.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_catalog_owner(db, current_user, row.owner_kind, int(row.owner_entity_id))
    if payload.media_kind is not None:
        row.media_kind = normalize_media_kind(payload.media_kind)
    if payload.asset_type is not None:
        row.asset_type = normalize_image_type(payload.asset_type)
    file_url = _text(payload.file_url or payload.img_url)
    if file_url:
        row.file_url = file_url
    if payload.object_name is not None:
        row.object_name = _text(payload.object_name)
    if payload.user_remark is not None:
        row.user_remark = _text(payload.user_remark)
    if payload.extra_info is not None:
        row.extra_info = dict(payload.extra_info or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_promo_catalog_asset(row)


@router.delete("/promo-catalog-assets/{asset_id}")
def delete_promo_catalog_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(PromoCatalogAsset)
        .filter(PromoCatalogAsset.id == asset_id, PromoCatalogAsset.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_catalog_owner(db, current_user, row.owner_kind, int(row.owner_entity_id), owner_only=True)
    now = now_bj_iso()
    row.is_deleted = True
    row.deleted_at = now
    row.updated_at = now
    db.add(row)
    db.commit()
    return {"status": "deleted", "kind": "promo_catalog_asset", "id": asset_id}
