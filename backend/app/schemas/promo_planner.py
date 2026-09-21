# -*- coding: utf-8 -*-
"""Commercial promo planner request / response schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class PromoImageAssetIn(BaseModel):
    img_url: str = ""
    image_id: str = ""
    image_type: str = "product"  # product | character | scene | prop
    media_kind: str = "image"  # image | video
    owner_kind: str = "project"  # project | enterprise | brand | offering
    owner_entity_id: Optional[int] = None
    catalog_asset_id: Optional[int] = None
    object_name: str = ""
    user_remark: str = ""
    analysis_status: str = ""
    analysis_error: str = ""


class PromoEnterpriseInfoIn(BaseModel):
    enterprise_name: str = ""
    enterprise_intro: str = ""
    brand_name: str = ""
    brand_intro: str = ""
    product_name: str = ""
    product_info: str = ""
    core_selling_points: List[str] = Field(default_factory=list)
    differentiation: str = ""
    target_user: str = ""
    pain_points: List[str] = Field(default_factory=list)
    competitor_problem: str = ""
    image_assets: List[PromoImageAssetIn] = Field(default_factory=list)

    @field_validator("core_selling_points", "pain_points", mode="before")
    @classmethod
    def _split_lines(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.replace("，", "\n").splitlines() if part.strip()]


class PromoCampaignDemandIn(BaseModel):
    user_raw_text: str = ""
    basic_intro: str = ""
    target_audience: str = ""
    market_and_competitors: str = ""
    goal_type: str = ""
    narrative_model: str = ""
    presentation_form: str = ""
    platform: Union[str, List[str]] = ""
    expect_duration: str = ""
    existing_material: str = ""
    constraint: str = ""
    cta: str = ""
    episodes_count: Optional[int] = 1


class PromoPlannerGenerateRequest(BaseModel):
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    product_id: Optional[int] = None
    enterprise_info: PromoEnterpriseInfoIn = Field(default_factory=PromoEnterpriseInfoIn)
    campaign_demand: PromoCampaignDemandIn = Field(default_factory=PromoCampaignDemandIn)
    image_asset_analysis: Optional[Dict[str, Any]] = None
    force_reanalyze: bool = False
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class PromoAssetAnalyzeRequest(BaseModel):
    asset: PromoImageAssetIn
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    product_id: Optional[int] = None
    image_asset_analysis: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class PromoPlannerInputSaveRequest(BaseModel):
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    product_id: Optional[int] = None
    enterprise_info: PromoEnterpriseInfoIn = Field(default_factory=PromoEnterpriseInfoIn)
    campaign_demand: PromoCampaignDemandIn = Field(default_factory=PromoCampaignDemandIn)


class PromoPlannerResultSaveRequest(BaseModel):
    promo_planner_result: Dict[str, Any] = Field(default_factory=dict)
    promo_dna_global_md: Optional[str] = None


class PromoScriptGenerateRequest(BaseModel):
    promo_planner_result: Optional[Dict[str, Any]] = None
    overwrite_existing: bool = True
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class PromoScriptSaveRequest(BaseModel):
    script_content: str = ""


class PromoEnterpriseCreate(BaseModel):
    name: str
    intro: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class PromoEnterpriseUpdate(BaseModel):
    name: Optional[str] = None
    intro: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class PromoEnterpriseOut(BaseModel):
    id: int
    name: str
    intro: Optional[str] = None
    extra_info: Dict[str, Any] = Field(default_factory=dict)
    owner_id: int
    brand_count: Optional[int] = 0
    product_count: Optional[int] = 0
    asset_count: Optional[int] = 0
    asset_previews: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PromoBrandCreate(BaseModel):
    enterprise_id: int
    name: str
    intro: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class PromoBrandUpdate(BaseModel):
    enterprise_id: Optional[int] = None
    name: Optional[str] = None
    intro: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class PromoBrandOut(BaseModel):
    id: int
    enterprise_id: int
    enterprise_name: Optional[str] = None
    name: str
    intro: Optional[str] = None
    extra_info: Dict[str, Any] = Field(default_factory=dict)
    owner_id: int
    product_count: Optional[int] = 0
    asset_count: Optional[int] = 0
    asset_previews: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PromoProductCreate(BaseModel):
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    name: str
    product_info: Optional[str] = None
    core_selling_points: List[str] = Field(default_factory=list)
    differentiation: Optional[str] = None
    target_user: Optional[str] = None
    pain_points: List[str] = Field(default_factory=list)
    competitor_problem: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None

    @field_validator("core_selling_points", "pain_points", mode="before")
    @classmethod
    def _split_lines(cls, value: Any) -> List[str]:
        return PromoEnterpriseInfoIn._split_lines(value)


class PromoProductUpdate(BaseModel):
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    name: Optional[str] = None
    product_info: Optional[str] = None
    core_selling_points: Optional[List[str]] = None
    differentiation: Optional[str] = None
    target_user: Optional[str] = None
    pain_points: Optional[List[str]] = None
    competitor_problem: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None

    @field_validator("core_selling_points", "pain_points", mode="before")
    @classmethod
    def _split_lines(cls, value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        return PromoEnterpriseInfoIn._split_lines(value)


class PromoProductOut(BaseModel):
    id: int
    enterprise_id: int
    enterprise_name: Optional[str] = None
    brand_id: Optional[int] = None
    brand_name: Optional[str] = None
    name: str
    product_info: Optional[str] = None
    core_selling_points: List[str] = Field(default_factory=list)
    differentiation: Optional[str] = None
    target_user: Optional[str] = None
    pain_points: List[str] = Field(default_factory=list)
    competitor_problem: Optional[str] = None
    extra_info: Dict[str, Any] = Field(default_factory=dict)
    owner_id: int
    asset_count: Optional[int] = 0
    asset_previews: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PromoCatalogAssetCreate(BaseModel):
    owner_kind: str
    owner_entity_id: int
    media_kind: str = "image"
    asset_type: str = "product"
    image_id: str = ""
    file_url: str = ""
    img_url: Optional[str] = None
    object_name: Optional[str] = None
    user_remark: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class PromoCatalogAssetUpdate(BaseModel):
    media_kind: Optional[str] = None
    asset_type: Optional[str] = None
    file_url: Optional[str] = None
    img_url: Optional[str] = None
    object_name: Optional[str] = None
    user_remark: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class PromoCatalogAssetAnalyzeRequest(BaseModel):
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class PromoCatalogAssetOut(BaseModel):
    id: int
    owner_id: int
    owner_kind: str
    owner_entity_id: int
    media_kind: str = "image"
    asset_type: str = "product"
    image_id: str = ""
    file_url: str = ""
    img_url: str = ""
    image_type: str = "product"
    object_name: str = ""
    user_remark: str = ""
    extra_info: Dict[str, Any] = Field(default_factory=dict)
    analysis_status: str = ""
    analysis_error: str = ""
    image_asset_analysis: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PromoProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None
    global_info: Optional[Dict[str, Any]] = None
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    product_id: Optional[int] = None


class PromoProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None
    global_info: Optional[Dict[str, Any]] = None
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    product_id: Optional[int] = None


class PromoProjectOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    extra_info: Dict[str, Any] = Field(default_factory=dict)
    global_info: Dict[str, Any] = Field(default_factory=dict)
    owner_id: int
    enterprise_id: Optional[int] = None
    brand_id: Optional[int] = None
    product_id: Optional[int] = None
    enterprise: Optional[PromoEnterpriseOut] = None
    brand: Optional[PromoBrandOut] = None
    product: Optional[PromoProductOut] = None
    kind: str = "promo"
    cover_image: Optional[str] = None
    cover_images: Optional[List[str]] = None
    promo_planner_input: Optional[Dict[str, Any]] = None
    promo_planner_result: Optional[Dict[str, Any]] = None
    promo_dna_global_md: Optional[str] = None
    linked_story_project_id: Optional[int] = None
    script_episode_id: Optional[int] = None
    script_content: Optional[str] = None
    has_script: Optional[bool] = False
    is_owner: Optional[bool] = True
    is_temp_view: Optional[bool] = False
    can_edit: Optional[bool] = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
