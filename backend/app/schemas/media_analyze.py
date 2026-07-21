# -*- coding: utf-8 -*-
"""Media/image analysis request schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AnalyzeImageRequest(BaseModel):
    asset_id: Optional[int] = None
    image_url: Optional[str] = None
    system_api_id: Optional[int] = None
    function_name: Optional[str] = None
