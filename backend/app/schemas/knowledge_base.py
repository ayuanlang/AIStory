# -*- coding: utf-8 -*-
"""Platform knowledge-base API schemas (P0)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class KbWorkCreate(BaseModel):
    title: str
    title_en: Optional[str] = None
    year: Optional[str] = None
    genre: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None


class KbWorkUpdate(BaseModel):
    title: Optional[str] = None
    title_en: Optional[str] = None
    year: Optional[str] = None
    genre: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None


class KbEntryCreate(BaseModel):
    category: str
    title: str
    work_id: Optional[int] = None
    plot_subtype: Optional[str] = None
    summary: Optional[str] = None
    body_text: Optional[str] = None
    tags: Optional[List[str]] = None
    style_keywords: Optional[List[str]] = None
    license_tier: str = "reference_ok"
    copyright_note: Optional[str] = None
    source_type: str = "manual"
    source_url: Optional[str] = None
    quality_score: Optional[float] = 3.0
    quality_notes: Optional[str] = None
    is_eval_gold: Optional[bool] = False
    # optional inline work create
    work_title: Optional[str] = None
    work_year: Optional[str] = None


class KbEntryUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    work_id: Optional[int] = None
    plot_subtype: Optional[str] = None
    summary: Optional[str] = None
    body_text: Optional[str] = None
    tags: Optional[List[str]] = None
    style_keywords: Optional[List[str]] = None
    license_tier: Optional[str] = None
    copyright_note: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    quality_score: Optional[float] = None
    quality_notes: Optional[str] = None
    is_eval_gold: Optional[bool] = None


class KbEntryReviewRequest(BaseModel):
    action: str = Field(..., description="approve | reject")
    note: Optional[str] = None


class KbEntryQualityRequest(BaseModel):
    quality_score: float = Field(..., ge=0, le=5)
    quality_notes: Optional[str] = None
    is_eval_gold: Optional[bool] = None


class KbSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    plot_subtype: Optional[str] = None
    top_k: int = 12
    # hybrid | semantic | keyword
    mode: str = "hybrid"
    # when set, only search within these entry ids (project collection)
    entry_ids: Optional[List[int]] = None
    # allow restricted tier in browse/search (default false for creative inject path)
    include_restricted: bool = False


class KbEvalCaseCreate(BaseModel):
    query: str
    name: Optional[str] = None
    category: Optional[str] = None
    expected_entry_ids: Optional[List[int]] = None
    expected_tags: Optional[List[str]] = None
    notes: Optional[str] = None
    is_active: bool = True


class KbEvalCaseUpdate(BaseModel):
    query: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    expected_entry_ids: Optional[List[int]] = None
    expected_tags: Optional[List[str]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class KbEvalRunRequest(BaseModel):
    top_k: int = 8
    mode: str = "hybrid"
    category: Optional[str] = None


class KbProjectCollectionUpdate(BaseModel):
    entry_ids: List[int] = Field(default_factory=list)
    collection_only: bool = False


class KbImportJsonRequest(BaseModel):
    entries: List[dict] = Field(default_factory=list)
    dry_run: bool = False
    auto_approve: bool = False
    reindex_approved: bool = True


class KbIngestWebRequest(BaseModel):
    category: str
    topic: str
    work_title: Optional[str] = None
    work_year: Optional[str] = None
    language: str = "zh"
    max_entries: int = 6
    system_api_id: Optional[int] = None


class KbIngestLlmRequest(BaseModel):
    category: str
    source_text: str
    work_title: Optional[str] = None
    work_year: Optional[str] = None
    language: str = "zh"
    max_entries: int = 6
    system_api_id: Optional[int] = None
